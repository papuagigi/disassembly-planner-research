"""Physical feasibility control: non-LLM reference search with the evaluated checker.

Each state is fully expanded: every canonical candidate (non-fixed part x
allowed direction) is removed from that exact state by the unchanged
FullDisassemblySim (source-axis straight extraction, source-mesh path check,
MuJoCo residual stability). Expansions run in parallel worker processes, each
with its own simulator restored to the exact parent state. Accepted children
are explored depth-first in a fixed generic order (higher part center first,
then ID, then direction). The search stops on n-1 removals (a complete
reference sequence), exhaustion, or the wall cap.

This is a control for interpreting planner failure. Its sequence is never given
to a planner. Absence of a found path is not an impossibility proof; the
per-state sample-0 lock records explain what blocked progress.
Pruning by remaining-part set (approximation) is recorded when used.
"""
from __future__ import annotations
import argparse
import json
import concurrent.futures as cf
import copy
import multiprocessing as mp
import os
import time
from pathlib import Path

from .common import ROOT, read, utc, write

_SIM = None


def _init(case_path, variant=None):
    global _SIM
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    from .physics_variants import apply
    apply(variant)  # diagnostic-only collision rule; None = evaluated physics
    from disassembly_real_v3.simulator import FullDisassemblySim
    _SIM = FullDisassemblySim(case_path, max_checks=10**9, capture=False)


def _try(state, pid, direction):
    _SIM.restore_state(dict(remaining=state['remaining'], poses=state['poses'], checks=0, trace=[], actions=[]))
    started = time.monotonic()
    r = _SIM.remove(pid, direction)
    out = dict(part_id=pid, direction=direction, valid=bool(r['valid']), reason=r['reason'],
               blockers=r.get('blockers', []), collision_distance_m=r.get('collision_distance_m'),
               seconds=time.monotonic() - started)
    if r['valid']:
        out['child'] = dict(remaining=list(_SIM.remaining), poses=copy.deepcopy(_SIM.poses))
    return out


def _key(state):
    from disassembly_recovery.shared_api import physical_state_key
    return physical_state_key(dict(remaining=state['remaining'], poses=state['poses']))


def search(case_path, wall_seconds, workers, out_path, prune_remaining_set=True, max_checks=None, variant=None, prefix=None):
    case_path = str(Path(case_path).resolve())
    case = read(case_path)
    parts = {p['id']: p for p in case['parts']}
    fixed = {p for p, v in parts.items() if v.get('fixed', False)}
    from disassembly_real_v3.simulator import FullDisassemblySim
    root_sim = FullDisassemblySim(case_path, max_checks=10**9, capture=False)
    prefix = [list(a) for a in (prefix or [])]
    from .physics_variants import apply as _apply_variant
    _apply_variant(variant)
    for pid, d in prefix:  # diagnostic seed: a known accepted prefix, re-verified with the same simulator
        assert root_sim.remove(pid, d)['valid'], ('prefix action rejected', pid, d)
    root = dict(remaining=list(root_sim.remaining), poses=copy.deepcopy(root_sim.poses))
    started = time.monotonic()
    expanded, explored_sets, dead = [], set(), set()
    stats = dict(checks=0, accepted=0, rejected_by_reason={})
    found = None
    status = 'running'

    def flush(final=False):
        write(out_path, dict(case_id=case['id'], case_path=case_path, utc=utc(), status=status,
                             wall_cap_seconds=wall_seconds, check_cap=max_checks, physics_variant=variant or 'evaluated_physics_unchanged', seeded_prefix=prefix, elapsed_seconds=time.monotonic() - started,
                             workers=workers, method=__doc__.strip(), prune_remaining_set=prune_remaining_set,
                             total_parts=len(parts), required_removals=len(parts) - 1, fixed=sorted(fixed),
                             stats=stats, reference_sequence=found, max_removed_reached=max([e['removed'] for e in expanded] + [0]),
                             expanded_states=expanded, final=final))

    ctx = mp.get_context('spawn')
    with cf.ProcessPoolExecutor(max_workers=workers, mp_context=ctx, initializer=_init, initargs=(case_path, variant)) as pool:
        def expand(state, path):
            nonlocal status, found
            if found is not None or time.monotonic() - started > wall_seconds:
                return
            if max_checks is not None and stats['checks'] >= max_checks:
                return
            if len(state['remaining']) <= 1:
                found = path
                return
            key = _key(state)
            rset = frozenset(state['remaining'])
            if key in dead or (prune_remaining_set and rset in explored_sets):
                return
            explored_sets.add(rset)
            cands = [(p, d) for p in sorted(state['remaining']) if p not in fixed
                     for d in parts[p].get('allowed_directions', ['+x', '-x', '+y', '-y', '+z', '-z'])]
            futures = [pool.submit(_try, state, p, d) for p, d in cands]
            rows = []
            for f in futures:
                remaining_time = wall_seconds - (time.monotonic() - started)
                try:
                    rows.append(f.result(timeout=max(1., remaining_time + 120)))
                except cf.TimeoutError:
                    status = 'wall_cap_during_expansion'
                    for g in futures:
                        g.cancel()
                    return
            stats['checks'] += len(rows)
            for r in rows:
                if r['valid']:
                    stats['accepted'] += 1
                else:
                    stats['rejected_by_reason'][r['reason']] = stats['rejected_by_reason'].get(r['reason'], 0) + 1
            locks = {}
            for r in rows:
                if not r['valid'] and r['reason'] == 'path_collision' and r['collision_distance_m'] == 0:
                    locks.setdefault(r['part_id'], set()).update(r['blockers'])
            accepted = [r for r in rows if r['valid']]
            expanded.append(dict(state_key=key, removed=len(path), remaining=sorted(state['remaining']),
                                 candidates=len(rows), accepted=[[r['part_id'], r['direction']] for r in accepted],
                                 sample0_locked={p: sorted(b) for p, b in sorted(locks.items())},
                                 elapsed_seconds=time.monotonic() - started))
            flush()
            centers = {p: state['poses'][p]['position'][2] for p in state['remaining']}
            accepted.sort(key=lambda r: (-centers[r['part_id']], r['part_id'], r['direction']))
            for r in accepted:
                expand(r['child'], path + [[r['part_id'], r['direction']]])
                if found is not None or time.monotonic() - started > wall_seconds:
                    return
            dead.add(key)

        expand(root, list(prefix))
    if found is not None:
        status = 'complete_reference_found'
    elif max_checks is not None and stats['checks'] >= max_checks:
        status = 'check_cap_reached_no_complete_path_found'
    elif time.monotonic() - started > wall_seconds or status == 'wall_cap_during_expansion':
        status = 'wall_cap_reached_no_complete_path_found'
    else:
        status = 'search_exhausted_no_complete_path' + ('_with_remaining_set_pruning' if prune_remaining_set else '')
    flush(final=True)
    return status


def main():
    p = argparse.ArgumentParser()
    p.add_argument('case')
    p.add_argument('--wall', type=float, default=2400.)
    p.add_argument('--workers', type=int, default=12)
    p.add_argument('--out', required=True)
    p.add_argument('--no-prune', action='store_true')
    p.add_argument('--max-checks', type=int, default=None)
    p.add_argument('--variant', default=None)
    p.add_argument('--prefix-json', default=None, help='JSON list of [part, direction] accepted prefix (diagnostic seed)')
    a = p.parse_args()
    print(search(a.case, a.wall, a.workers, a.out, prune_remaining_set=not a.no_prune, max_checks=a.max_checks, variant=a.variant,
                 prefix=json.loads(a.prefix_json) if a.prefix_json else None), flush=True)


if __name__ == '__main__':
    main()

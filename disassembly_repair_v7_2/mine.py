"""Deterministic failure mining for S4 (no model call).

Unlike v6 (which kept only "failure followed by a successful alternative" pairs and so
over-promised retrying other directions), every recorded query is counted. Output is a
CAD-anonymous statistics bundle plus a few anonymized examples for the SKILL.md writer.
Pilot CADs reserved for the retry evaluation are rejected as inputs.
"""
from __future__ import annotations
import collections
import json
import math
from pathlib import Path

from .common import ROOT, read, write, utc, V7_PILOT_CADS

UP = 0.7  # |world z| threshold for an "up/down" direction


def _rate(a, n):
    return None if n == 0 else round(a / n, 3)


def _rank(values, x):
    s = sorted(values)
    return (s.index(x) / max(1, len(s) - 1)) if len(s) > 1 else 0.5


def mine(result_paths, out_path=None):
    for p in result_paths:
        assert not any(c in str(p) for c in V7_PILOT_CADS), ('pilot CAD must not feed S4', p)
    by_k = collections.Counter()           # k already-rejected directions -> (accepted next, tried next)
    by_k_ok = collections.Counter()
    feat = collections.defaultdict(lambda: [0, 0])   # feature bucket -> [accepted, tried]
    blocker_first = [0, 0]                  # after a collision naming Q, Q's next query at same state accepted?
    episodes, wasted_enclosed, total_checks, deadend_checks = [], 0, 0, 0
    examples = []
    code_errors = collections.Counter()     # generated-code execution errors (type: message), anonymized
    first_ten = collections.defaultdict(collections.Counter)  # condition -> direction family of each episode's first 10 checks
    reuse = [0, 0]                          # direction == last committed removal's direction
    other_after_success = [0, 0]            # other directions once some removal has succeeded
    per_condition = collections.defaultdict(lambda: dict(episodes=0, checks=0, dir_family=collections.Counter(),
                                                         accepted_family=collections.Counter(), enclosed_checks=0,
                                                         first_accepts=[]))
    for p in result_paths:
        r = read(p)
        obs = r.get('initial_observation') or {}
        vectors = obs.get('direction_vectors_world') or {}
        trace = r.get('trace', [])
        total_checks += len(trace)
        # per exact state bookkeeping
        state_rejects = collections.defaultdict(lambda: collections.defaultdict(set))
        blockers_seen = collections.defaultdict(set)
        parts_by_state = {}
        source = 'v6' if 'disassembly_final_v6' in str(p) else 'v7.2'
        pc = per_condition[source + ':' + str(r.get('condition') or 'unknown')]
        for d in r.get('decisions', []):
            e = d.get('execution_error')
            if e and e.get('type') not in ('LimitError', 'WallTimeLimit', 'InstructionLimit', 'MemoryLimit'):
                code_errors[f"{e.get('type')}: {str(e.get('message'))[:160]}"] += 1
        pc['episodes'] += 1
        pc['checks'] += len(trace)
        last_dir = None
        for t in trace:
            st = t.get('physical_state_key_before')
            pid, d = t.get('part_id'), t.get('direction')
            if st is None or pid is None:
                continue
            if last_dir is not None:
                bucket = reuse if d == last_dir else other_after_success
                bucket[1] += 1
                bucket[0] += bool(t.get('valid'))
            if t.get('committed'):
                last_dir = d
            k = len(state_rejects[st][pid])
            by_k[min(k, 5)] += 1
            if t.get('valid'):
                by_k_ok[min(k, 5)] += 1
            elif k >= 3:
                wasted_enclosed += 1
            # world direction family
            v = vectors.get(d)
            fam = 'unknown' if not v else ('up' if v[2] > UP else ('down' if v[2] < -UP else 'lateral'))
            pc['dir_family'][fam] += 1
            if trace.index(t) < 10:
                first_ten[source + ':' + str(r.get('condition') or 'unknown')][fam] += 1
            if t.get('valid'):
                pc['accepted_family'][fam] += 1
            elif k >= 3:
                pc['enclosed_checks'] += 1
            feat['dir:' + fam][1] += 1
            feat['dir:' + fam][0] += bool(t.get('valid'))
            # blocker-first rule
            if pid in blockers_seen[st]:
                blocker_first[1] += 1
                blocker_first[0] += bool(t.get('valid'))
            if not t.get('valid'):
                state_rejects[st][pid].add(d)
                for b in t.get('blockers') or []:
                    if b != '__floor__':
                        blockers_seen[st].add(b)
        # height / size ranks from the initial observation (root state only, where geometry is known)
        parts = {q['id']: q for q in obs.get('remaining_parts', []) if not q.get('fixed')}
        if parts:
            zs = [q['center'][2] for q in parts.values()]
            vols = [math.prod(max(1e-9, b - a) for a, b in zip(*q['bounds'])) for q in parts.values()]
            root = trace[0].get('physical_state_key_before') if trace else None
            for t in trace:
                if t.get('physical_state_key_before') != root or t.get('part_id') not in parts:
                    continue
                q = parts[t['part_id']]
                zr = _rank(zs, q['center'][2])
                vr = _rank(vols, math.prod(max(1e-9, b - a) for a, b in zip(*q['bounds'])))
                for name, rank in (('height', zr), ('volume', vr)):
                    bucket = f'{name}:{"top" if rank >= 2/3 else ("middle" if rank >= 1/3 else "bottom")}_third'
                    feat[bucket][1] += 1
                    feat[bucket][0] += bool(t.get('valid'))
        # dead-end states (all tried, none accepted) and their check spend
        led = (r.get('observation') or {}).get('search_ledger', {})
        dead = {s['state_key'] for s in led.get('states', []) if s.get('known_dead_end')}
        deadend_checks += sum(1 for t in trace if t.get('physical_state_key_before') in dead)
        accepted = [t for t in trace if t.get('committed')]
        pc['first_accepts'].append(accepted[0]['checker_call'] if accepted else None)
        episodes.append(dict(condition=r.get('condition'), success=bool(r.get('success')), checks=len(trace),
                             removed=len(r.get('actions', [])), required=r.get('required_removals'),
                             termination=r.get('termination'), first_accept_check=accepted[0]['checker_call'] if accepted else None,
                             cached_rejections=len((r.get('recovery_state') or {}).get('cached_rejections', [])),
                             llm_calls=r.get('llm_calls')))
        if len(examples) < 6:
            # anonymized: positions only, no part IDs or CAD names
            enclosed = [(s, pid, len(ds)) for s, m in state_rejects.items() for pid, ds in m.items() if len(ds) >= 3]
            if enclosed:
                examples.append(dict(kind='enclosed_part', directions_rejected=enclosed[0][2],
                                     note='A part rejected in several directions at one exact state; later accepted removals were other parts.'))
    bundle = dict(
        utc=utc(), inputs=len(result_paths), episodes=episodes, total_checks=total_checks,
        p_accept_given_k_prior_rejections_same_part_same_state={str(k): _rate(by_k_ok[k], by_k[k]) for k in sorted(by_k)},
        tries_by_k={str(k): by_k[k] for k in sorted(by_k)},
        checks_spent_on_parts_with_3plus_rejections_at_state=wasted_enclosed,
        accept_rate_by_feature={k: dict(rate=_rate(a, n), tried=n) for k, (a, n) in sorted(feat.items())},
        blocker_named_part_next_query_accept_rate=dict(rate=_rate(*blocker_first), tried=blocker_first[1]),
        accept_rate_same_direction_as_most_recent_committed_removal_of_ANY_part=dict(
            rate=_rate(*reuse), tried=reuse[1],
            meaning='After some part P was removed along direction label L, later queries on OTHER remaining parts '
                    'that also used label L were accepted at this rate (assemblies often share one insertion axis).'),
        accept_rate_other_directions_after_a_committed_removal=dict(
            rate=_rate(*other_after_success), tried=other_after_success[1],
            meaning='Same situation, queries using any label different from the most recent successful label L.'),
        per_condition={c: dict(episodes=v['episodes'], checks=v['checks'], checks_by_direction_family=dict(v['dir_family']),
                               accepted_by_direction_family=dict(v['accepted_family']),
                               checks_on_parts_with_3plus_rejections=v['enclosed_checks'], first_accept_checks=v['first_accepts'])
                       for c, v in per_condition.items()},
        first_ten_checks_direction_family=first_ten,
        checks_at_known_dead_end_states=deadend_checks,
        generated_code_execution_errors=dict(code_errors.most_common(12)),
        anonymized_examples=examples,
        scope='Counts over every recorded query of development episodes; no CAD IDs, part IDs or reference sequences.')
    if out_path:
        write(out_path, bundle)
    return bundle


if __name__ == '__main__':
    import sys
    b = mine([Path(p) for p in sys.argv[2:]], sys.argv[1])
    print(json.dumps({k: v for k, v in b.items() if k not in ('episodes', 'anonymized_examples')}, indent=1))

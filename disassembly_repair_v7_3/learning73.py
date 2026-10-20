"""v7.3 case registry, job builder and the offline rule gate for SKILL.md reference implementations.

Development CADs reuse the existing case files and shared initial states read-only (v7.2 outputs/cases for the
v7.2 development CADs, v7 pilot selection for the v7.1 pilot CADs). New evaluation CADs come from
outputs/protocol/selection_selected.json.

Offline rule gate (fixed before S5 is written): the "## Reference implementation" program of a candidate SKILL.md is
run WITHOUT any model, as the generated-code policy of one episode, on each S5 input CAD (P2 physics, E1, the same
restricted runtime and API as A/B, max 240 charged checks, 10M instructions). It passes if it fully disassembles at
least 4 of the 5 CADs within 240 checks. Wall time is capped at 1800 s per run and reported, not used for passing,
because gate runs execute in parallel; charged checks are deterministic per state and do not depend on CPU load.
"""
from __future__ import annotations
import collections
import concurrent.futures as cf
import multiprocessing as mp
import time

from .common import ROOT, V7, V72, read, write, utc
from .mine73 import S5_INPUT_CADS, VALIDATION_CADS

PHYSICS = 'P2_persist_up_to_stable_penetration'
GATE_MIN_SUCCESSES = 4
GATE_WALL_SECONDS = 1800.


def dev_case(cid):
    if cid in ('asap_05902', 'asap_06146', 'asap_03012'):
        c = [x for x in read(V7 / 'outputs/protocol/pilot_selected_P2.json')['cases'] if x['case_id'] == cid][0]
        return dict(case_id=cid, case_path=c['case_path'], shared_path=c['shared_path'])
    from disassembly_repair_v7_2.learning import DEV_CASES
    from .common import WORKSPACE
    shared = V72 / 'outputs/cases' / cid / 'shared.json'
    assert shared.exists(), shared
    return dict(case_id=cid, case_path=str(WORKSPACE / DEV_CASES[cid]), shared_path=str(shared))


def eval_case(cid):
    c = [x for x in read(ROOT / 'outputs/protocol/selection_selected.json')['cases'] if x['case_id'] == cid][0]
    return dict(case_id=cid, case_path=c['case_path'], shared_path=c['shared_path'])


def job(case, arm, bank, phase, folder, protocol_sha256=None):
    from .contracts import LIMITS, ARMS
    return dict(folder=str(folder), case_path=case['case_path'], shared_path=case['shared_path'],
                architecture=ARMS[arm]['architecture'], bank_path=str(bank), limits=LIMITS, phase=phase, arm=arm,
                protocol_sha256=protocol_sha256, physics_variant=PHYSICS)


def policy_run(args):
    """One model-free episode of a fixed program (runs in its own process)."""
    cid, code, threads = args
    import os
    os.environ['V73_GEOMETRY_THREADS'] = str(threads)
    from disassembly_real_v3.simulator import FullDisassemblySim
    from disassembly_repair_v7.physics_variants import apply
    from .contracts import LIMITS
    from . import fast_geometry, runtime
    fast_geometry.THREADS = threads
    apply(PHYSICS)
    fast_geometry.install()
    runtime.guards.memory_check = lambda: None
    case = dev_case(cid)
    shared = read(case['shared_path'])
    sim = FullDisassemblySim(case['case_path'], max_checks=LIMITS['max_checks'], state=shared['state'])
    started = time.monotonic()
    payload = dict(code=code, max_checks=LIMITS['max_checks'], max_steps=LIMITS['max_steps'], timeout_seconds=GATE_WALL_SECONDS,
                   recovery_state=shared['recovery_state'], max_checkpoints=LIMITS['max_checkpoints'],
                   max_restores=LIMITS['max_restores'], deadline_monotonic=started + GATE_WALL_SECONDS)
    result = {}
    try:
        result = runtime.execute_payload(payload, sim, callback=lambda e: None)
        error = result['error']
    except Exception as exc:   # compile errors surface here
        error = dict(type=type(exc).__name__, message=str(exc)[:600])
    # End-state facts (what a CODE planner would see in its next turn), for writer feedback only.
    ledger = ((result.get('observation') or {}).get('search_ledger') or {}) if isinstance(result, dict) else {}
    current = ledger.get('current') or {}
    vec = sim.snapshot().get('direction_vectors_world', {})
    fam = lambda d: 'up' if vec.get(d, [0, 0, 0])[2] > .7 else ('down' if vec.get(d, [0, 0, 0])[2] < -.7 else 'lateral')  # noqa: E731
    ended = 'success' if sim.success else ('error' if error else 'program_returned_before_full_disassembly')
    return dict(case_id=cid, success=bool(sim.success), removed=len(sim.actions), checks=sim.checks,
                seconds=round(time.monotonic() - started, 1), error=error, ended=ended,
                first_accept_check=next((t['checker_call'] for t in sim.trace if t.get('committed')), None),
                untested_actions_at_end=current.get('untested_action_count'),
                resumable_checkpoints_at_end=len(ledger.get('resumable_checkpoints') or []),
                known_dead_end_states=ledger.get('known_dead_end_state_count'),
                accepted_by_world_family=dict(collections.Counter(fam(t['direction']) for t in sim.trace if t.get('committed'))),
                queried_by_world_family=dict(collections.Counter(fam(t['direction']) for t in sim.trace)))


def gate(code, cads=S5_INPUT_CADS, threads=3, workers=5):
    with cf.ProcessPoolExecutor(min(workers, len(cads)), mp_context=mp.get_context('spawn')) as ex:
        rows = list(ex.map(policy_run, [(c, code, threads) for c in cads]))
    passed = sum(r['success'] for r in rows) >= GATE_MIN_SUCCESSES
    return dict(utc=utc(), passed=passed, successes=sum(r['success'] for r in rows), rows=rows,
                rule=f'>= {GATE_MIN_SUCCESSES} of {len(cads)} full disassemblies within 240 checks (model-free reference implementation)')

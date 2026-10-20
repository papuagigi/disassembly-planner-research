"""Saved-code / saved-response regression on the known v6 CADs (development only).

No model is called: providers replay preserved v6 responses in their original
order. Physics answers come from preserved v6 traces when the exact query was
recorded, otherwise from the unchanged real simulator (hybrid). These runs test
the v7 mechanics on real geometry; they are NOT first-encounter results and a
replayed response was not conditioned on the v7 prompt.

Scenarios
  a_v6_repro   v6 runtime + v3 API, A/05954 code, strict oracle, 160 checks -> exact v6 trace?
  a_v7         v7 actor, A/05954 code, hybrid oracle, default limits
  b_v6_repro   v6 runtime, B/05954 call-3 code at the preserved dead end -> 0 checks?
  b_v7         v7 actor, B/05954 responses 1..8, hybrid oracle -> no_progress_stop?
  c_v7         v7 actor, C/06444 responses 1..8 replayed under the v7 scheduler, hybrid oracle
"""
from __future__ import annotations
import argparse
import copy
import time
from pathlib import Path

from ..common import ROOT, read, utc, v6_trial, write, V6
from .providers import ReplayProvider
from .replay_sim import ReplaySim, load_oracle, v6_case_path, v6_shared

OUT = ROOT / 'outputs/regression'


class NoMoreResponses(RuntimeError):
    pass


class BoundedReplay(ReplayProvider):
    def complete(self, prompt, schema, call_index):
        if call_index > len(self.responses):
            raise NoMoreResponses('preserved v6 responses exhausted at call %d (offline replay boundary)' % call_index)
        return super().complete(prompt, schema, call_index)


def _sim(case_id, mode, max_checks, state=None):
    oracle, poses = load_oracle(case_id)
    return ReplaySim(v6_case_path(case_id), oracle, poses, mode=mode, max_checks=max_checks, capture=False, state=state)


def summarize(result, sim):
    from collections import Counter
    trace = result['trace']
    seen, reentry = set(), 0
    for t in trace:
        if t.get('committed'):
            k = (t['physical_state_key_before'], t['part_id'], t['direction'])
            reentry += k in seen
            seen.add(k)
    total = result.get('total_part_count') or len(sim.parts)
    best = max([len(result.get('actions', []))] + [total - len(t.get('remaining_after', [])) for t in trace])
    rec = result.get('recovery_state', {})
    first_valid = next((t['checker_call'] for t in trace if t.get('valid')), None)
    return dict(success=bool(result.get('success')), termination=result.get('termination'),
                final_removed=len(result.get('actions', [])), best_removed=best, checks=len(trace),
                first_valid_action_check=first_valid, accepted_edge_reentries=reentry,
                guarded_requests=len(rec.get('guarded_requests', [])),
                restores=rec.get('restore_count'), checkpoints=len(rec.get('checkpoints', {})),
                auto_checkpoints=sum(1 for a in rec.get('auto_checkpoints', []) if a.get('created')),
                llm_calls=result.get('llm_calls'), error=result.get('error'),
                failure_reasons=dict(Counter(t['reason'] for t in trace if not t.get('valid'))),
                replay_sources=dict(Counter(r['source'] for r in sim.replay_log)),
                recomputed_child_key_mismatches=sum(1 for r in sim.replay_log if r.get('child_key_matches') is False))


def a_v6_repro():
    from disassembly_real_v3 import runtime as old
    old.memory_check = lambda: None
    old.guards.memory_check = lambda: None
    shared = v6_shared('asap_05954')
    sim = _sim('asap_05954', 'strict', 160, state=shared['state'])
    code = read(v6_trial('asap_05954', 'A'))['decisions'][0]['response']['code']
    payload = dict(code=code, exports=[], library_bank=None, max_checks=160, max_steps=10_000_000,
                   timeout_seconds=3600., recovery_state=shared['recovery_state'], max_checkpoints=128, max_restores=256)
    result = old.execute_payload(payload, sim, callback=lambda e: None)
    original = read(v6_trial('asap_05954', 'A'))['trace']
    same = [(t['physical_state_key_before'], t['part_id'], t['direction'], t['valid']) for t in result['trace']] == \
           [(t['physical_state_key_before'], t['part_id'], t['direction'], t['valid']) for t in original]
    result['termination'] = 'v6_runtime_' + (result['error']['type'] if result['error'] else 'returned')
    return result, sim, dict(trace_identical_to_v6=same)


def _v7(case_id, arm, mode='hybrid', responses_upto=None, limits=None):
    from ..actors import solve
    v6 = read(v6_trial(case_id, arm))
    responses = [d['response'] for d in v6['decisions']][:responses_upto]
    provider = BoundedReplay(responses)
    shared = v6_shared(case_id)
    bank = V6 / 'memory' / ('S0.json' if arm == 'A' else 'S3.json')
    arch = 'graph_dfs' if arm == 'C' else 'code'
    holder = {}

    def factory():
        holder['sim'] = _sim(case_id, mode, 240, state=shared['state'])
        return holder['sim']
    result = solve(v6_case_path(case_id), provider, bank, arch, shared=shared, limits=limits,
                   progress_path=OUT / f'{case_id}_{arm}_v7' / 'progress.json', sim_factory=factory)
    return result, holder['sim'], dict(replayed_responses=len(responses))


def b_v6_repro():
    from disassembly_real_v3 import runtime as old
    old.memory_check = lambda: None
    old.guards.memory_check = lambda: None
    v6 = read(v6_trial('asap_05954', 'B'))
    sim = _sim('asap_05954', 'strict', 240, state=v6['state'])
    code = v6['decisions'][2]['response']['code']
    payload = dict(code=code, exports=[], library_bank=None, max_checks=240, max_steps=10_000_000,
                   timeout_seconds=600., recovery_state=v6['recovery_state'], max_checkpoints=128, max_restores=256)
    before = sim.checks
    result = old.execute_payload(payload, sim, callback=lambda e: None)
    result['termination'] = 'v6_runtime_' + (result['error']['type'] if result['error'] else 'returned')
    return result, sim, dict(new_checks=sim.checks - before, start_checks=before)


RESUME_PROGRAM = """def run(api):
    s = api.snapshot()
    rows = s['search_ledger']['resumable_checkpoints']
    if len(rows) == 0:
        return
    best = rows[0]
    for r in rows:
        if r['removed_count'] > best['removed_count']:
            best = r
    api.restore(best['handle'])
    s = api.snapshot()
    tested = set()
    for f in s['current_state_feedback']:
        tested.add((f['part_id'], f['direction']))
    for p in s['remaining_parts']:
        if p['fixed']:
            continue
        for d in p['allowed_directions']:
            if (p['id'], d) in tested:
                continue
            r = api.remove(p['id'], d)
            if r['valid']:
                return
run(api)
"""


def b_resume_probe():
    """Mechanism check, not an LLM result: a fixed replacement program resumes the deepest
    non-dead-end saved state of the b_v7 end state using only search_ledger facts."""
    from .. import runtime
    runtime.guards.memory_check = lambda: None
    end = read(OUT / 'asap_05954_B_v7/progress.json')
    sim = _sim('asap_05954', 'hybrid', 240, state=end['state'])
    before = sim.checks
    payload = dict(code=RESUME_PROGRAM, max_checks=240, max_steps=10_000_000, timeout_seconds=600.,
                   recovery_state=end['recovery_state'], max_checkpoints=128, max_restores=256)
    result = runtime.execute_payload(payload, sim, callback=lambda e: None)
    restores = [e for e in result['recovery_state']['events'] if e['operation'] == 'restore']
    result['termination'] = 'fixed_resume_program_' + ('error' if result['error'] else 'returned')
    return result, sim, dict(new_checks=sim.checks - before, restored_removed_count=len(result['actions']),
                             restore_changed_state=bool(restores and restores[-1]['state_key_before'] != restores[-1]['state_key_after']),
                             program='RESUME_PROGRAM (fixed, not model-generated)')


SCENARIOS = dict(a_v6_repro=a_v6_repro, b_v6_repro=b_v6_repro,
                 a_v7=lambda: _v7('asap_05954', 'A'), b_v7=lambda: _v7('asap_05954', 'B'),
                 c_v7=lambda: _v7('asap_06444', 'C'), b_resume_probe=b_resume_probe)


def run(name):
    started = time.monotonic()
    result, sim, extra = SCENARIOS[name]()
    summary = dict(scenario=name, utc=utc(), wall_seconds=time.monotonic() - started, **summarize(result, sim), **extra,
                   scope='Offline regression on a known v6 CAD; preserved responses replayed; not a first encounter.')
    folder = OUT / name
    write(folder / 'summary.json', summary)
    keep = {k: v for k, v in result.items() if k not in ('initial_observation', 'observation')}
    keep['replay_log'] = sim.replay_log
    write(folder / 'result.json', keep)
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument('scenarios', nargs='+', choices=sorted(SCENARIOS))
    a = p.parse_args()
    for s in a.scenarios:
        r = run(s)
        print({k: r[k] for k in ('scenario', 'success', 'termination', 'final_removed', 'best_removed', 'checks',
                                  'accepted_edge_reentries', 'guarded_requests', 'llm_calls', 'wall_seconds')}, flush=True)


if __name__ == '__main__':
    main()

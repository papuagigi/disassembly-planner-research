"""Predeclared live B/C contract smoke on prior failures, before test generation."""
from datetime import datetime, timezone
import hashlib
import json
import time

from disassembly_mujoco.agent import CodexCLIProvider
from .common import ROOT, WORKSPACE, MODEL, EFFORT, LIMITS, CONDITIONS, read, write, prepare, solve, neutral_observation_hash

FIXTURES = [('heldout_02', 'seeded'), ('heldout_03', 'normal')]

def run():
    folder = ROOT/'outputs/development'
    if folder.exists():
        raise FileExistsError('Smoke already started. Retain and audit before separately named repair round.')
    assert not (ROOT/'outputs/input_audit/heldout_cases.json').exists()
    assert read(ROOT/'outputs/transport_validation/final.json')['status'] == 'PASS'
    folder.mkdir(parents=True)
    previous = read(WORKSPACE/'disassembly_abc_v2/outputs/evaluation/manifest.json')
    rows = []
    for case_id, track in FIXTURES:
        case = next(c for c in previous['cases'] if c['case_id'] == case_id)
        shared = prepare(case, track)
        write(folder/case_id/track/'shared_input.json', shared)
        for condition in CONDITIONS[1:]:
            path = folder/case_id/track/condition
            write(path/'started.json', dict(at_utc=datetime.now(timezone.utc).isoformat(), condition=condition))
            provider = CodexCLIProvider(path/'llm_calls', model=MODEL, reasoning_effort=EFFORT, timeout=120)
            start = time.monotonic()
            result = solve(case, condition, provider, shared, bank_path=ROOT/'memory/S5.json')
            result.update(condition=condition, track=track, repeat=1, model=MODEL, reasoning_effort=EFFORT,
                          elapsed_seconds_total=time.monotonic()-start, preparation_checks=shared['state']['checks'])
            write(path/'result.json', result)
            errors = [d.get('execution',{}).get('error') for d in result.get('decisions',[]) if d.get('execution',{}).get('error')]
            row = {k:result.get(k) for k in ['success','termination','checker_calls','llm_calls','execution_steps','bank_execution_steps']}
            row.update(case_id=case_id, condition=condition, track=track, errors=errors,
                       identical_initial_observation=result['initial_observation_sha256']==neutral_observation_hash(shared['observation']),
                       physical_action_executed=result['checker_calls']>shared['state']['checks'])
            rows.append(row)
            print(json.dumps(row), flush=True)
    ready = all(r['identical_initial_observation'] and r['physical_action_executed']
                and not any(e.get('type') in ['WorkerError','FileNotFoundError','ModuleNotFoundError'] for e in r['errors']) for r in rows)
    names = ['code_actor.py','runtime.py','skill_adapter.py','controller.py','memory.py']
    names += [p.name for p in ROOT.glob('*.py') if 'transport' in p.name or 'serial' in p.name]
    names += [p.name for p in ROOT.glob('*.py') if 'frontier' in p.name or 'search_skill' in p.name]
    review = dict(runtime_ready=ready, rows=rows, predeclared_fixtures=FIXTURES,
                  scope='Prior failures are development evidence now. No fresh test OBJ exists. Goal success is descriptive, not a performance admission gate.',
                  model=MODEL, reasoning_effort=EFFORT, limits=LIMITS,
                  source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names})
    write(folder/'final_review.json', review)
    print('runtime_ready='+str(ready), flush=True)

if __name__ == '__main__':
    run()

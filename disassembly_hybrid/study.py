"""Freeze, run and retain every scheduled trial of the three-arm study."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
from .common import MODEL, EFFORT, LIMITS, METHODS, digest, write, prepare_shared, neutral_observation_hash

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent

def read(path):
    return json.loads(Path(path).read_text())

def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_files():
    return sorted([*ROOT.glob('*.py'),
                   *(WORKSPACE/'disassembly_mujoco'/n for n in ['simulator.py','agent.py','runtime.py']),
                   *(WORKSPACE/'disassembly_planner_2d/planner2d'/n for n in ['llm.py','code_runtime.py','code_worker.py','geometry.py'])])

def assets(cases):
    paths = set()
    for case in cases:
        case = Path(case).resolve()
        paths.add(case)
        for p in read(case)['parts']:
            paths.add((case.parent/p['visual_mesh']).resolve())
            paths.update((case.parent/m).resolve() for m in p['collision_meshes'])
    return sorted(paths)

def freeze(output, cases, repetitions=3):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = [Path(p).resolve() for p in cases]
    if len(cases) != len(set(cases)) or repetitions != 3:
        raise ValueError('Distinct cases and three predeclared repetitions required')
    from disassembly_mujoco.agent import validate_library
    library = read(WORKSPACE/'disassembly_mujoco/skill_library.json')
    library_hash = validate_library(library)
    records = []
    for case in cases:
        state, obs, original = prepare_shared(case, LIMITS['max_checks'])
        records.append({'path':str(case), 'id':read(case)['id'], 'sha256':file_hash(case),
                        'initial_observation_sha256':neutral_observation_hash(obs),
                        'initial_graph':obs['directed_blocking_graph'],
                        'common_probe_count':state['checks'],
                        'part_count':len(original['remaining_parts']),
                        'target_id':original['target_id']})
    runtime = {name:importlib.metadata.version(name) for name in ('mujoco','numpy','scipy','trimesh','coacd')}
    manifest = {'created_utc':datetime.now(timezone.utc).isoformat(), 'model':MODEL,'reasoning_effort':EFFORT,
        'limits':LIMITS, 'repetitions':repetitions,'methods':list(METHODS),'cases':records,
        'expected_trials':len(cases)*repetitions*3,
        'library_sha256':library_hash,
        'source_sha256':{str(p):file_hash(p) for p in source_files()},
        'asset_sha256':{str(p):file_hash(p) for p in assets(cases)},
        'input_audit_sha256':{str(p):file_hash(p) for p in (ROOT/'outputs/input_audit').glob('*.json')},
        'runtime':{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'packages':runtime},
        'ordering':'For each case, three repeats rotate A/B/C starting condition, balancing ordinal position.',
        'common_input':'Six target-direction probes executed independently per trial and charged to24. All arms receive same numerical observation and directional graph evidence. No offline reference plans or screening traces are in prompts.',
        'graph':'Observed blockers -> moving part, indexed by full physical state and direction. Unknown actions remain eligible. No universal precedence is inferred from one blocked direction. Updated after feedback.',
        'library':'B uses the original frozen executable recover_target. C uses local recommendation procedures extracted/adapted from the same prior experience, with control retained by fixed DFS. B-C is a system comparison, not a single-factor library ablation.',
        'budget':'Identical primary upper bounds:4 LLM calls,24 physics calls including probes,480s total wall. All arms use1000000 counted planner opcodes as a generous safety bound, not equal FLOPs: A/B count generated policy and skills, C counts controller/graph/skills with bookkeeping. A/B retain original120s per code turn guard. This new study increases the old50000 opcode safeguard for ALL arms before evaluation, because dev-only C bookkeeping incurred a different cost. Model token usage is measured, not forced equal.',
        'failure_policy':'Every scheduled result retained. Budget exhaustion UNKNOWN, not physical impossibility. Provider/worker failures reported separately, no heuristic replacement or silent reruns.',
        'scope':'Actual3D OBJ, sampled six-axis straight extraction and MuJoCo residual stability, assumed physical parameters and fixture. No robot, gripping/force model or physical calibration.',
        'heldout':'Assembly identities absent from prior development/extraction. A feasibility-screened sample, not random population. Freeze precedes all three-arm evaluations. No tuning after results.',
        'sampling':'Model slug/effort fixed; provider backend snapshot/seed/temperature not exposed. Repeats on one CAD are not independent assemblies.'}
    manifest['manifest_sha256']=digest(manifest)
    write(output/'manifest.json',manifest)
    write(output/'library.json',library)
    for p in source_files():
        dst=output/'source_snapshot'/p.relative_to(WORKSPACE)
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,dst)
    print(json.dumps({'phase':'frozen','manifest_sha256':manifest['manifest_sha256'],'expected_trials':manifest['expected_trials']},ensure_ascii=False),flush=True)

def verify_manifest(output):
    m=read(Path(output)/'manifest.json')
    for section in ('source_sha256','asset_sha256','input_audit_sha256'):
        for p, expected in m[section].items():
            if not Path(p).is_file() or file_hash(p)!=expected:
                raise ValueError('Frozen input changed: '+p)
    payload={k:v for k,v in m.items() if k!='manifest_sha256'}
    if digest(payload)!=m['manifest_sha256']:
        raise ValueError('Manifest hash mismatch')
    return m

def worker(output, case_index, repeat, method):
    output=Path(output).resolve(); m=verify_manifest(output)
    case=m['cases'][case_index]; folder=output/'evaluation'/case['id']/f'repeat_{repeat:02d}'/method
    started=time.monotonic()
    write(folder/'started.json',{'utc':datetime.now(timezone.utc).isoformat(),'case':case['id'],'method':method})
    from disassembly_mujoco.agent import CodexCLIProvider
    p=CodexCLIProvider(folder/'llm_calls',model=m['model'],reasoning_effort=m['reasoning_effort'],timeout=120)
    state,obs,raw=prepare_shared(case['path'],m['limits']['max_checks'])
    if neutral_observation_hash(obs)!=case['initial_observation_sha256']:
        raise ValueError('Shared initial observation changed')
    elapsed_preflight=time.monotonic()-started
    limits={**m['limits'],'timeout_seconds':max(.001,m['limits']['timeout_seconds']-elapsed_preflight)}
    if method=='graph_llm_dfs_library':
        from .core import solve_hybrid
        result=solve_hybrid(case['path'],p,initial_state=state,initial_observation=obs,**limits)
    else:
        from .code_actor import solve_code
        library=read(output/'library.json') if method=='code_with_library' else None
        result=solve_code(case['path'],p,library=library,initial_state=state,initial_observation=obs,**limits)
    result.update({'method':method,'repeat':repeat,'case_id':case['id'],
                   'initial_observation_sha256':neutral_observation_hash(obs),
                   'common_probe_count':state['checks'],'common_probe_seconds':elapsed_preflight,
                   'elapsed_seconds_total':time.monotonic()-started,'protocol_sha256':m['manifest_sha256'],
                   'model':m['model'],'reasoning_effort':m['reasoning_effort'],'limits':m['limits']})
    write(folder/'result.json',result)
    print(json.dumps({k:result.get(k) for k in ('case_id','method','repeat','success','termination','checker_calls','llm_calls','execution_steps','backtracks','elapsed_seconds_total')},ensure_ascii=False),flush=True)

def evaluate(output):
    output=Path(output).resolve(); m=verify_manifest(output)
    schedule=[]
    for ci,case in enumerate(m['cases']):
        for rep in range(1,m['repetitions']+1):
            shift=(ci+rep-1)%3; order=list(METHODS[shift:]+METHODS[:shift])
            for method in order:
                schedule.append((ci,rep,method))
    write(output/'schedule.json',[{'case':m['cases'][ci]['id'],'repeat':rep,'method':meth,'ordinal':i+1} for i,(ci,rep,meth) in enumerate(schedule)])
    for ordinal,(ci,rep,method) in enumerate(schedule,1):
        folder=output/'evaluation'/m['cases'][ci]['id']/f'repeat_{rep:02d}'/method
        if (folder/'result.json').exists():
            print(json.dumps({'phase':'retained_existing','ordinal':ordinal,'folder':str(folder)}),flush=True)
            continue
        if (folder/'started.json').exists():
            raise RuntimeError('Interrupted scheduled trial must be audited before resume: '+str(folder))
        cmd=[sys.executable,'-B','-m','disassembly_hybrid.study','worker','--output',str(output),'--case-index',str(ci),'--repeat',str(rep),'--method',method]
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        folder.mkdir(parents=True,exist_ok=True)
        start=time.monotonic()
        proc=subprocess.Popen(cmd,cwd=WORKSPACE,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        timed_out=False
        try:
            stdout,stderr=proc.communicate(timeout=m['limits']['timeout_seconds'])
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(proc.pid,signal.SIGKILL);stdout,stderr=proc.communicate()
        (folder/'worker.stdout').write_text(stdout);(folder/'worker.stderr').write_text(stderr)
        if stdout.strip():print(stdout.strip(),flush=True)
        if not (folder/'result.json').exists():
            write(folder/'result.json',{'case_id':m['cases'][ci]['id'],'method':method,'repeat':rep,
                'success':False,'status':'UNKNOWN','termination':'wall_budget_exhausted' if timed_out else 'worker_error',
                'worker_returncode':proc.returncode,'worker_error':stderr[-4000:],
                'checker_calls':None,'llm_calls':len(list((folder/'llm_calls').glob('call_*'))) if (folder/'llm_calls').exists() else 0,
                'actions':[],'trace':[],'elapsed_seconds_total':time.monotonic()-start,
                'protocol_sha256':m['manifest_sha256'],'limits':m['limits']})
            print(json.dumps({'phase':'worker_failure','ordinal':ordinal,'folder':str(folder),'timed_out':timed_out}),flush=True)
        write(output/'progress.json',{'completed':ordinal,'expected':len(schedule),'latest_result':str(folder/'result.json')})
    verify_manifest(output)
    write(output/'evaluation_complete.json',{'expected_trials':len(schedule),'actual_results':len(list((output/'evaluation').rglob('result.json'))),'manifest_sha256':m['manifest_sha256']})

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','evaluate','worker'])
    p.add_argument('--output',required=True);p.add_argument('--cases',nargs='*',default=[])
    p.add_argument('--case-index',type=int);p.add_argument('--repeat',type=int);p.add_argument('--method',choices=METHODS)
    a=p.parse_args()
    if a.command=='freeze':freeze(a.output,a.cases)
    elif a.command=='evaluate':evaluate(a.output)
    else:worker(a.output,a.case_index,a.repeat,a.method)

if __name__=='__main__':main()

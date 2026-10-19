"""Frozen 2×2 transfer evaluation: append-only outputs and retained failures."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from disassembly_recovery.common import prepare_shared,neutral_observation_hash
from .memory import SkillBank,digest,write
from .discovery import MODEL,EFFORT,LIMITS
ROOT=Path(__file__).resolve().parent;WORKSPACE=ROOT.parent
CONDITIONS=('S0_off','S0_on','S1_off','S1_on')

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
    paths=[ROOT/n for n in ['controller.py','memory.py','discovery.py','learn.py','study.py','data_tools/build_locking_cases.py']]
    old=read(WORKSPACE/'disassembly_recovery/outputs/protocol/actor_freeze.json')['source_sha256']
    return paths+[Path(p)for p in old]

def freeze():
    out=ROOT/'outputs/protocol/freeze.json'
    if out.exists():raise FileExistsError('Already frozen')
    ledger=read(ROOT/'outputs/learning/ledger.json');assert ledger['status']=='complete'
    assert not(ROOT/'outputs/input_audit/heldout_cases.json').exists(),'Generate held-out data only after source freeze'
    m={'created_utc':datetime.now(timezone.utc).isoformat(),'model':MODEL,'reasoning_effort':EFFORT,
        'limits':LIMITS,'conditions':list(CONDITIONS),'repetitions':3,'planned_trials':36,'tracks':['normal'],
        'source_sha256':{str(p.resolve()):sha(p)for p in sources()},
        'banks':{v:{'path':str((ROOT/'memory/banks'/(v+'.json')).resolve()),
            'file_sha256':sha(ROOT/'memory/banks'/(v+'.json')),
            'bank_sha256':SkillBank(ROOT/'memory/banks'/(v+'.json')).sha256}for v in ['S0','S1']},
        'learning_ledger_sha256':sha(ROOT/'outputs/learning/ledger.json'),
        'development_case_index_sha256':sha(ROOT/'outputs/input_audit/development_cases_v2.json'),
        'primary_question':'Does experience-derived validated executable memory transfer to new problems; does online ranking add value?',
        'fairness':'Same controller, graph, retrieval/activation, observations, API and physics. Only frozen bank version and online model ranking vary. Equal resource upper bounds, actual usage measured.',
        'scope':'New designed solid-guide 3D OBJ mechanisms; sampled six-axis straight extraction then MuJoCo gravity/friction residual stability. No robot/grasp/force-driven pull.',
        'evaluation_learning':False,'weights_changed':False,
        'learning_semantics':'Persistent skill banks change between development rounds, then remain frozen across held-out independent repeats.',
        'sampling':'Three designed held-out mechanisms/variants; independent resets are not independent real products.',
        'failure_policy':'Every scheduled trial retained; no retry or substitute path. Budget exhaustion is UNKNOWN, not physical impossibility.',
        'offline_cost_policy':'Discovery, candidate validation, case certification, tests and replay are separate from primary inference cost.'}
    m['manifest_sha256']=digest(m);write(out,m)
    for p in sources():
        q=ROOT/'outputs/protocol/source_snapshot'/p.relative_to(WORKSPACE);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
    print(json.dumps({'freeze':str(out),'file_sha256':sha(out),'manifest_sha256':m['manifest_sha256']}),flush=True)

def verify_frozen():
    m=read(ROOT/'outputs/protocol/freeze.json')
    assert digest({k:v for k,v in m.items()if k!='manifest_sha256'})==m['manifest_sha256']
    for p,h in m['source_sha256'].items():assert sha(p)==h,('Frozen source changed',p)
    for row in m['banks'].values():assert sha(row['path'])==row['file_sha256'];assert SkillBank(row['path']).sha256==row['bank_sha256']
    assert sha(ROOT/'outputs/learning/ledger.json')==m['learning_ledger_sha256']
    return m

def prepare():
    frozen=verify_frozen();out=ROOT/'outputs/evaluation/manifest.json'
    if out.exists():raise FileExistsError('Evaluation already prepared')
    index=read(ROOT/'outputs/input_audit/heldout_cases.json');cases=[];assets={}
    assert len(index['cases'])==3
    for row in index['cases']:
        case=Path(row['case_path']);raw=read(case);paths={case}
        for part in raw['parts']:
            paths.add((case.parent/part['visual_mesh']).resolve())
            paths.update((case.parent/p).resolve()for p in part['collision_meshes'])
        assets.update({str(p):sha(p)for p in paths})
        state,obs,reg=prepare_shared(case,max_checks=LIMITS['max_checks'])
        path=ROOT/'outputs/evaluation/shared_inputs'/row['case_id']/'normal.json'
        write(path,{'state':state,'observation':obs,'recovery_state':reg})
        cases.append({**row,'tracks':{'normal':{'path':str(path.resolve()),'sha256':sha(path),
            'observation_sha256':neutral_observation_hash(obs),'preparation_checks':state['checks']}}})
    m={**frozen,'cases':cases,'asset_sha256':assets,'freeze_file_sha256':sha(ROOT/'outputs/protocol/freeze.json'),
        'case_selection_sha256':sha(ROOT/'outputs/input_audit/heldout_cases.json'),
        'runtime':{n:importlib.metadata.version(n)for n in ['mujoco','numpy','scipy','trimesh']}}
    m.pop('manifest_sha256');m['manifest_sha256']=digest(m);write(out,m)
    print(json.dumps({'prepared_cases':len(cases),'planned_trials':m['planned_trials'],'manifest_sha256':m['manifest_sha256']}),flush=True)

def manifest():
    verify_frozen();m=read(ROOT/'outputs/evaluation/manifest.json')
    assert digest({k:v for k,v in m.items()if k!='manifest_sha256'})==m['manifest_sha256']
    for p,h in m['asset_sha256'].items():assert sha(p)==h,('Frozen asset changed',p)
    for c in m['cases']:
        for row in c['tracks'].values():assert sha(row['path'])==row['sha256']
    return m

def worker(case_index,repeat,condition):
    from .controller import solve
    from disassembly_mujoco.agent import CodexCLIProvider
    m=manifest();case=m['cases'][case_index];rank=condition.endswith('_on');bank=condition.split('_')[0]
    folder=ROOT/'outputs/evaluation/trials'/case['case_id']/('repeat_%02d'%repeat)/condition
    write(folder/'started.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'condition':condition})
    data=read(case['tracks']['normal']['path']);started=time.monotonic()
    provider=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)if rank else None
    r=solve(case['case_path'],provider,SkillBank(m['banks'][bank]['path']),llm_rank=rank,
        initial_state=data['state'],initial_observation=data['observation'],recovery_state=data['recovery_state'],**m['limits'])
    r.update(condition=condition,bank_version=bank,repeat=repeat,track='normal',model=MODEL,reasoning_effort=EFFORT,
        protocol_sha256=m['manifest_sha256'],preparation_checks=data['state']['checks'],
        minimum_removals=case['reference']['minimum_removals'],elapsed_seconds_total=time.monotonic()-started,
        initial_observation_sha256=neutral_observation_hash(data['observation']))
    r['learning_retrievals']=r['retrievals'];write(folder/'result.json',r)
    print(json.dumps({k:r.get(k)for k in ['case_id','condition','repeat','success','termination','checker_calls','llm_calls','elapsed_seconds_total']}),flush=True)

def evaluate():
    m=manifest();schedule=[]
    for i,c in enumerate(m['cases']):
        for repeat in range(1,4):
            offset=(i+repeat-1)%4
            for condition in CONDITIONS[offset:]+CONDITIONS[:offset]:
                schedule.append({'ordinal':len(schedule)+1,'case_index':i,'repeat':repeat,'condition':condition})
    write(ROOT/'outputs/evaluation/schedule.json',schedule)
    for job in schedule:
        c=m['cases'][job['case_index']];folder=ROOT/'outputs/evaluation/trials'/c['case_id']/('repeat_%02d'%job['repeat'])/job['condition']
        if(folder/'result.json').exists():continue
        if(folder/'started.json').exists():raise RuntimeError('Interrupted trial requires explicit audit: '+str(folder))
        folder.mkdir(parents=True,exist_ok=True)
        command=[sys.executable,'-B','-m','disassembly_learning_v1.study','worker','--case-index',str(job['case_index']),
                 '--repeat',str(job['repeat']),'--condition',job['condition']]
        start=time.monotonic();proc=subprocess.Popen(command,cwd=WORKSPACE,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        timeout=False
        try:out,err=proc.communicate(timeout=m['limits']['timeout_seconds']+10)
        except subprocess.TimeoutExpired:timeout=True;os.killpg(proc.pid,signal.SIGKILL);out,err=proc.communicate()
        (folder/'worker.stdout').write_text(out);(folder/'worker.stderr').write_text(err)
        if out.strip():print(out.strip(),flush=True)
        if not(folder/'result.json').exists():
            write(folder/'result.json',dict(case_id=c['case_id'],case_path=c['case_path'],condition=job['condition'],
                bank_version=job['condition'].split('_')[0],bank_sha256=m['banks'][job['condition'].split('_')[0]]['bank_sha256'],
                llm_rank=job['condition'].endswith('_on'),model=MODEL,reasoning_effort=EFFORT,repeat=job['repeat'],
                track='normal',protocol_sha256=m['manifest_sha256'],success=False,
                termination='wall_budget_exhausted'if timeout else'worker_error',error=err[-3000:],checker_calls=None,
                llm_calls=len(list((folder/'llm_calls').glob('call_*'))),trace=[],actions=[],
                elapsed_seconds_total=time.monotonic()-start,preparation_checks=c['tracks']['normal']['preparation_checks']))
        write(ROOT/'outputs/evaluation/progress.json',{'completed':job['ordinal'],'expected':len(schedule)})
    manifest();write(ROOT/'outputs/evaluation/complete.json',{'trials':len(schedule),'source_verification':'PASS'})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','prepare','evaluate','worker'])
    p.add_argument('--case-index',type=int);p.add_argument('--repeat',type=int);p.add_argument('--condition',choices=CONDITIONS)
    a=p.parse_args()
    if a.command=='freeze':freeze()
    elif a.command=='prepare':prepare()
    elif a.command=='evaluate':evaluate()
    else:worker(a.case_index,a.repeat,a.condition)

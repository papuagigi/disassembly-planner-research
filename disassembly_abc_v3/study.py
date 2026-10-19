"""Append-only matched A/B/C evaluation; no test-time memory acquisition."""
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

from .common import ROOT,WORKSPACE,MODEL,EFFORT,LIMITS,CONDITIONS,prepare as shared_prepare
from .common import read,write,digest,neutral_observation_hash,solve
from .memory import SkillBank

TRACK_REPEATS={'seeded':2,'normal':2}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    own=list(ROOT.glob('*.py'))+list((ROOT/'data_tools').glob('*.py'))
    old=read(WORKSPACE/'disassembly_abc_v2/outputs/protocol/freeze.json')['source_sha256']
    return sorted(set(own+[Path(p) for p in old]),key=str)


def progress(phase,**details):
    value=dict(owner='Codex',claude_assigned=False,phase=phase,
               updated_utc=datetime.now(timezone.utc).isoformat(),**details)
    write(ROOT/'outputs/progress.json',value)
    with(ROOT/'outputs/journal.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')


def freeze():
    path=ROOT/'outputs/protocol/freeze.json'
    if path.exists():raise FileExistsError('Already frozen')
    assert not(ROOT/'outputs/input_audit/heldout_cases.json').exists()
    validation=read(ROOT/'outputs/transport_validation/final.json')
    assert validation['status']=='PASS', 'Validate exact transport before new test meshes exist'
    chain=read(ROOT/'outputs/transport_validation/development_chain.json')
    assert chain['status']=='PASS' and chain['results']==4, 'Audit complete live development state chains'
    smoke=read(ROOT/'outputs/development/final_review.json')
    assert smoke['runtime_ready'], 'Complete development-only live contract review'
    for name,expected in smoke['source_sha256'].items():
        assert sha(ROOT/name)==expected, ('Actor changed after live development review',name)
    for name,expected in validation['source_sha256'].items():
        assert sha(ROOT/name)==expected, ('Transport changed after validation',name)
    bank=ROOT/'memory/S5.json';origin=WORKSPACE/'disassembly_abc_v2/memory/S5.json'
    assert sha(bank)==sha(origin)==sha(ROOT/'outputs/protocol/library.json')
    value=dict(created_utc=datetime.now(timezone.utc).isoformat(),model=MODEL,reasoning_effort=EFFORT,
        conditions=list(CONDITIONS),limits=LIMITS,track_repetitions=TRACK_REPEATS,
        tracks=list(TRACK_REPEATS),planned_trials=36,
        source_sha256={str(p.resolve()):sha(p) for p in sources()},
        banks={'S5':dict(path=str(bank.resolve()),file_sha256=sha(bank),bank_sha256=SkillBank(bank).sha256)},
        bank_origin=dict(path=str(origin.resolve()),file_sha256=sha(origin),previous_version='S5',version='S5',
                         same_exact_source_and_bank_for_B_C=True,previous_skill_records_retained=True),
        library_snapshot_sha256=sha(ROOT/'outputs/protocol/library.json'),
        geometry_catalog_sha256=sha(ROOT/'outputs/input_audit/pre_freeze_geometry_catalog.json'),
        development_review_sha256=sha(ROOT/'outputs/development/final_review.json'),
        transport_validation_sha256=sha(ROOT/'outputs/transport_validation/final.json'),
        development_chain_sha256=sha(ROOT/'outputs/transport_validation/development_chain.json'),
        development_environment_retry_sha256=sha(ROOT/'outputs/development_environment_retry.json'),
        change='Lossless bounded semantic skill-state transport; logging summaries remain separate. No skill-source retraining, weight change or cap increase.',
        skill_stage_limits=dict(base_or_learned_opcodes=150000,wall_seconds=0.3,aggregate_max_steps=LIMITS['max_steps']),
        primary_question='How should LLM code generation, reusable procedures and fixed graph/DFS divide planning work?',
        comparison='A vs B changes library access; B vs C changes control ownership, filtering, ranking and activation together. Systems comparison, not one isolated algorithm effect.',
        condition_contract={
            CONDITIONS[0]:'LLM-generated restricted Python owns search/API calls; no bank binding or reusable source.',
            CONDITIONS[1]:'LLM-generated restricted Python may explicitly call same S5 next_step; generated policy dispatches physical operations.',
            CONDITIONS[2]:'Fixed graph/DFS with online LLM priorities calls identical S5 and shared physical API.'},
        fairness='Same per-case/start physical state, observation, recovery registry, OBJ, SharedAPI, gravity/friction, model/effort and all upper limits. Actual calls/tokens/runtime differ.',
        execution_accounting='Generated policy or fixed controller plus executable S5 stages counted. Trusted serialization/physical glue excluded equally from opcode metric but included in elapsed time. Not equal FLOPs.',
        inference_environment='Live isolated tool-disabled Codex CLI; explicit model/effort; backend seed/snapshot not exposed.',
        preparation='normal: fully assembled plus6target probes. seeded:2useful removals/checkpoints, one accepted wrong support removal,6probes. Costs charged equally; no semantic role labels supplied.',
        evaluation_learning=False,weights_changed=False,
        memory_policy='Same S5 bank as prior study, frozen; episode-local runtime memory persists within episode but resets between independent repeats.',
        repetition_policy='Reset physical state, costs, checkpoints, model context and runtime ledger; repeats are inference replication, not cumulative learning.',
        scope='Fresh parameter variants of a self-designed industrial-inspired bearing-service fixture with dynamic product members and explicitly anchored environment fixtures. Not manufacturer CAD, threaded fastener dynamics, calibrated industrial validation or robot control.',
        sampling='Three designed related variants, not three independent industrial products. Normal/seeded tracked separately.',
        failure_policy='Every scheduled outcome retained, including provider/code/budget failures; no score-driven retries, exclusions or reference substitutions.',
        offline_cost_policy='Development, certification, long-memory tests, audit and replay are separate from scored evaluation costs.')
    value['manifest_sha256']=digest(value);write(path,value)
    for p in sources():
        dst=ROOT/'outputs/protocol/source_snapshot'/p.relative_to(WORKSPACE)
        dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(p.read_bytes())
    progress('frozen_before_heldout',freeze_file_sha256=sha(path),evaluation_started=False)
    print(json.dumps({'freeze_sha256':sha(path),'manifest_sha256':value['manifest_sha256'],'sources':len(sources())}),flush=True)


def verify_frozen():
    m=read(ROOT/'outputs/protocol/freeze.json')
    assert digest({k:v for k,v in m.items() if k!='manifest_sha256'})==m['manifest_sha256']
    for p,h in m['source_sha256'].items():assert sha(p)==h,('Frozen source changed',p)
    for bank in m['banks'].values():
        assert sha(bank['path'])==bank['file_sha256']
        assert SkillBank(bank['path']).sha256==bank['bank_sha256']
    assert sha(ROOT/'outputs/protocol/library.json')==m['library_snapshot_sha256']
    assert sha(m['bank_origin']['path'])==m['bank_origin']['file_sha256']
    assert sha(ROOT/'outputs/transport_validation/final.json')==m['transport_validation_sha256']
    assert sha(ROOT/'outputs/transport_validation/development_chain.json')==m['development_chain_sha256']
    assert sha(ROOT/'outputs/development_environment_retry.json')==m['development_environment_retry_sha256']
    assert sha(ROOT/'outputs/development/final_review.json')==m['development_review_sha256']
    assert sha(ROOT/'outputs/input_audit/pre_freeze_geometry_catalog.json')==m['geometry_catalog_sha256']
    return m


def prepare():
    frozen=verify_frozen();out=ROOT/'outputs/evaluation/manifest.json'
    if out.exists():raise FileExistsError('Already prepared')
    index=read(ROOT/'outputs/input_audit/heldout_cases.json');cases=[];assets={}
    assert len(index['cases'])==3 and all(c['accepted'] for c in index['cases'])
    for case in index['cases']:
        path=Path(case['case_path']);raw=read(path);paths={path}
        for part in raw['parts']:
            paths.add((path.parent/part['visual_mesh']).resolve())
            paths.update((path.parent/q).resolve() for q in part['collision_meshes'])
        assets.update({str(q):sha(q) for q in paths});tracks={}
        for track in TRACK_REPEATS:
            shared=shared_prepare(case,track);dst=ROOT/'outputs/evaluation/shared_inputs'/case['case_id']/(track+'.json')
            write(dst,shared);tracks[track]=dict(path=str(dst.resolve()),sha256=sha(dst),
                observation_sha256=neutral_observation_hash(shared['observation']),preparation_checks=shared['state']['checks'])
        cases.append({**case,'tracks':tracks})
    m={**frozen,'cases':cases,'asset_sha256':assets,'freeze_file_sha256':sha(ROOT/'outputs/protocol/freeze.json'),
       'case_selection_sha256':sha(ROOT/'outputs/input_audit/heldout_cases.json'),
       'runtime':{n:importlib.metadata.version(n) for n in ['mujoco','numpy','scipy','trimesh']}}
    m.pop('manifest_sha256');m['manifest_sha256']=digest(m);write(out,m)
    print(json.dumps({'cases':len(cases),'trials':36,'manifest_sha256':m['manifest_sha256']}),flush=True)


def manifest():
    verify_frozen();m=read(ROOT/'outputs/evaluation/manifest.json')
    assert digest({k:v for k,v in m.items() if k!='manifest_sha256'})==m['manifest_sha256']
    for p,h in m['asset_sha256'].items():assert sha(p)==h,('Frozen asset changed',p)
    for c in m['cases']:
        for t in c['tracks'].values():assert sha(t['path'])==t['sha256']
    return m


def worker(case_index,repeat,condition,track):
    from disassembly_mujoco.agent import CodexCLIProvider
    m=manifest();case=m['cases'][case_index]
    folder=ROOT/'outputs/evaluation/trials'/case['case_id']/track/('repeat_%02d'%repeat)/condition
    if(folder/'started.json').exists():raise FileExistsError('Trial already started')
    write(folder/'started.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'condition':condition})
    shared=read(case['tracks'][track]['path']);start=time.monotonic()
    provider=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    result=solve(case,condition,provider,shared,bank_path=m['banks']['S5']['path'])
    result.update(case_id=case['case_id'],case_path=case['case_path'],condition=condition,method=condition,
        track=track,repeat=repeat,model=MODEL,reasoning_effort=EFFORT,limits=m['limits'],
        protocol_sha256=m['manifest_sha256'],initial_observation_sha256=neutral_observation_hash(shared['observation']),
        preparation_checks=shared['state']['checks'],elapsed_seconds_total=time.monotonic()-start,
        minimum_removals=case['reference'].get('minimum_removals'),
        library_available=condition!='A_code_no_library',
        bank_version='S5' if condition!='A_code_no_library' else None,
        bank_sha256=m['banks']['S5']['bank_sha256'] if condition!='A_code_no_library' else None)
    write(folder/'result.json',result)
    print(json.dumps({k:result.get(k) for k in ['case_id','track','repeat','condition','success','termination','checker_calls','llm_calls','elapsed_seconds_total']}),flush=True)


def evaluate():
    m=manifest();schedule=[]
    for ti,(track,repeats) in enumerate(TRACK_REPEATS.items()):
        for i,case in enumerate(m['cases']):
            for repeat in range(1,repeats+1):
                offset=(i+repeat+ti-1)%len(CONDITIONS)
                for condition in CONDITIONS[offset:]+CONDITIONS[:offset]:
                    schedule.append(dict(ordinal=len(schedule)+1,case_index=i,repeat=repeat,condition=condition,track=track))
    schedule_path=ROOT/'outputs/evaluation/schedule.json'
    if schedule_path.exists():assert read(schedule_path)==schedule
    else:write(schedule_path,schedule)
    for job in schedule:
        case=m['cases'][job['case_index']]
        folder=ROOT/'outputs/evaluation/trials'/case['case_id']/job['track']/('repeat_%02d'%job['repeat'])/job['condition']
        if(folder/'result.json').exists():continue
        if(folder/'started.json').exists():raise RuntimeError('Interrupted trial requires explicit audit: '+str(folder))
        folder.mkdir(parents=True,exist_ok=True)
        cmd=[sys.executable,'-B','-m','disassembly_abc_v3.study','worker','--case-index',str(job['case_index']),
             '--repeat',str(job['repeat']),'--condition',job['condition'],'--track',job['track']]
        start=time.monotonic();proc=subprocess.Popen(cmd,cwd=WORKSPACE,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        timeout=False
        try:out,err=proc.communicate(timeout=LIMITS['timeout_seconds']+10)
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(proc.pid,signal.SIGKILL);out,err=proc.communicate()
        (folder/'worker.stdout').write_text(out);(folder/'worker.stderr').write_text(err)
        if out.strip():print(out.strip(),flush=True)
        if not(folder/'result.json').exists():
            write(folder/'result.json',dict(case_id=case['case_id'],case_path=case['case_path'],
                condition=job['condition'],method=job['condition'],track=job['track'],repeat=job['repeat'],
                model=MODEL,reasoning_effort=EFFORT,limits=LIMITS,protocol_sha256=m['manifest_sha256'],success=False,
                termination='outer_wall_budget_exhausted' if timeout else 'worker_error',error=err[-3000:],
                trace=[],actions=[],checker_calls=None,llm_calls=len(list((folder/'llm_calls').glob('call_*'))),
                preparation_checks=case['tracks'][job['track']]['preparation_checks'],
                elapsed_seconds_total=time.monotonic()-start,library_available=job['condition']!='A_code_no_library',
                bank_version='S5' if job['condition']!='A_code_no_library' else None,
                bank_sha256=m['banks']['S5']['bank_sha256'] if job['condition']!='A_code_no_library' else None))
        write(ROOT/'outputs/evaluation/progress.json',{'completed':job['ordinal'],'expected':len(schedule)})
        progress('evaluation',completed=job['ordinal'],expected=len(schedule),latest_result=str(folder/'result.json'))
    manifest();write(ROOT/'outputs/evaluation/complete.json',{'trials':len(schedule),'source_verification':'PASS'})
    progress('evaluation_complete',completed=len(schedule),expected=len(schedule),next='Replay and independent analysis')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','prepare','evaluate','worker'])
    p.add_argument('--case-index',type=int);p.add_argument('--repeat',type=int)
    p.add_argument('--condition',choices=CONDITIONS);p.add_argument('--track',choices=list(TRACK_REPEATS));a=p.parse_args()
    if a.command=='freeze':freeze()
    elif a.command=='prepare':prepare()
    elif a.command=='evaluate':evaluate()
    else:worker(a.case_index,a.repeat,a.condition,a.track)

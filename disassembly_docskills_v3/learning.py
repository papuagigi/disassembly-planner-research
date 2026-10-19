"""Learn one physical-procedure document from new CAD failures;validate separately."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import time
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress
from .contracts import MODEL,EFFORT,CODE_SPEC,API_NOTES,DEV_LIMITS
from .documents import materialize,make_bank
from disassembly_real_v3.simulator import FullDisassemblySim
from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_real_v3 import runtime
from .evidence_replay import replay_result

DIRECTIONS=['+x','-x','+y','-y','+z','-z']

def public_result(sim,api,case,limits,started,**extra):
    return dict(case_id=case['case_id'],case_path=case['case_path'],limits=limits,
        state=sim.export_state(),recovery_state=api.export_recovery_state(),trace=sim.trace,actions=sim.actions,
        checker_calls=sim.checks,elapsed_seconds=time.monotonic()-started,
        max_rss_bytes_observed=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)),
        success=bool(sim.success),**sim.task_progress(),**extra)

def collect(case):
    folder=ROOT/'outputs/development/collection'/case['case_id'];folder.mkdir(parents=True,exist_ok=True)
    final=folder/'result.json'
    if final.exists():return read(final)
    if (folder/'progress.json').exists():
        retained=read(folder/'progress.json')
        retained.update(error=dict(type='InterruptedCollector',message='Retained already observed physical failures;no silent restart'),interrupted_collection=True)
        write(final,retained,exclusive=True);return retained
    limits={**DEV_LIMITS,'max_checks':36,'timeout_seconds':120.}
    shared=read(case['shared_path']);started=time.monotonic()
    sim=FullDisassemblySim(case['case_path'],max_checks=36,state=shared['state'])
    api=SharedAPI(sim,recovery_state=shared['recovery_state'],max_checks=36)
    initial=api.snapshot();root=api.checkpoints()[0]['handle'];failures=[];valid=[];pairs=[];seed_paths={};error=None
    def persist():
        value=public_result(sim,api,case,limits,started,initial_observation=initial,
            failures=failures,valid_queries=valid,repair_pairs=pairs,seeds=seed_paths,error=error,
            collector='Fixed generic query probes,not an evaluated learned planner',llm_calls=0)
        write(folder/'progress.json',value);return value
    def query(part,direction,commit=False):
        if sim.checks>=36 or time.monotonic()-started>=120:raise TimeoutError('development collection budget')
        result=(api.remove if commit else api.check)(part,direction)
        if not result['valid']:
            failures.append(copy.deepcopy(result));index=result['checker_call']
            path=folder/'failure_states'/f'{index:03d}.json'
            seed=dict(state=sim.export_state(),recovery_state=api.export_recovery_state(),observation=api.snapshot())
            write(path,seed,exclusive=True);seed_paths[str(index)]=str(path)
        else:valid.append(copy.deepcopy(result))
        persist();return result
    def deadline(sig,frame):raise TimeoutError('development collection wall limit')
    old=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,120)
    try:
        movable=[p['id'] for p in initial['remaining_parts'] if not p['fixed']]
        # Probe a small,deterministic prefix;all actions are validator queries.
        for part in movable[:4]:
            for direction in DIRECTIONS:query(part,direction)
        for bad in failures:
            for good in valid:
                if good['part_id']==bad['part_id'] and good['direction']!=bad['direction'] and good['physical_state_key_before']==bad['physical_state_key_before'] and bad['reason']=='path_collision':
                    pairs.append(dict(kind='alternative_direction',original_failure=bad['checker_call'],
                        target=bad['part_id'],rejected_direction=bad['direction'],accepted_direction=good['direction'],
                        failure_seed=seed_paths[str(bad['checker_call'])],evidence_check=good['checker_call']))
                    break
        # Also seek changed-geometry repairs. These measured future actions stay
        # withheld from independent validators,who receive only the earlier seed.
        root_failures=list(failures);root_valid=list(valid)
        for bad in root_failures[:3]:
            if sim.checks>32:break
            other=next((g for g in root_valid if g['part_id']!=bad['part_id']),None)
            if not other:break
            accepted=query(other['part_id'],other['direction'],True)
            if accepted['valid']:
                retry=query(bad['part_id'],bad['direction'])
                if retry['valid']:
                    pairs.append(dict(kind='changed_geometry',original_failure=bad['checker_call'],
                        target=bad['part_id'],rejected_direction=bad['direction'],removed_other=other['part_id'],
                        evidence_check=retry['checker_call'],failure_seed=seed_paths[str(bad['checker_call'])]))
            api.restore(root);persist()
    except BaseException as exc:
        if isinstance(exc,(KeyboardInterrupt,SystemExit)):raise
        error=dict(type=type(exc).__name__,message=str(exc))
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
    value=persist();write(final,value,exclusive=True)
    audit,_,_=replay_result(final,shared_path=case['shared_path'],allow_incomplete=True);write(folder/'replay_audit.json',audit,exclusive=True)
    return value

def collect_job(case):
        folder=ROOT/'outputs/development/collection'/case['case_id'];folder.mkdir(parents=True,exist_ok=True)
        result_path=folder/'result.json'
        if not result_path.exists():
            log=folder/('worker_'+str(len(list(folder.glob('worker_*.log')))+1)+'.log')
            with log.open('x') as f:
                proc=subprocess.Popen([sys.executable,'-B','-m','disassembly_docskills_v3.learning','collect_one',case['case_id']],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
                try:rc=proc.wait(timeout=300)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL);rc=proc.wait()
            if not result_path.exists():
                if (folder/'progress.json').exists():
                    retained=read(folder/'progress.json');retained.update(error=dict(type='InterruptedCollector',message='Worker interrupted;observed prefix retained'),interrupted_collection=True)
                    write(result_path,retained,exclusive=True)
                else:raise RuntimeError('Development collector failed before any recorded evidence;inspect '+str(log))
        result=read(result_path)
        audit_path=folder/'replay_audit.json'
        if not audit_path.exists():
            audit,_,_=replay_result(result_path,shared_path=case['shared_path'],allow_incomplete=True);write(audit_path,audit,exclusive=True)
        return dict(case=case,result_path=str(result_path),sha256=sha(result_path),
            failure_count=len(result['failures']),repair_pairs=len(result['repair_pairs']),
            observed_query_count=len(result['trace']))

def collect_run():
    index=ROOT/'outputs/development/collection_index.json'
    if index.exists():return read(index)
    selected=read(ROOT/'outputs/input_audit/selected_development.json');rows=[]
    discovery_ids={c['case_id'] for c in selected['discovery_cases']}
    # Independent development probes may run in parallel. The selected cohort
    # and discovery/validation roles are already fixed; final episodes are serial.
    with ThreadPoolExecutor(max_workers=4) as executor:
        for row in executor.map(collect_job,selected['cases']):
            row['role']='discovery' if row['case']['case_id'] in discovery_ids else 'validation';rows.append(row)
            progress('collecting_physical_failures',case=row['case']['case_id'],completed=len(rows),total=len(selected['cases']))
    write(index,dict(utc=utc(),cases=rows),exclusive=True)

PROPOSAL_SCHEMA={'type':'object','properties':{
    'name':{'type':'string'},'description':{'type':'string'},'markdown_body':{'type':'string'},
    'evidence_patterns':{'type':'array','items':{'type':'string'}}},
    'required':['name','description','markdown_body','evidence_patterns'],'additionalProperties':False}

def propose():
    folder=ROOT/'outputs/development/new_document';folder.mkdir(parents=True,exist_ok=True)
    final=folder/'proposal.json'
    if final.exists():return read(final)
    rows=read(ROOT/'outputs/development/collection_index.json')['cases'];evidence=[]
    for i,row in enumerate(r for r in rows if r['role']=='discovery'):
        d=read(row['result_path'])
        fields=['checker_call','part_id','direction','valid','committed','reason','blockers','remaining_before','remaining_after']
        traces=[]
        selected_failures=[]
        for reason in ['path_collision','unstable_remainder']:
            record=next((r for r in d['failures'] if r['reason']==reason),None)
            if record:selected_failures.append(record)
        for record in d['failures']:
            if len(selected_failures)>=4:break
            if all(record['checker_call']!=r['checker_call'] for r in selected_failures):selected_failures.append(record)
        for t in selected_failures+d['valid_queries'][:2]:
            item={k:t.get(k) for k in fields};st=t.get('stability') or {}
            item['stability']={k:st.get(k) for k in ['stable','unstable_parts','max_displacement_m','max_rotation_deg']};traces.append(item)
        evidence.append(dict(evidence_id=f'D{i+1:02d}',source_result_sha256=row['sha256'],part_count=row['case']['part_count'],
            direction_vectors_world=d['initial_observation'].get('direction_vectors_world'),
            observed_queries=traces,measured_repair_pairs=d['repair_pairs'][:2],
            all_observed_failure_reasons=dict(Counter(r['reason'] for r in d['failures'])),
            all_failure_count=len(d['failures']),all_valid_query_count=len(d['valid_queries'])))
    ep=folder/'discovery_evidence.json'
    if ep.exists():assert read(ep)==dict(cases=evidence)
    else:write(ep,dict(cases=evidence),exclusive=True)
    previous=(ROOT/'memory/physical_procedure_verified/physical-disassembly-failure-repair/SKILL.md').read_text()
    prompt='''Write one portable LLM-readable SKILL.md procedural document learned ONLY from these measured physical CAD disassembly failures and repairs. No tools,files,browsing or execution. Output the schema JSON. The new name must differ from physical-disassembly-failure-repair. Do not output exact CAD IDs,five-digit identifiers,answer sequences,Python programs or API-format repair advice. Ground each physical rule in evidence IDs D01 etc. Keep it under6000characters. Include purpose,triggers,diagnosis,numbered executable-by-the-planner steps,expected trusted feedback,non-applicability and evidence limitations. Explain CODE versus GRAPH_DFS application. Every removal still needs validation. Preserve alternatives and exact-state failure memory. Focus on an additional physical procedure actually supported by the data,not a claim of universal success or an API fix. Prior document will be retained separately;do not contradict or duplicate its instructions without observed justification. Do not treat a direction label as world direction. New evaluation cases are not provided.\nPRIOR DOCUMENT:\n'''+previous+'\nDISCOVERY PHYSICAL EVIDENCE:\n'+json.dumps(evidence,ensure_ascii=False)
    from disassembly_mujoco.agent import CodexCLIProvider
    provider=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    response,metadata=provider.complete(prompt,PROPOSAL_SCHEMA,1)
    assert response['name']!='physical-disassembly-failure-repair'
    assert not re.search(r'\b\d{5}\b|asap_\d|```',response['markdown_body'])
    assert len(response['markdown_body'])<=6000
    document=materialize(ROOT/'memory/candidate_v3',response['name'],response['description'],response['markdown_body'])
    result=dict(utc=utc(),document_path=str(document),document_sha256=sha(document),response=response,
        contributing_discovery_CADs=len(evidence),metadata=metadata,no_evaluation_input=True)
    write(final,result,exclusive=True);return result

REPAIR_SCHEMA={'type':'object','properties':{'code':{'type':'string'},'summary':{'type':'string'}},'required':['code','summary'],'additionalProperties':False}

def _validate_one(row,proposal,deadline):
    case=row['case'];folder=ROOT/'outputs/development/document_validation'/case['case_id'];folder.mkdir(parents=True,exist_ok=True)
    final=folder/'admission.json'
    if final.exists():return read(final)
    collection=read(row['result_path']);pairs=collection['repair_pairs']
    if not pairs:
        result=dict(passed=False,case_id=case['case_id'],reason='no independently witnessed bounded repair opportunity',no_model_calls=True)
        write(final,result,exclusive=True);return result
    choice=min(pairs,key=lambda r:r['original_failure']);shared=read(choice['failure_seed'])
    original=next(t for t in shared['state']['trace'] if t['checker_call']==choice['original_failure'])
    # Do not pass choice,pairs,the future good direction,or the collection trace.
    prompt='''You independently verify a physical SKILL.md on a separate development CAD failure. No external tools or files. Generate one short Python program using the supplied API. Goal:stably COMMIT removal of the previously rejected target using the physical document. For path collision you may use a different validated direction or remove a blocker then retry. For instability remove a relevant different body stably before retrying the exact original target/direction. At most6NEWqueries;do not repeat the unchanged rejected query;do not remove fixed parts. The prior failed query has already happened. Use only fields in the public contract. Avoid forbidden names/imports/classes. A successful future sequence is NOT provided. Return code and summary JSON only.\nAPI CONTRACT:\n'''+CODE_SPEC+'\nDOCUMENT:\n'+Path(proposal['document_path']).read_text()+'\nPUBLIC FAILURE:\n'+json.dumps(original,ensure_ascii=False)+'\nPUBLIC OBSERVATION AT FAILURE:\n'+json.dumps(shared['observation'],ensure_ascii=False)
    # Give verifiers the same public datatype/optional-feedback notes as A/B/C;
    # these shared API facts are not learned physical memory.
    prompt=prompt.replace('\nAPI CONTRACT:\n'+CODE_SPEC,'\nAPI CONTRACT:\n'+CODE_SPEC+API_NOTES,1)
    from disassembly_mujoco.agent import CodexCLIProvider
    provider=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=max(.1,deadline-time.monotonic()))
    response,metadata=provider.complete(prompt,REPAIR_SCHEMA,1)
    seed_checks=shared['state']['checks'];limits={**DEV_LIMITS,'max_checks':seed_checks+6,'timeout_seconds':60.,'max_steps':200000}
    sim=FullDisassemblySim(case['case_path'],max_checks=limits['max_checks'],state=shared['state'])
    started=deadline-60.;before_actions=len(sim.actions)
    if time.monotonic()>=deadline:raise TimeoutError('independent repair verifier wall budget')
    payload=dict(code=response['code'],exports=[],library_bank=None,max_checks=limits['max_checks'],max_steps=200000,
        timeout_seconds=max(.1,deadline-time.monotonic()),recovery_state=shared['recovery_state'],max_checkpoints=128,max_restores=256)
    execution=runtime.execute_payload(payload,sim,callback=lambda event:None)
    signal.setitimer(signal.ITIMER_REAL,0) # Replaying recorded evidence is separate from the repair allowance.
    repair_elapsed=time.monotonic()-started
    api=SharedAPI(sim,recovery_state=execution['recovery_state'],max_checks=limits['max_checks'])
    result=public_result(sim,api,case,limits,started,execution_error=execution['error'],initial_observation=shared['observation'])
    rp=folder/'result.json';write(rp,result,exclusive=True)
    audit,_,_=replay_result(rp,shared_path=choice['failure_seed']);write(folder/'replay_audit.json',audit,exclusive=True)
    new_actions=sim.actions[before_actions:];target=original['part_id']
    target_index=next((i for i,a in enumerate(new_actions) if a['part_id']==target),None)
    resolved=target_index is not None
    if original['reason']=='unstable_remainder':
        resolved=resolved and target_index>0 and new_actions[target_index]['direction']==original['direction']
    new_trace=sim.trace[len(shared['state']['trace']):]
    fixed=set(case['fixture_ids']);unsafe=any(t['part_id'] in fixed for t in new_trace)
    repeated=any(t['part_id']==target and t['direction']==original['direction'] and t.get('physical_state_key_before')==original.get('physical_state_key_before') for t in new_trace)
    passed=bool(resolved and not unsafe and not repeated and execution['error'] is None and sim.checks-seed_checks<=6 and repair_elapsed<=60.)
    result=dict(passed=passed,case_id=case['case_id'],original_reason=original['reason'],new_checks=sim.checks-seed_checks,
        repaired_target_committed=bool(resolved),unsafe_fixed_part_attempt=unsafe,repeated_original_unchanged_rejection=repeated,
        execution_error=execution['error'],independent_physical_replay=audit['status'],result_path=str(rp),result_sha256=sha(rp),
        repair_elapsed_seconds=repair_elapsed,
        document_sha256=proposal['document_sha256'],no_future_repair_sequence_supplied=True)
    write(final,result,exclusive=True);return result

def validate_one(row,proposal):
    def expire(sig,frame):raise TimeoutError('independent repair verifier wall budget')
    old=signal.signal(signal.SIGALRM,expire);signal.setitimer(signal.ITIMER_REAL,60.)
    try:return _validate_one(row,proposal,time.monotonic()+60.)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)

def validate_and_freeze():
    complete=ROOT/'outputs/development/complete.json'
    if complete.exists():return read(complete)
    rows=[r for r in read(ROOT/'outputs/development/collection_index.json')['cases'] if r['role']=='validation'];out=[];generation_error=None
    try:proposal=propose()
    except Exception as exc:
        generation_error=repr(exc);proposal=None
    for row in rows if proposal else []:
        progress('validating_new_physical_document',case=row['case']['case_id'],completed=len(out),total=len(rows))
        try:out.append(validate_one(row,proposal))
        except Exception as exc:
            # One failed verifier is negative evidence, not permission to repeat
            # a model call or remove a validation CAD from the denominator.
            final=ROOT/'outputs/development/document_validation'/row['case']['case_id']/'admission.json'
            failure=dict(passed=False,case_id=row['case']['case_id'],reason='verifier error or interrupted attempt',error=repr(exc),document_sha256=proposal['document_sha256'])
            if not final.exists():write(final,failure,exclusive=True)
            out.append(read(final))
    passed=sum(r['passed'] for r in out);required=math.ceil(2*len(out)/3)
    admitted=proposal is not None and len(out)>=6 and passed>=required and not any(r.get('unsafe_fixed_part_attempt') for r in out)
    receipt=dict(status='ADMITTED_BOUNDED_PHYSICAL_PROCEDURE' if admitted else 'REJECTED',utc=utc(),
        validations=out,passed=passed,required=required,required_fraction=2/3,required_independent_CADs_min=6,actual_validation_CADs=len(out),
        document_sha256=proposal['document_sha256'] if proposal else None,generation_error=generation_error,
        scope='Bounded independent physical repair,not full-planner robustness or held-out efficacy',
        no_evaluation_input=True,no_model_weight_updates=True)
    admission=ROOT/'outputs/development/new_document/admission.json'
    if admission.exists():assert read(admission)['document_sha256']==receipt['document_sha256'];receipt=read(admission);admitted=receipt['status']=='ADMITTED_BOUNDED_PHYSICAL_PROCEDURE'
    else:write(admission,receipt,exclusive=True)
    previous=ROOT/'memory/physical_procedure_verified/physical-disassembly-failure-repair/SKILL.md';docs=[previous]
    if admitted:
        p=Path(proposal['document_path']);reference=p.parent/'references/admission.json'
        if reference.exists():assert read(reference)==receipt
        else:write(reference,receipt,exclusive=True)
        docs.append(p)
    from .documents import DocumentBank
    bp=ROOT/'memory/S2.json'
    bank=DocumentBank(bp) if bp.exists() else make_bank(bp,docs,version='S2-expanded-development-v3' if admitted else 'S2-prior-only-new-document-rejected-v3',evidence=str(admission))
    assert sorted(r['sha256'] for r in bank.manifest['skills'])==sorted(sha(p) for p in docs)
    write(complete,dict(utc=utc(),new_document_admitted=admitted,
        actual_new_discovery_CADs=len([r for r in read(ROOT/'outputs/development/collection_index.json')['cases'] if r['role']=='discovery']),
        actual_new_discovery_CADs_with_physical_observations=sum(r['role']=='discovery' and r['observed_query_count']>0 for r in read(ROOT/'outputs/development/collection_index.json')['cases']),
        actual_new_validation_CADs_with_physical_observations=sum(r['role']=='validation' and r['observed_query_count']>0 for r in read(ROOT/'outputs/development/collection_index.json')['cases']),
        actual_new_validation_CADs=len(rows),prior_skill_source_CADs=2,bank_path=str(bank.path),bank_sha256=bank.sha256,
        bank_content_sha256=bank.content_sha256,skills=len(bank.documents)),exclusive=True)
    print(json.dumps(dict(new_document_admitted=admitted,validation_passed=passed,validation_total=len(out),bank_skills=len(bank.documents))),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['collect','collect_one','learn']);p.add_argument('case',nargs='?');a=p.parse_args()
    if a.command=='collect':collect_run()
    elif a.command=='learn':validate_and_freeze()
    else:
        case=next(c for c in read(ROOT/'outputs/input_audit/selected_development.json')['cases'] if c['case_id']==a.case);collect(case)

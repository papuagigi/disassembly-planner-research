"""One failure-derived document proposal and one independent admission pass."""
from collections import Counter
from pathlib import Path
import math
import re
import shutil
from .common import ROOT,read,write,sha,utc,progress
from .contracts import LIMITS,MODEL,EFFORT
from .driver import run
from .documents import DocumentBank,materialize,make_bank
from .metrics import summarize
from .post_evidence import replay_result
from .native_health import audit as audit_native_health
from .scope import study_scope
import fcntl

PROPOSAL_SCHEMA={'type':'object','properties':{'name':{'type':'string'},'description':{'type':'string'},'markdown_body':{'type':'string'}},'required':['name','description','markdown_body'],'additionalProperties':False}

def evidence_indices(trace,events,pairs,maximum=24):
    """Prefer actual late failures/restores over a root-only prompt summary."""
    chosen=[]
    def around(check,radius=1):
        if not trace:return
        j=min(range(len(trace)),key=lambda i:abs(trace[i]['checker_call']-check))
        for i in range(max(0,j-radius),min(len(trace),j+radius+1)):
            if i not in chosen and len(chosen)<maximum:chosen.append(i)
    for p in pairs[:4]:
        around(p['failed_check']);around(p['accepted_check'])
    for e in [e for e in events if e['operation']=='restore'][:4]:around(e['checks_before'],2)
    unstable=[t for t in trace if t.get('reason')=='unstable_remainder']
    for t in unstable[:1]+unstable[-1:]:around(t['checker_call'])
    rejected=[t for t in trace if not t.get('valid')]
    for t in rejected[-2:]+trace[:2]+trace[-3:]:around(t['checker_call'])
    return sorted(chosen)

def repairs(result):
    """Measured later accepted removals; never infer a repair from a declaration."""
    trace=result.get('trace',[]);out=[]
    for i,bad in enumerate(trace):
        if bad.get('valid') or bad.get('reason') not in ('path_collision','unstable_remainder'):continue
        for j in range(i+1,len(trace)):
            good=trace[j]
            if not good.get('committed') or good['part_id']!=bad['part_id']:continue
            changed=good.get('physical_state_key_before')!=bad.get('physical_state_key_before')
            if bad['reason']=='unstable_remainder':
                other=any(t.get('committed') and t['part_id']!=bad['part_id'] for t in trace[i+1:j])
                ok=changed and other and good['direction']==bad['direction']
            else:ok=changed or good['direction']!=bad['direction']
            if ok:
                out.append(dict(failed_check=bad['checker_call'],accepted_check=good['checker_call'],part=bad['part_id'],
                    reason=bad['reason'],old_direction=bad['direction'],new_direction=good['direction'],changed_state=changed))
                break
    return out

def audit_result(folder,case):
    p=folder/'physical_audit.json'
    if p.exists():return read(p)
    audit,_,_=replay_result(folder/'result.json',shared_path=case['shared_path'],allow_incomplete=True)
    write(p,audit,exclusive=True);return audit

def discovery_job(case):
    folder=ROOT/'outputs/development/full_search'/case['case_id']
    return dict(folder=str(folder),case_path=case['case_path'],shared_path=case['shared_path'],architecture='graph_dfs',
        bank_path=str(ROOT/'memory/S2.json'),limits=LIMITS,phase='discovery',arm='C',
        public_task_note='Development experience collection;seek complete disassembly within the stated limits. Do not fabricate a restore or a successful branch.')

def collect():
    lockpath=ROOT/'outputs/development/discovery_collection.lock';lockpath.parent.mkdir(parents=True,exist_ok=True)
    with lockpath.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        return _collect()

def _collect():
    final=ROOT/'outputs/development/discovery_complete.json'
    if final.exists():return read(final)
    cohort=read(ROOT/'outputs/input_audit/selected_development.json');rows=[]
    for case in cohort['discovery_cases']:
        folder=ROOT/'outputs/development/full_search'/case['case_id']
        progress('full_search_learning',case=case['case_id'],completed=len(rows),total=len(cohort['discovery_cases']))
        result=run(discovery_job(case))
        audit=audit_result(folder,case)
        health=audit_native_health(folder)
        rows.append(dict(case=case,result_path=str(folder/'result.json'),sha256=sha(folder/'result.json'),
            metrics=summarize(result),repairs=repairs(result) if health['warning_free_observed'] else [],
            native_engine_health=health,audit=audit['status']))
        from .post_status import checkpoint
        checkpoint()
    value=dict(utc=utc(),cases=rows,full_search_CADs=len(rows),previous_local_probe_discovery_CADs=90,
        reused_discovery_CADs=cohort['reused_discovery_CADs'],new_discovery_CADs=cohort['new_discovery_CADs'],
        unique_discovery_CADs_total=90+cohort['new_discovery_CADs'],
        actual_backtracking_episodes=sum(r['metrics']['restores']>0 for r in rows))
    write(final,value,exclusive=True);return value

def propose():
    folder=ROOT/'outputs/development/new_document';folder.mkdir(parents=True,exist_ok=True)
    final=folder/'proposal.json'
    if final.exists():return read(final)
    attempt=folder/'attempt_started.json'
    if attempt.exists():raise RuntimeError('The single proposal attempt already started without a final proposal;retain failure,do not repeat')
    collection=read(ROOT/'outputs/development/discovery_complete.json');evidence=[]
    fields=['checker_call','part_id','direction','valid','committed','reason','blockers','remaining_before','remaining_after','physical_state_key_before','physical_state_key_after']
    for i,row in enumerate(collection['cases']):
        result=read(row['result_path']);trace=result.get('trace',[]);events=result.get('recovery_state',{}).get('events',[])
        trusted=row['native_engine_health']['warning_free_observed'] and bool(trace)
        indices=evidence_indices(trace,events,row['repairs'])
        evidence.append(dict(evidence_id=f'L{i+1:02}',source_result_sha256=row['sha256'],part_count=row['case']['part_count'],
            native_engine_health=row['native_engine_health']['status'],physical_procedure_evidence_usable=trusted,
            metrics=row['metrics'] if trusted else {'excluded_from_skill_evidence':'Native solver warning;retain raw episode for infrastructure accounting'},
            measured_repairs=row['repairs'][:8] if trusted else [],
            observed_queries=[{k:trace[j].get(k) for k in fields} for j in indices] if trusted else [],
            actual_restore_events=[e for e in events if e['operation']=='restore'][:4] if trusted else []))
    write(folder/'learning_evidence.json',dict(cases=evidence),exclusive=not (folder/'learning_evidence.json').exists())
    bank=DocumentBank(ROOT/'memory/S2.json')
    prompt='''Generate ONE portable physical disassembly procedure as LLM-readable SKILL.md from the measured full-search development evidence below. Output only schema JSON. No tools/files/browsing,Python programs,CAD IDs,answer sequences,or API-format patches. Name must be new. Cite L01... evidence. At most6000characters. Include purpose,observed triggers,numbered planner actions,expected trusted physical feedback,limitations,applicability to generated-code B and fixed Graph/DFS C. Retain prior documents;do not contradict them. Separate observed repair/backtracking from unvalidated hypotheses. Do not claim successful backtracking if none is measured. Failed removal queries do not commit,so they alone do not require checkpoint restoration. Exact-state records survive restoration;do not retry an unchanged known failure. C's fixed DFS controls restore timing;documents only guide ordering. Never invent a hidden support,rotation,grasp,or collision exemption. Every accepted removal requires physical validation. Focus on any additional long-horizon procedure actually supported,not universal disassembly success. All evaluation and independent validation CADs are withheld.\nPRIOR DOCUMENTS:\n'''+str(bank.documents)+'\nMEASURED DEVELOPMENT EVIDENCE:\n'+__import__('json').dumps(evidence,ensure_ascii=False)
    from disassembly_mujoco.agent import CodexCLIProvider
    write(attempt,dict(utc=utc(),one_attempt_only=True),exclusive=True)
    provider=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    response,metadata=provider.complete(prompt,PROPOSAL_SCHEMA,1)
    assert response['name'] not in bank.documents
    assert len(response['markdown_body'])<=6000 and not re.search(r'\basap_|\b\d{5}\b|```',response['markdown_body'])
    document=materialize(ROOT/'memory/candidate',response['name'],response['description'],response['markdown_body'])
    value=dict(document_path=str(document),document_sha256=sha(document),metadata=metadata,utc=utc(),
        attempted_full_search_CADs=len(evidence),contributing_full_search_CADs=sum(e['physical_procedure_evidence_usable'] for e in evidence),
        no_validation_or_test_input=True)
    write(final,value,exclusive=True);return value

def admission_decision(rows,generation_error=None,*,minimum=None):
    if minimum is None:minimum=study_scope()['validation_CADs']
    required=math.ceil(2*len(rows)/3)
    passed=sum(bool(r.get('passed')) for r in rows)
    admitted=generation_error is None and len(rows)>=minimum and passed>=required and all(r.get('physical_audit') in ('PASS','PASS_VERIFIED_PREFIX') for r in rows) and not any(r.get('unsafe_fixed_attempt') or r.get('invalid_restore') or r.get('native_engine_warning_veto') for r in rows)
    return dict(status='ADMITTED_BOUNDED_FULL_SEARCH_PROCEDURE' if admitted else 'REJECTED',passed=passed,required=required,
        actual_validation_CADs=len(rows),validations=rows,generation_error=generation_error,utc=utc(),
        scope='Independent bounded functional/physical repair admission;not causal efficacy or a proof of semantic compliance',no_test_input=True)

def validate_and_freeze_bank():
    complete=ROOT/'outputs/development/complete.json'
    if complete.exists():return read(complete)
    prior=DocumentBank(ROOT/'memory/S2.json');docs=[(prior.path.parent/r['path']).resolve() for r in prior.manifest['skills']]
    proposal=None;error=None
    try:proposal=propose()
    except Exception as exc:error=repr(exc)
    candidate_path=ROOT/'memory/validation.json'
    if proposal and not candidate_path.exists():make_bank(candidate_path,docs+[Path(proposal['document_path'])],version='candidate-unadmitted-v4')
    rows=[]
    cases=read(ROOT/'outputs/input_audit/selected_development.json')['validation_cases']
    for case in cases:
        folder=ROOT/'outputs/development/full_validation'/case['case_id'];receipt=folder/'admission.json'
        if receipt.exists():rows.append(read(receipt));continue
        progress('independent_full_search_validation',case=case['case_id'],completed=len(rows),total=len(cases))
        result=run(dict(folder=str(folder),case_path=case['case_path'],shared_path=case['shared_path'],architecture='code',
            bank_path=str(candidate_path if proposal else prior.path),limits=LIMITS,phase='validation',arm='B'))
        audit=audit_result(folder,case);health=audit_native_health(folder)
        pairs=repairs(result) if health['warning_free_observed'] else []
        unsafe=any(t['part_id'] in set(case['fixture_ids']) for t in result.get('trace',[]))
        invalid_restore=any(e['operation']=='restore' and e.get('status')=='error' for e in result.get('recovery_state',{}).get('events',[]))
        value=dict(case_id=case['case_id'],passed=bool(proposal and health['warning_free_observed'] and (result.get('success') or pairs) and not unsafe and not invalid_restore),
            full_success=bool(result.get('success')),measured_repairs=pairs,unsafe_fixed_attempt=unsafe,invalid_restore=invalid_restore,
            native_engine_warning_veto=not health['warning_free_observed'],native_engine_health=health,
            physical_audit=audit['status'],result_path=str(folder/'result.json'),result_sha256=sha(folder/'result.json'),
            actual_restores=result.get('recovery_state',{}).get('restore_count',0),candidate_was_available=bool(proposal),
            document_sha256=proposal['document_sha256'] if proposal else None)
        write(receipt,value,exclusive=True);rows.append(value)
        from .post_status import checkpoint
        checkpoint()
    admission=admission_decision(rows,error);admission['document_sha256']=proposal['document_sha256'] if proposal else None
    ap=ROOT/'outputs/development/new_document/admission.json'
    if ap.exists():admission=read(ap)
    else:write(ap,admission,exclusive=True)
    if admission['status'].startswith('ADMITTED'):
        p=Path(proposal['document_path'])
        admitted=ROOT/'memory/admitted'/p.parent.name/'SKILL.md'
        admitted.parent.mkdir(parents=True,exist_ok=True)
        if not admitted.exists():shutil.copy2(p,admitted)
        assert sha(admitted)==proposal['document_sha256']
        # Preserve the evaluated validation bank byte-for-byte. Supply only
        # aggregate admission facts to the final LLM,never validation repairs.
        ref=admitted.parent/'references/admission.json'
        if not ref.exists():write(ref,dict(status=admission['status'],passed=admission['passed'],required=admission['required'],
            actual_validation_CADs=admission['actual_validation_CADs'],document_sha256=admission['document_sha256'],
            full_admission_record_sha256=sha(ap),validation_case_answers_not_supplied=True,
            scope=admission['scope']),exclusive=True)
        docs.append(admitted)
    bp=ROOT/'memory/S3.json'
    bank=DocumentBank(bp) if bp.exists() else make_bank(bp,docs,version='S3-final-v4',evidence=str(ap))
    collection=read(ROOT/'outputs/development/discovery_complete.json')
    value=dict(utc=utc(),actual_full_search_discovery_CADs=collection['full_search_CADs'],actual_independent_validation_CADs=len(rows),
        actual_unique_discovery_CADs_including_prior=collection['unique_discovery_CADs_total'],prior_local_probe_discovery_CADs=90,
        new_document_admitted=admission['status'].startswith('ADMITTED'),validation_passes=admission['passed'],
        bank_sha256=bank.sha256,bank_content_sha256=bank.content_sha256,skills=len(bank.documents))
    write(complete,value,exclusive=True);return value

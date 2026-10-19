"""Second, distinct bounded candidate: repair checkpoint-schema/resume failures.

The broad first candidate is preserved as rejected. No final geometry has been
opened. This candidate uses its actual development failure, not test outcomes.
"""
import argparse
import json
from pathlib import Path
from .common import ROOT,read,write,sha,utc,progress
from .documents import materialize,make_bank
from .learning import CASES,MEM,DEV
from .contracts import MODEL,EFFORT,DEV_LIMITS
from .driver import run
from .metrics import summarize
from .evidence_replay import replay_result

BASE=DEV/'checkpoint_candidate'

def propose():
    from disassembly_mujoco.agent import CodexCLIProvider
    origin=DEV/'validation/00804/candidate/result.json';value=read(origin)
    source=dict(origin_path=str(origin),origin_sha256=sha(origin),
        rejection_receipt=str(DEV/'admission.json'),
        execution_errors=[d.get('execution_error') for d in value['decisions'] if d.get('execution_error')],
        faulty_code=value['decisions'][2]['response']['code'],
        observed_checkpoint_metadata=value['observation']['recovery']['checkpoints'],
        observed_history=[{k:t.get(k) for k in ['operation','part_id','direction','valid','reason','committed','physical_state_key_before','physical_state_key_after','remaining_before','remaining_after']} for t in value['trace']],
        confirmed_schema=dict(checkpoints='list[dict]',checkpoint_remaining_parts='list[str] IDs; NOT part dictionaries',
            remaining_parts='snapshot list[dict] part records',current_state_feedback='list[dict] detailed checker records',
            history_feedback='list[dict] compact records; persists across restores/model turns',accepted_action_prefix='list[dict] current committed path',
            checkpoint_accepted_action_prefix='list[dict] historical accepted path when saved'),
        observed_failure='A valid accepted prefix reached a conservative collision dead end; all six directions were rejected. The generated code retried the same six, then treated checkpoint part-ID strings as dicts and raised TypeError. It stopped at3/4 despite a previously independently verified feasible local path. No universal physical impossibility was established.')
    if not (BASE/'failure_evidence.json').exists():write(BASE/'failure_evidence.json',source,exclusive=True)
    old=read(DEV/'admission_criteria.json');old.update(version=2,declared_before_validation=utc(),
        candidate='checkpoint-schema-resume',cases=['00804','00749'],planned_pairs=['new empty bank vs candidate2 on failure origin00804','new empty bank vs candidate2 on different product00749'])
    if not (BASE/'criteria.json').exists():write(BASE/'criteria.json',old,exclusive=True)
    schema={'type':'object','properties':{k:{'type':'string'} for k in ['name','description','body','reasoning']},'required':['name','description','body','reasoning'],'additionalProperties':False}
    prompt='''Create ONE short concrete error-repair SKILL.md from the actual development failure below.
The previous broad document was rejected. This is a distinct checkpoint-schema/resume repair, not an unbounded revision of the broad guide.
Use purpose, applicability/failure signature, cause, actionable procedure, expected feedback, exclusions, evidence, validation and version1.0 sections.
Do NOT return an executable policy or a generic essay about DFS. Explain exact public data shapes that caused TypeError and how to resume without replaying a completed/rejected branch.
CODE architecture: the generated program owns search/frontier; there is no host DFS. It must checkpoint before committing a branch, recover to an actual ancestor of the current accepted prefix, reconstruct ancestor candidates from current part records after restore (checkpoint remaining_parts are only IDs), and retain tried-edge evidence for the exact state. State-local invalid actions do not become global bans.
Only restore after the current branch's legal alternatives are exhausted; never jump to root merely because the focus part is blocked. Preserve completed child-edge bookkeeping when resuming.
GRAPH_DFS architecture: host already owns all this bookkeeping and recovery. Do not generate/replace it; use failure blockers/support feedback only for ranking the offered candidates. The document need not change ranking if evidence is insufficient.
Do not repeat API contract facts unrelated to the actual failure. Do not encode product IDs, exact part IDs or a remembered successful action order. Prefer a concise procedure to complete example code.
Name is a lowercase hyphenated slug <=64 chars. Include a Validation link to references/admission.json, provisional until an ADMITTED receipt exists. No tools.\nEVIDENCE:\n'''+json.dumps(source,ensure_ascii=False)
    provider=CodexCLIProvider(BASE/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    if (BASE/'llm_calls/call_03/response.json').exists():
        response=read(BASE/'llm_calls/call_03/response.json');meta=read(BASE/'llm_calls/call_03/metadata.json')
    else:response,meta=provider.complete(prompt,schema,3)
    # A source evidence file path is required provenance, not a product-specific
    # decision rule. Only the portable procedural sections exclude source IDs.
    import re
    procedure=re.split(r'\n#+ Evidence\b',response['body'],flags=re.I)[0]
    if any(aid in procedure for aid in CASES):raise ValueError('Product identity in portable procedure')
    path=materialize(MEM/'candidates/candidate_02',response['name'],response['description'],response['body'])
    write(BASE/'proposal.json',dict(response=response,metadata=meta,path=str(path),sha256=sha(path)),exclusive=True)
    make_bank(MEM/'candidate2.json',[path],version='candidate-02-provisional',evidence=str(BASE/'criteria.json'))
    progress('second_distinct_document_proposed',first_candidate='REJECTED',new_source='actual development TypeError and failed resumption',no_test_geometry=True)

def validate():
    reports=[]
    for aid in ['00804','00749']:
        values={}
        for version in ['S0','candidate2']:
            folder=BASE/'validation'/aid/version
            result=run(dict(folder=str(folder),case_path=str(CASES[aid]),architecture='code',
                bank_path=str(MEM/(version+'.json')),limits=DEV_LIMITS,phase='development_validation',arm=version,shared_path=None))
            audit_path=folder/'replay_audit.json'
            audit=read(audit_path) if audit_path.exists() else replay_result(folder/'result.json',output=audit_path)[0]
            values[version]=dict(metrics=summarize(result),audit=audit,path=str(folder/'result.json'))
        a=values['S0']['metrics'];b=values['candidate2']['metrics'];result=read(values['candidate2']['path'])
        invalid=[e for e in result['recovery_state']['events'] if e['operation']=='restore' and e.get('status')!='completed']
        passed=bool(b['document_reads'] and b['claimed_skill_ids'] and b['final_progress']>=a['final_progress']
            and (not a['success'] or b['success']) and not b['duplicate_rejected_queries'] and not invalid and values['candidate2']['audit']['status']=='PASS')
        reports.append(dict(source_id=aid,pass_functional_criteria=passed,before=a,after=b,evidence=values))
    triggered=any(r['after']['failed_checks'] for r in reports)
    passed=all(r['pass_functional_criteria'] for r in reports) and triggered
    p=Path(read(BASE/'proposal.json')['path'])
    receipt=dict(status='ADMITTED' if passed else 'REJECTED',created_utc=utc(),document_sha256=sha(p),
        criteria_sha256=sha(BASE/'criteria.json'),failure_evidence_sha256=sha(BASE/'failure_evidence.json'),
        validations=reports,physical_failure_signature_exercised=triggered,independent_fresh_code=True,
        validation_actor_received_proposer_code=False,learning_kind='persistent document admission; no weight update',
        effect_claim='Functional validation only. Development costs and negative effects retained; unseen-product efficacy untested.')
    write(BASE/'admission.json',receipt,exclusive=True);write(p.parent/'references/admission.json',receipt,exclusive=True)
    if passed:
        make_bank(MEM/'S1.json',[p],version='S1-doc-1.0',evidence=str(BASE/'admission.json'))
        write(DEV/'selected_admission.json',dict(status='ADMITTED',receipt=str(BASE/'admission.json'),sha256=sha(BASE/'admission.json')))
    print('CHECKPOINT_DOCUMENT_ADMISSION',receipt['status'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['propose','validate']);a=p.parse_args();globals()[a.command]()

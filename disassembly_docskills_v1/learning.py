"""Failure -> LLM document proposal -> independent fresh-code replay -> admission.

No proposed actor code is supplied to validators; only the candidate document.
Engineering and learning receipts are separate. Final test meshes are unopened.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress
from .documents import materialize,make_bank,DocumentBank
from .contracts import MODEL,EFFORT,DEV_LIMITS
from .driver import run
from .metrics import summarize

MEM=ROOT/'memory';DEV=ROOT/'outputs/development'
CASES={aid:WORKSPACE/'disassembly_real_v3/cases/fresh_01'/f'asap_{aid}.json' for aid in ['00749','00804']}

def evidence():
    MEM.mkdir(exist_ok=True)
    if not (MEM/'S0.json').exists():make_bank(MEM/'S0.json',[],version='S0-empty')
    origin=WORKSPACE/'disassembly_real_v3/outputs/supplementary/trials/asap_00749/normal/repeat_01/B_code_with_library/result.json'
    old=read(origin)
    fields=['checker_call','operation','part_id','direction','reason','valid','blockers','stability','committed','remaining_before','remaining_after','physical_state_key_before']
    failures=dict(origin_path=str(origin),origin_sha256=sha(origin),source_is_previous_executable_bank_study=True,
        trace=[{k:t.get(k) for k in fields} for t in old['trace']],
        restore_events=[e for e in old['recovery_state']['events'] if e['operation']=='restore'],
        coordinator_observation='Restores at checks12,25,30 abandon accepted prefixes; no claim every restore is logically required. The first instability is removal2 at check11; later the same part can be removed after the assembly changes.',
        scope='Develop a portable procedure using exact-state feedback and checkpoint ancestry, not product IDs or reference action orders.')
    write(DEV/'failure_evidence.json',failures,exclusive=True)
    criteria=dict(version=1,declared_before_validation=utc(),cases=list(CASES),max_validation_episodes=12,
        planned_pairs=['code S0 vs candidate document on origin00749','code S0 vs candidate document on different product00804'],
        admission=['valid compact procedural Markdown without product identifiers or fixed action sequence',
                   'explicit model read plus claimed application on both products',
                   'no loss of full success or final progress relative to the matched empty-bank actor',
                   'no duplicate previously rejected exact-state action; no invalid restores; at least one physical failure feedback exercised in candidate validation',
                   'physical/action/restore replay invariants pass on recorded validation traces'],
        interpretation='Functional, bounded two-product validation; not proof of average speed or unseen-product benefit.',
        source_code_not_supplied_to_validator=True,weight_updates=False)
    write(DEV/'admission_criteria.json',criteria,exclusive=True)
    print('FAILURE_EVIDENCE_READY',flush=True)

def propose():
    from disassembly_mujoco.agent import CodexCLIProvider
    import json
    failure=read(DEV/'failure_evidence.json')
    schema={'type':'object','properties':{k:{'type':'string'} for k in ['name','description','body','reasoning']},'required':['name','description','body','reasoning'],'additionalProperties':False}
    prompt='''Propose ONE concise transferable procedural SKILL.md from these actual failed physics queries and counterproductive search behavior.
The user wants document memory that an LLM reads, not callable stored Python. Do not return Python code or a hard-coded sequence.
Use purpose, applicability/failure signature, diagnosis, ordered repair steps, expected checker feedback, exclusions, evidence and version sections.
Distinguish whole-sequence goal from temporary focus. A rejected action leaves physical state unchanged. Restores must use observed ancestry, not jump to root because one focus is blocked.
Maintain exact-state attempted-edge bookkeeping across restore; do not globally blacklist an action when geometry changes. Continue unrelated legal branches before declaring exhaustion.
Support contacts are hints only. Do not call a stable accepted prefix a dead end without checking alternatives.
Do not include numeric product identities, exact part IDs or specific successful reference directions. Generic API names and state-key concepts are allowed.
The skill must guide both code generation and candidate ordering under a fixed DFS controller, while respecting that controller's recovery contract.
Include a Validation section: the linked `references/admission.json` is authoritative; absent/pending receipt means provisional, not admitted. Include Version1.0.
Your body is the skill procedure, not a retrospective report. No external tools.\nACTUAL SOURCE EVIDENCE:\n'''+json.dumps(failure,ensure_ascii=False)
    provider=CodexCLIProvider(DEV/'skill_proposal/llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    log=DEV/'skill_proposal/llm_calls'
    if (log/'call_01/response.json').exists():
        response=read(log/'call_01/response.json');meta=read(log/'call_01/metadata.json')
    else:response,meta=provider.complete(prompt,schema,1)
    initial_response=response
    revision_reason='The first draft assumes a fixed DFS controller in all architectures; B instead must generate its own search code. This conflicts with the shared API contract, before validation or test geometry exposure.'
    if (log/'call_02/response.json').exists():
        response=read(log/'call_02/response.json');meta=read(log/'call_02/metadata.json')
    else:
        revision='''Revise this one draft to fix a structural contract error. Two modes use the same document:
CODE MODE A/B: there is NO host DFS or hidden search controller. The LLM must generate executable Python that implements its own frontier/bookkeeping/checkpoint restoration through api.
GRAPH_DFS MODE C: host has fixed DFS; LLM only ranks and should not replace host recovery.
State explicit conditional steps for each mode. Do not tell B to wait for a controller signal that does not exist. Preserve evidence limits and no product-specific action order.
Return name in lowercase hyphenated slug form <=64 chars, description, body, reasoning. Keep Version1.0 and references/admission.json.
This is the one allowed pre-validation revision, based on the supplied contract conflict, not held-out performance.
DRAFT:\n'''+json.dumps(response,ensure_ascii=False)
        response,meta=provider.complete(revision,schema,2)
    import re
    slug=re.sub(r'[^a-z0-9]+','-',response['name'].lower()).strip('-')[:64].rstrip('-')
    if any(aid in response['body'] for aid in CASES):raise ValueError('Product identity leaked into portable procedure')
    path=materialize(MEM/'candidates/candidate_01',slug,response['description'],response['body'])
    write(DEV/'skill_proposal/proposal.json',dict(response=response,initial_response=initial_response,revision_reason=revision_reason,metadata=meta,path=str(path),sha256=sha(path)),exclusive=True)
    make_bank(MEM/'candidate.json',[path],version='candidate-01-provisional',evidence=str(DEV/'admission_criteria.json'))
    progress('document_candidate_proposed',skill=response['name'],not_admitted=True)

def validate():
    from .evidence_replay import replay_result
    for aid in CASES:
        for version in ['S0','candidate']:
            run(dict(folder=str(DEV/'validation'/aid/version),case_path=str(CASES[aid]),
                architecture='code',bank_path=str(MEM/(version+'.json')),limits=DEV_LIMITS,
                phase='development_validation',arm=version,shared_path=None))
    reports=[]
    for aid in CASES:
        before=read(DEV/'validation'/aid/'S0/result.json');after=read(DEV/'validation'/aid/'candidate/result.json')
        a,b=summarize(before),summarize(after)
        replay_path=DEV/'validation'/aid/'candidate/replay_audit.json'
        audit=read(replay_path) if replay_path.exists() else replay_result(DEV/'validation'/aid/'candidate/result.json',output=replay_path)[0]
        invalid_restores=[e for e in after.get('recovery_state',{}).get('events',[]) if e['operation']=='restore' and e.get('status')!='completed']
        passed=bool(b['document_reads'] and b['claimed_skill_ids'] and b['final_progress']>=a['final_progress']
                    and (not a['success'] or b['success']) and not b['duplicate_rejected_queries'] and not invalid_restores and audit['status']=='PASS')
        reports.append(dict(source_id=aid,pass_functional_criteria=passed,before=a,after=b,
            before_path=str(DEV/'validation'/aid/'S0/result.json'),after_path=str(DEV/'validation'/aid/'candidate/result.json')))
    triggered=any(r['after']['failed_checks'] for r in reports)
    passed=all(r['pass_functional_criteria'] for r in reports) and triggered
    proposal=read(DEV/'skill_proposal/proposal.json');path=Path(proposal['path'])
    receipt=dict(status='ADMITTED' if passed else 'REJECTED',created_utc=utc(),criteria_sha256=sha(DEV/'admission_criteria.json'),
        document_sha256=sha(path),failure_evidence_sha256=sha(DEV/'failure_evidence.json'),
        validations=reports,physical_failure_signature_exercised=triggered,
        independent_fresh_code=True,validation_actor_received_proposer_code=False,
        learning_kind='persistent document admission; no model-weight update',
        effectiveness_claim='Functional validation only; final held-out comparison is still required.')
    write(path.parent/'references/admission.json',receipt,exclusive=True)
    write(DEV/'admission.json',receipt,exclusive=True)
    if passed:make_bank(MEM/'S1.json',[path],version='S1-doc-1.0',evidence=str(path.parent/'references/admission.json'))
    print('DOCUMENT_ADMISSION',receipt['status'],flush=True)

def smoke():
    from .evidence_replay import replay_result
    reports=[]
    for bank in ['S0','S1']:
        folder=DEV/'controller_smoke'/bank
        result=run(dict(folder=str(folder),case_path=str(CASES['00804']),architecture='graph_dfs',
            bank_path=str(MEM/(bank+'.json')),limits=DEV_LIMITS,phase='development_controller_validation',arm='C_'+bank,shared_path=None))
        audit_path=folder/'replay_audit.json'
        audit=read(audit_path) if audit_path.exists() else replay_result(folder/'result.json',output=audit_path)[0]
        reports.append(dict(bank=bank,metrics=summarize(result),replay=audit))
    write(DEV/'controller_validation.json',dict(status='PASS' if all(r['replay']['status']=='PASS' for r in reports) else 'FAIL',
        results=reports,interpretation='Execution and replay validation, not final held-out efficacy. Fixed finite additional two development episodes.'),exclusive=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['evidence','propose','validate','smoke']);a=p.parse_args()
    globals()[a.command]()

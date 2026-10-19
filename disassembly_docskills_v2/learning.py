"""Physical failure -> real SKILL.md -> independent task-level admission."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress
from .contracts import MODEL,EFFORT,DEV_LIMITS
from .documents import materialize,make_bank
from .driver import run
from .metrics import summarize
from .evidence_replay import replay_result

DEV=ROOT/'outputs/development';MEM=ROOT/'memory'

def propose(round_number=1):
    from disassembly_mujoco.agent import CodexCLIProvider
    name='candidate_%02d'%round_number;folder=DEV/name;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'proposal.json').exists():return read(folder/'proposal.json')
    evidence=read(DEV/'failure_evidence.json')
    prompt='''Create ONE portable SKILL.md describing a PHYSICAL DISASSEMBLY FAILURE-REPAIR PROCEDURE inferred from the supplied real CAD/MuJoCo traces. This is an LLM-readable natural-language procedure, NOT Python code, not a stored search implementation, not API schema advice.
Inspect the failure feedback, unstable residual part IDs, collision blockers, geometry changes and later accepted actions. Distinguish support relationships from interlocking/balancing constraints: a component that becomes unstable need not be in an outgoing support edge. Derive a concrete, testable conditional repair rather than "be careful".
Give precise steps for (1) a collision-free extraction rejected because remaining components move/fall, and (2) an extraction blocked by other component geometry. Say what observed evidence to inspect, which CURRENT removable component candidates to prioritize, when to defer/retry the rejected component, what feedback verifies progress, and when the procedure is inapplicable. All checks still require the trusted physical validator. Never claim known success before a query. Support/contact graph is a hint, not a guaranteed precedence graph. Fixed/absent components cannot be removed.
The same document is read by two roles: CODE generates its own executable program/frontier/record keeping; GRAPH_DFS only ranks available candidate actions and cannot replace host DFS/recovery. The repair must change physical action priorities in BOTH roles. Use role-conditional instructions. Unknown actions must remain available. A failed hypothetical check leaves committed state unchanged. Remember failures only for the exact physical state; reassess after accepted removals or restoration. Never restore just because a single candidate fails; no untested global action blacklist. Use direction_vectors_world for actual world direction, not the spelling of an action label.
Use purpose, applicability/observable triggers, diagnosis, numbered repair procedure, CODE/GRAPH_DFS application, expected physical feedback, exclusions, evidence and validation/version1.0. No product-specific identities, literal part IDs, memorized direction sequence, complete program or numeric held-out references. Cite generic outputs/development/failure_evidence.json and references/admission.json (pending means provisional). Keep under8000 UTF-8 bytes.
You are proposing a procedure from existing source evidence; independent actors will test it on actual reproduced physical failures without your code or any future answer sequence. Do not claim validation or efficacy before admission. No tools.
Return JSON strings name(lowercase-hyphen slug),description,body,reasoning.
ACTUAL PHYSICAL EVIDENCE:\n'''+json.dumps(evidence,ensure_ascii=False)
    if round_number>1:
        previous=read(DEV/'candidate_01/proposal.json');diagnostics=read(DEV/'candidate_01/admission.json')
        prompt+='\nThe single permitted revision must address these DEVELOPMENT observations, not change the validator or physics. Preserve failed candidate history.\nPRIOR_DOCUMENT:\n'+previous['response']['body']+'\nDEVELOPMENT_DIAGNOSTICS:\n'+json.dumps(diagnostics,ensure_ascii=False)
    schema={'type':'object','properties':{k:{'type':'string'} for k in ['name','description','body','reasoning']},'required':['name','description','body','reasoning'],'additionalProperties':False}
    provider=CodexCLIProvider(folder/'proposal_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    response,metadata=provider.complete(prompt,schema,1)
    slug=re.sub('[^a-z0-9]+','-',response['name'].lower()).strip('-')[:64].rstrip('-')
    assert not any(a in response['body'] for a in ['00749','01275','00804','00880'])
    path=materialize(MEM/name,slug,response['description'],response['body'])
    reference=path.parent/'references/admission.json'
    write(reference,dict(status='PROVISIONAL',validation_pending=True,not_evidence_of_effectiveness=True),exclusive=True)
    row=dict(candidate=round_number,response=response,metadata=metadata,path=str(path),sha256=sha(path))
    write(folder/'proposal.json',row,exclusive=True)
    make_bank(MEM/(name+'.json'),[path],version=name+'-physical-provisional',evidence=str(reference))
    if not (MEM/'S0.json').exists():make_bank(MEM/'S0.json',[],version='S0-empty')
    progress('physical_document_proposed',candidate=round_number,document=str(path),admitted=False)
    return row

def validate(round_number=1,candidate_tag=None):
    candidate=candidate_tag or 'candidate_%02d'%round_number;folder=DEV/candidate
    if (folder/'admission.json').exists():return read(folder/'admission.json')
    specs=read(DEV/'failure_seeds.json')['seeds'];reports=[]
    for i,seed in enumerate(specs):
        arms=[('A','code','S0'),('B','code',candidate),('C0','graph_dfs','S0'),('C','graph_dfs',candidate)]
        order=arms[i:]+arms[:i]
        results={}
        for arm,architecture,bank in order:
            target=folder/'validation'/seed['label']/arm
            progress('physical_document_validation',candidate=round_number,seed=seed['label'],arm=arm)
            result=run(dict(folder=str(target),case_path=seed['case_path'],shared_path=seed['shared_path'],
                architecture=architecture,bank_path=str(MEM/(bank+'.json')),limits=DEV_LIMITS,
                phase='development_physical_repair_validation',arm=arm,
                public_task_note='This is a development repair state containing actual rejected extraction feedback. Continue the full-disassembly task using only public observations. All conditions start at the identical prefix and share its costs.'))
            audit_path=target/'replay_audit.json'
            try:
                audit=read(audit_path) if audit_path.exists() else replay_result(target/'result.json',shared_path=seed['shared_path'],output=audit_path)[0]
            except Exception as exc:audit=dict(status='FAIL',error=repr(exc))
            metric=summarize(result)
            new=result.get('trace',[])[seed['seed_checks']:]
            failed_part=seed['failure']['part_id']
            resolved=[t for t in new if t.get('part_id')==failed_part and t.get('valid') and t.get('committed')
                and set(t.get('remaining_before',[]))!=set(read(seed['shared_path'])['state']['remaining'])]
            errors=[d['execution_error'] for d in result.get('decisions',[]) if d.get('execution_error')]
            invalid_restores=[e for e in result.get('recovery_state',{}).get('events',[]) if e['operation']=='restore' and e.get('status')!='completed']
            row=dict(arm=arm,metrics=metric,seed_costs_included=True,new_stable_removals=sum(bool(t.get('committed')) for t in new),
                previously_rejected_part_resolved_after_geometry_change=bool(resolved),execution_errors=errors,
                invalid_restores=len(invalid_restores),replay=audit,result_path=str(target/'result.json'),result_sha256=sha(target/'result.json'))
            results[arm]=row
        for treated,baseline in [('B','A'),('C','C0')]:
            x=results[treated];b=results[baseline];m=x['metrics'];before=b['metrics']
            x['functional_pass']=bool(m['document_reads'] and m['claimed_skill_ids'] and x['new_stable_removals']>0
                and x['previously_rejected_part_resolved_after_geometry_change'] and not x['execution_errors'] and not x['invalid_restores']
                and not m['duplicate_rejected_queries'] and m['final_progress']>=before['final_progress'] and x['replay']['status']=='PASS')
        reports.append(dict(seed=seed['label'],source_id=seed['source_id'],results=results))
    passed=all(s['results'][a]['functional_pass'] for s in reports for a in ['B','C'])
    proposal=read(folder/'proposal.json');document=Path(proposal['path'])
    receipt=dict(status='ADMITTED' if passed else 'REJECTED',created_utc=utc(),candidate=round_number,document_sha256=sha(document),
        validations=reports,validation_scope='task-level physical failure repair: accepted removals and formerly rejected component resolved after changed assembly, no API-only admission',
        reference_future_sequences_supplied=False,proposer_code_supplied=False,model_weight_updates=False,
        cost_improvement_required=False,heldout_efficacy_unknown=True)
    write(folder/'admission.json',receipt,exclusive=True)
    # Provisional validation reference is replaced only here, before final freeze.
    write(document.parent/'references/admission.json',receipt)
    if passed:
        make_bank(MEM/'S1.json',[document],version='S1-physical-document-1.0',evidence=str(folder/'admission.json'))
        write(DEV/'selected_admission.json',dict(status='ADMITTED',candidate=round_number,path=str(folder/'admission.json'),sha256=sha(folder/'admission.json')),exclusive=True)
    progress('physical_document_admission',candidate=round_number,status=receipt['status'])
    print('PHYSICAL_ADMISSION',receipt['status'],flush=True)
    return receipt

def normal_smoke():
    case=WORKSPACE/'disassembly_real_v3/cases/fresh_01/asap_00804.json'
    rows=[]
    for arm,architecture in [('B','code'),('C','graph_dfs')]:
        folder=DEV/'normal_controller_checks'/arm
        result=run(dict(folder=str(folder),case_path=str(case),shared_path=None,architecture=architecture,
            bank_path=str(MEM/'S1.json'),limits=DEV_LIMITS,phase='development_normal_start_check',arm=arm))
        ap=folder/'replay_audit.json';audit=read(ap) if ap.exists() else replay_result(folder/'result.json',output=ap)[0]
        rows.append(dict(arm=arm,metrics=summarize(result),replay=audit))
    write(DEV/'normal_controller_checks/complete.json',dict(status='PASS' if all(r['replay']['status']=='PASS' for r in rows) else 'FAIL',results=rows),exclusive=True)

def main():
    for r in [1,2]:
        propose(r)
        if validate(r)['status']=='ADMITTED':normal_smoke();return
    progress('physical_document_development_stopped',status='NO_ADMITTED_TASK_LEVEL_SKILL',no_API_only_fallback=True)
    raise RuntimeError('No task-level physical skill passed the finite independent validation. Preserve rejection; do not run a misleading learned-bank campaign.')

def engineering_validation():
    """One disclosed rerun after fixing seeded graph initialization,not a new doc.

    The two rejected candidate receipts/paths remain untouched. No additional
    candidate or held-out geometry is used to choose/repair the procedure.
    """
    import shutil
    tag='candidate_02_engineering_validation';folder=DEV/tag;folder.mkdir(parents=True,exist_ok=True)
    amendment=DEV/'graph_seed_import_amendment.json'
    if not amendment.exists():
        original=read(DEV/'candidate_02/proposal.json');source=Path(original['path'])
        target=MEM/tag/source.parent.name/'SKILL.md';target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        assert sha(source)==sha(target)
        write(target.parent/'references/admission.json',dict(status='PROVISIONAL',scope='Unchanged physical procedure;one disclosed revalidation after host exact-state evidence import fix',prior_candidate_rejected=True),exclusive=True)
        write(folder/'proposal.json',{**original,'path':str(target),'unchanged_document_sha256':sha(source),'new_document_generated':False},exclusive=True)
        make_bank(MEM/(tag+'.json'),[target],version=tag+'-provisional',evidence=str(amendment))
        write(amendment,dict(created_utc=utc(),source_document_sha256=sha(source),controller_sha256=sha(ROOT/'controller.py'),
            diagnosis='C did not ingest already observed rejection in its seeded initial state;duplicate support2/-x at the unchanged initial state was confirmed in candidate2 C check7',
            prior_rejection_preserved=True,document_unchanged=True,criteria_unchanged=True,physics_unchanged=True,
            extra_development_episodes=8,extra_candidates=0,additional_attempts_after_this=0,new_evaluation_geometry_unopened=True),exclusive=True)
    receipt=validate(2,tag)
    if receipt['status']!='ADMITTED':raise RuntimeError('The single engineering revalidation did not admit the task-level skill;stop without replacing it by API advice.')
    normal_smoke()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['propose','validate','smoke','all','engineering-validation']);p.add_argument('--round',type=int,default=1);a=p.parse_args()
    if a.command=='propose':propose(a.round)
    elif a.command=='validate':validate(a.round)
    elif a.command=='smoke':normal_smoke()
    elif a.command=='engineering-validation':engineering_validation()
    else:main()

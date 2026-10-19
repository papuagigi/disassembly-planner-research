"""Final finite development block: independent repair-task verification.

Amendment is explicit and pre-probe: document correctness is not the same as
optional retrieval or mean full-product efficacy. Prior rejections stay rejected.
Four verifier episodes exhaust the original12-development-episode ceiling.
Final first-encounter evaluation retains autonomous optional document selection.
"""
import argparse
import json
from pathlib import Path
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress
from .learning import CASES,MEM,DEV
from .documents import materialize,make_bank
from .contracts import MODEL,EFFORT,DEV_LIMITS
from .qualification import shared_input
from .driver import run
from .metrics import summarize
from .evidence_replay import replay_result

BASE=DEV/'repair_verifier'
NOTE='''This is a DEVELOPMENT REPAIR VERIFIER, not the final first-encounter benchmark.
The starting state reproduces a logged blocked branch and its past failure feedback; evaluator-created checkpoints before those past removals are available equally in both bank conditions.
Independently implement the repair without receiving any proposer's code. If a proposed document is listed, explicitly request and read it before producing the validation program; otherwise solve from the common public API.
Resume current/ancestor branches using state-local recorded evidence and actual checkpoint data shapes. Avoid redoing recorded failed actions at the same state. Explore unrelated candidates before treating a blocked focus as a dead end.
The repair task requires safe branch resumption with at least one newly accepted edge. Full disassembly is observed separately; it is not inferred from repairing one defect.
'''

def amend_and_propose():
    from disassembly_mujoco.agent import CodexCLIProvider
    amendment=dict(declared_before_probe=utc(),reason='Optional initial retrieval can be skipped, so a full-product episode without a read cannot establish document correctness. Separate independent explicit-read repair verification from autonomous first-encounter efficacy, following ASPIRE verifier role.',
        prior_admissions_preserved=['outputs/development/admission.json','outputs/development/checkpoint_candidate/admission.json'],
        total_prior_model_validation_episodes=8,new_verifier_episodes=4,total_ceiling=12,
        remaining_document_candidate_count=0,remaining_after_this_revision_model_proposals=0,
        cases=['00804','00749'],new_evaluation_geometry_unopened=True,
        primary_test_unchanged='A/B/C,C(S0); optional autonomous reads; same model,budgets; frozen new CAD first episodes only',
        admission_criteria=['document explicitly read and claimed by independent fresh-code verifier in both products',
            'no TypeError/invalid checkpoint access or restore','no repeated previously rejected exact-state edge, including seeded history',
            'at least one newly committed physical removal per product; for exhausted00804 starting branch, restore a strict observed ancestor first',
            'all API actions,checkpoint context,final physical states and costs independently replay exactly'],
        interpretation='Functional recovery skill admission, not a claim of improved average full-product success. First two autonomous development comparisons remain negative evidence.',
        reference_paths_not_supplied=True,proposer_code_not_supplied_to_verifier=True)
    write(BASE/'AMENDMENT.json',amendment,exclusive=True)
    original=read(DEV/'checkpoint_candidate/proposal.json');failed=read(DEV/'checkpoint_candidate/validation/00804/candidate2/result.json')
    schema={'type':'object','properties':{k:{'type':'string'} for k in ['name','description','body','reasoning']},'required':['name','description','body','reasoning'],'additionalProperties':False}
    prompt='''Make the one allowed revision of this narrow checkpoint-resume procedural skill, using new actual failure evidence.
In a development execution the model ignored the catalog at program creation, repeated31 previously rejected state/action checks, undid6 accepted removals, and consumed60 checks without finishing. It did not read the document. Another product did read it and succeeded. Do not claim these establish a benefit.
Make description useful when DESIGNING a generated checkpoint/frontier search, as well as repairing string-index TypeError at resumption. Preserve CODE vs fixed GRAPH_DFS responsibility.
Add precise reconstruction of tried edges from snapshot.history_feedback across model turns, including BOTH committed and rejected attempts at each physical_state_key_before. This prevents re-entering a completed child after restore. Current-state candidate part records come from snapshot.remaining_parts; cp.remaining_parts are string IDs only.
Choose nearest eligible actual ancestor by accepted_action_prefix prefix relationship; only restore after all current legal candidates are spent. Do not skip unrelated candidates because focus is blocked.
Keep the skill short, procedural, no complete Python search policy, no specific part/product IDs or remembered direction order. Evidence may link source logs; no hard-coded actions in procedure. Version1.1. Validation link references/admission.json provisional until admitted.
Return lowercase hyphenated name, description, body, reasoning; no external tools.\nCURRENT DOCUMENT:\n'''+Path(original['path']).read_text()
    provider=CodexCLIProvider(BASE/'proposal_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    response,metadata=provider.complete(prompt,schema,4)
    path=materialize(MEM/'candidates/candidate_02_revision_01',response['name'],response['description'],response['body'])
    write(BASE/'proposal.json',dict(response=response,metadata=metadata,path=str(path),sha256=sha(path),revision_of=original['path']),exclusive=True)
    make_bank(MEM/'repair_candidate.json',[path],version='candidate2-revision1-provisional',evidence=str(BASE/'AMENDMENT.json'))

def prepare_probes():
    from disassembly_real_v3.simulator import FullDisassemblySim
    from disassembly_learning_v3.shared_api import SharedAPI
    sequences={'00804':[('0','-x'),('1','-x'),('3','-y')],
               '00749':[('3','-y'),('0','+z')]}
    blocked={'00804':'4','00749':'2'}
    for aid in ['00804','00749']:
        cp=CASES[aid];sim=FullDisassemblySim(cp,max_checks=60);api=SharedAPI(sim,max_checks=60)
        for p,d in sequences[aid]:
            api.checkpoint();r=api.remove(p,d);assert r['valid'],('Actual source prefix changed',aid,p,d,r['reason'])
        api.checkpoint()
        for d in ['+x','-x','+y','-y','+z','-z']:
            r=api.remove(blocked[aid],d);assert not r['valid'],('Expected logged focus rejection not reproduced',aid,d)
        seed=dict(state=sim.export_state(),recovery_state=api.export_recovery_state(),observation=api.snapshot(),
            preparation_checks=sim.checks,evaluation_first_encounter=False,
            provenance='Reexecuted development failure prefix; checkpoints added before the same observed branches to verify the proposed checkpoint-before-branch repair. No withheld reference order supplied.')
        write(BASE/'probes'/aid/'shared.json',seed,exclusive=True)
        print('REPAIR_PROBE_READY',aid,sim.checks,flush=True)

def validate():
    amendment=read(BASE/'AMENDMENT.json');rows=[]
    for aid in ['00804','00749']:
        seed_path=BASE/'probes'/aid/'shared.json';seed=read(seed_path);results={}
        seed_events=len(seed['recovery_state']['events'])
        for bank in ['S0','repair_candidate']:
            folder=BASE/'trials'/aid/bank
            result=run(dict(folder=str(folder),case_path=str(CASES[aid]),shared_path=str(seed_path),architecture='code',
                bank_path=str(MEM/(bank+'.json')),limits=DEV_LIMITS,phase='development_explicit_repair_verifier',arm=bank,public_task_note=NOTE))
            audit_path=folder/'replay_audit.json'
            audit=read(audit_path) if audit_path.exists() else replay_result(folder/'result.json',shared_path=seed_path,output=audit_path)[0]
            newtrace=result['trace'][len(seed['state']['trace']):];oldbad={(t['physical_state_key_before'],t['part_id'],t['direction']) for t in seed['state']['trace'] if not t.get('valid')}
            repeated=0
            for t in newtrace:
                key=(t['physical_state_key_before'],t['part_id'],t['direction']);repeated+=key in oldbad
                if not t['valid']:oldbad.add(key)
            errors=[d.get('execution_error') for d in result['decisions'] if d.get('execution_error')]
            events=result['recovery_state']['events'][seed_events:]
            restores=[e for e in events if e['operation']=='restore' and e.get('restored')]
            accepted=[t for t in newtrace if t.get('committed')]
            behavior_pass=bool(not repeated and accepted and not errors and audit['status']=='PASS')
            if aid=='00804':
                start_prefix=len(seed['state']['actions'])
                valid_ancestor=any(len(result['recovery_state']['checkpoints'][e['handle']]['metadata']['accepted_action_prefix'])<start_prefix for e in restores)
                behavior_pass=behavior_pass and valid_ancestor
            read_applied=bool(result['document_reads'] and any(d.get('claimed_application_ids') for d in result['decisions']))
            passed=behavior_pass and (bank=='S0' or read_applied)
            results[bank]=dict(functional_repair_pass=passed,trace_behavior_pass=behavior_pass,document_read_and_claimed=read_applied,metrics=summarize(result),new_physical_checks=len(newtrace),new_accepted_edges=len(accepted),new_repeated_rejected_edges=repeated,
                new_restores=len(restores),execution_errors=errors,replay_audit=audit,result=str(folder/'result.json'))
        rows.append(dict(source_id=aid,**results))
    passed=all(row['repair_candidate']['functional_repair_pass'] for row in rows)
    proposal=read(BASE/'proposal.json');p=Path(proposal['path'])
    receipt=dict(status='ADMITTED' if passed else 'REJECTED',created_utc=utc(),criteria_sha256=sha(BASE/'AMENDMENT.json'),
        document_sha256=sha(p),source_failure_evidence=[str(DEV/'checkpoint_candidate/failure_evidence.json'),str(DEV/'checkpoint_candidate/validation/00804/candidate2/result.json')],
        validations=rows,validation_kind='explicit-read independent fresh-code repair task, not autonomous full-product efficacy',
        full_product_success_required_for_admission=False,all_prior_negative_outcomes_retained=True,
        no_model_weight_update=True,total_live_development_validation_episodes=12,
        final_evaluation_autonomous_retrieval_unchanged=True)
    write(BASE/'admission.json',receipt,exclusive=True);write(p.parent/'references/admission.json',receipt,exclusive=True)
    if passed:
        make_bank(MEM/'S1.json',[p],version='S1-doc-1.1',evidence=str(BASE/'admission.json'))
        write(DEV/'selected_admission.json',dict(status='ADMITTED',receipt=str(BASE/'admission.json'),sha256=sha(BASE/'admission.json')),exclusive=True)
    progress('finite_document_development_complete',admission=receipt['status'],episodes=12,remaining_development_episodes=0)
    print('EXPLICIT_REPAIR_VERIFICATION',receipt['status'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['amend_and_propose','prepare_probes','validate']);a=p.parse_args();globals()[a.command]()

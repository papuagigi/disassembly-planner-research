"""Scoped physical-procedure verification; never relabel strict actor rejection."""
from pathlib import Path
import json
import shutil
from .common import ROOT,read,write,sha,utc,progress
from .contracts import MODEL,EFFORT
from .documents import make_bank
from .evidence_replay import replay_result

BASE=ROOT/'outputs/development/physical_procedure_verifier'

def main():
    from disassembly_mujoco.agent import CodexCLIProvider
    from disassembly_real_v3.simulator import FullDisassemblySim
    from disassembly_real_v3.runtime import execute_payload
    BASE.mkdir(parents=True,exist_ok=True)
    original=read(ROOT/'outputs/development/candidate_02/proposal.json');source=Path(original['path'])
    doc=ROOT/'memory/physical_procedure_verified'/source.parent.name/'SKILL.md'
    if not (BASE/'criteria.json').exists():
        doc.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,doc)
        write(BASE/'criteria.json',dict(created_utc=utc(),declared_before_new_verifier_calls=True,
            strict_actor_admission_remains='REJECTED',strict_admission_paths=[str(ROOT/'outputs/development'/p/'admission.json') for p in ['candidate_01','candidate_02','candidate_02_engineering_validation']],
            reason='Separate the knowledge artifact physical repair test from end-to-end actor zero-runtime-error integration. Both failures were physically repaired by treated actors,but recovered generated-code field errors failed the stricter gate. Do not reinterpret that outcome.',
            scope='Bounded physical disassembly procedure only;not API-only repair and not full-planner robustness/admission',
            document_unchanged_sha256=sha(doc),max_independent_program_attempts_per_state=2,states=['support','interlock'],
            admission=['no execution error in the accepted independent verifier','at least one different component stably removed',
                'the previously rejected exact part/direction is physically accepted after changed remaining geometry',
                'independent replay matches physical feedback,states and costs'],
            no_new_document_candidate=True,no_future_reference_sequence_or_proposer_code=True,no_new_evaluation_geometry_opened=True,
            after_this_no_additional_development_attempts=True),exclusive=True)
    assert sha(source)==sha(doc)
    reports=[]
    seeds=read(ROOT/'outputs/development/failure_seeds.json')['seeds']
    for seed in seeds:
        outcomes=[];passed=False
        for attempt in [1,2]:
            folder=BASE/seed['label']/('attempt_%02d'%attempt);rp=folder/'result.json'
            if rp.exists():raw=read(rp);verification=read(folder/'verification.json')
            else:
                shared=read(seed['shared_path']);observation=shared['observation']
                # Remove bulky implementation diagnostics only from this bounded
                # verifier prompt; actual public physical evidence stays exact.
                observation=json.loads(json.dumps(observation))
                for item in observation.get('current_state_feedback',[]):item.pop('collision_policy',None)
                prompt='''Independently write a SHORT restricted Python program to validate the supplied PHYSICAL DISASSEMBLY REPAIR SKILL on this actual failed state. Do not solve the full product. You receive the document and public observations only,no proposer code or future answer sequence.
Goal: make at least one stable accepted removal of a DIFFERENT remaining nonfixed component,then query the EXACT originally rejected part/direction again. Stop when that original query becomes valid,or at40total checks including the seed. Every action is independently checked with real source geometry and MuJoCo. A change of direction without a change of remaining geometry does not validate this repair. Do not use tools/files/imports.
API: api.snapshot() returns state_key,remaining_parts(list of dicts with id,fixed,allowed_directions),current_state_feedback(list of exact recent result dicts),support_edges,direction_vectors_world. api.remove(part_id,direction) tests and commits only valid/stable removals; api.check(part_id,direction) tests without committing. Both consume one check. Their reason/valid fields exist; stability is OPTIONAL and may be absent or None for path collisions. Use result.get('stability') or {} and optional access for its fields. Snapshot feedback carries observed unstable_parts in a stability dict only when such a test ran. These type instructions are API facts,not the learned physical procedure.
Allowed builtins:len,range,list,dict,set,tuple,sorted,min,max,enumerate,all,any,bool,str. No imports,classes,reflection,type,isinstance,exceptions,fstrings. Include top-level invocation of your function. Keep code short and bounded. Return code and summary. No tools.
PHYSICAL PROCEDURE DOCUMENT:\n'''+doc.read_text()+'\nPUBLIC OBSERVATION:\n'+json.dumps(observation,ensure_ascii=False)+'\nOBSERVED ORIGINAL REJECTION:\n'+json.dumps({k:seed['failure'].get(k) for k in ['part_id','direction','reason','stability']},ensure_ascii=False)
                if outcomes:prompt+='\nYour previous bounded verification outcome (same development state,final permitted attempt):\n'+json.dumps(outcomes[-1],ensure_ascii=False)
                schema={'type':'object','properties':{'code':{'type':'string'},'summary':{'type':'string'}},'required':['code','summary'],'additionalProperties':False}
                provider=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=90)
                response,metadata=provider.complete(prompt,schema,1)
                sim=FullDisassemblySim(seed['case_path'],max_checks=40,state=shared['state'])
                raw=execute_payload(dict(code=response['code'],exports=[],library_bank=None,max_checks=40,max_steps=1000000,
                    timeout_seconds=90,recovery_state=shared['recovery_state'],max_checkpoints=128,max_restores=256),sim,callback=lambda e:None)
                raw.update(case_id=sim.case['id'],case_path=seed['case_path'],limits=dict(max_checks=40,max_checkpoints=128,max_restores=256),
                    decisions=[dict(response=response,metadata=metadata)],verification_scope='bounded physical repair,not full disassembly',
                    proposer_code_supplied=False,reference_sequence_supplied=False,document_sha256=sha(doc))
                write(rp,raw,exclusive=True)
                new=raw['trace'][seed['seed_checks']:];initial=set(shared['state']['remaining'])
                recovered=[t for t in new if t.get('valid') and t['part_id']==seed['failure']['part_id'] and t['direction']==seed['failure']['direction']
                    and set(t['remaining_before'])!=initial]
                others=[t for t in new if t.get('committed') and t['part_id']!=seed['failure']['part_id']]
                audit=replay_result(rp,shared_path=seed['shared_path'],output=folder/'replay_audit.json')[0]
                verification=dict(passed=bool(raw['error'] is None and recovered and others and audit['status']=='PASS'),
                    error=raw['error'],new_physical_checks=len(new),other_stable_removals=len(others),
                    exact_rejected_query_accepted_after_changed_geometry=bool(recovered),independent_physical_replay=audit['status'],
                    no_claim_of_full_planner_reliability=True)
                write(folder/'verification.json',verification,exclusive=True)
            outcomes.append(verification)
            if verification['passed']:passed=True;break
        reports.append(dict(seed=seed['label'],passed=passed,attempts=outcomes))
    admitted=all(r['passed'] for r in reports)
    receipt=dict(status='ADMITTED_PHYSICAL_PROCEDURE' if admitted else 'REJECTED',created_utc=utc(),document_sha256=sha(doc),
        validations=reports,strict_full_actor_integration_status='REJECTED',strict_rejections_preserved=True,
        scope='Independent bounded physical failure repair;not API-only repair,not full-search robustness,not held-out benefit',
        no_new_document_candidate=True,no_model_weight_update=True,heldout_efficacy_unknown=True)
    write(BASE/'admission.json',receipt,exclusive=True);write(doc.parent/'references/admission.json',receipt,exclusive=True)
    if not admitted:raise RuntimeError('The final bounded physical-procedure verifier did not pass;stop without claiming a validated physical skill.')
    make_bank(ROOT/'memory/S1.json',[doc],version='S1-physical-repair-unit-verified-1.0',evidence=str(BASE/'admission.json'))
    write(ROOT/'outputs/development/selected_admission.json',dict(status=receipt['status'],path=str(BASE/'admission.json'),sha256=sha(BASE/'admission.json'),strict_actor_integration_status='REJECTED'),exclusive=True)
    progress('bounded_physical_procedure_admitted',strict_full_actor_integration='REJECTED',states=2)
    from .learning import normal_smoke
    normal_smoke()

if __name__=='__main__':main()

"""Bounded live LLM skill discovery; no handwritten repair passed as learned code."""
import copy
import json
from pathlib import Path
import time
from disassembly_mujoco.agent import CodexCLIProvider
from disassembly_learning_v1 import discovery as prior
from disassembly_learning_v1.memory import create_bank, validate_skill
from .common import ROOT, WORKSPACE, MODEL, EFFORT, LIMITS, SkillBank, digest, read, write, solve_case

EXTRA = '''\nSUPPORT-FAILURE STUDY:
Existing skills are retained byte-for-byte. Propose one additional repair chosen from the actual logs.
Current support_edges are vertical contact relationships, NOT proof of sufficient load-bearing balance.
A failed unstable_remainder check leaves accepted state unchanged. Restoration is useful only to a different saved state.
Consider which previous checkpoint restores useful support while retaining already completed useful removals.
Checkpoints supply creation_event_index, remaining_parts, removed_count and opaque handle. Never invent a handle.
The bank retrieves ONE matching skill: most triggers wins, newest wins ties. Existing S1 has three triggers.
Choose applicability conservatively so the old collision skill can still run in states where the new repair is not needed.
Do not rank the same rejected action again. Do not assume a failed direction makes all future states impossible.
All changes are soft priorities/restoration hints: no candidate is permanently deleted by a skill.
Use new failure evidence, not a known answer sequence. Before and after share the unchanged controller.
'''

def compact(result):
    value = prior.compact_episode(result)
    value['track'] = result['track']
    value['checkpoints'] = [c['metadata'] for c in result['recovery_state']['checkpoints'].values()]
    value['backtracks'] = result['backtracks']
    value['retrieval_features'] = [{**{k:r.get(k) for k in ('state_key','skill_id','returned_handle','checks_before','executed_action')}, 'features': r['retrieval']['features']} for r in result['retrievals']]
    value['failure_counts'] = {reason:sum(t.get('reason') == reason for t in result['trace']) for reason in ('path_collision','unstable_remainder')}
    return value

def run_suite(cases, bank, folder):
    return [solve_case(c,bank,t,folder/c['case_id']/t) for c in cases for t in ('normal','seeded')]

def learn(max_candidates=3):
    folder=ROOT/'outputs/learning'; assert not (folder/'ledger.json').exists(), 'Append-only completed study'
    index=read(ROOT/'outputs/input_audit/development_cases.json')
    dev=index['development']; validation=index['validation']
    parent_path=WORKSPACE/'disassembly_learning_v1/memory/banks/S1.json'
    parent=read(parent_path)
    target=ROOT/'memory/banks/S1.json';target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): assert target.read_bytes()==parent_path.read_bytes()
    else: target.write_bytes(parent_path.read_bytes())
    baseline=run_suite(dev,parent,folder/'baseline_development')
    baseline_val=run_suite(validation,parent,folder/'baseline_validation')
    previous=[];attempts=[];selected=None
    for number in range(1,max_candidates+1):
        attempt=folder/f'candidate_{number:02d}'; assert not attempt.exists()
        prompt=prior.INSTRUCTIONS+EXTRA+'\nBASELINE PROCEDURES:\n'+Path(prior.library_functions.__file__).read_text()+\
            '\nACTUAL DEVELOPMENT FAILURES:\n'+json.dumps([compact(r) for r in baseline])+\
            '\nCURRENT SKILLS:\n'+json.dumps(parent['skills'])+\
            '\nPREVIOUS DEVELOPMENT FEEDBACK:\n'+json.dumps(previous)
        started=time.monotonic();record={'candidate':number,'admitted':False}
        provider=CodexCLIProvider(attempt/'llm',model=MODEL,reasoning_effort=EFFORT,timeout=120)
        try:
            response,meta=provider.complete(prompt,prior.SCHEMA,1)
            skill={k:response[k] for k in ('name','failure_signature','when_to_apply','strategy','triggers','source')}
            skill['id']='repair_'+digest(skill)[:12];skill['source_sha256']=validate_skill(skill)
            skill['provenance']={'model':MODEL,'reasoning_effort':EFFORT,'candidate':number,
                'response_sha256':digest(response),'development_case_ids':[c['case_id'] for c in dev],
                'handwritten_repair':False,'validation_feedback_returned':False}
            write(attempt/'skill.json',skill)
            candidate=copy.deepcopy(parent);candidate.pop('bank_sha256')
            candidate['skills'].append(skill);candidate['version']=f'candidate_{number:02d}'
            candidate['bank_sha256']=digest(candidate)
            results=run_suite(dev,candidate,attempt/'development')
            accepted=prior.acceptable(baseline,results)
            record.update(syntax_ok=True,metadata=meta,skill_id=skill['id'],
                development_before=prior.score(baseline),development_after=prior.score(results),development_improves=accepted)
            previous.append({'source':response['source'],'rationale':response['rationale'],
                'development_score':prior.score(results),'baseline_score':prior.score(baseline),
                'failure_evidence':[compact(r) for r in results]})
            if accepted:selected=(skill,candidate,record)
        except Exception as error:
            record.update(syntax_ok=False,error={'type':type(error).__name__,'message':str(error)})
            previous.append({'candidate_error':record['error']})
        record['elapsed_seconds']=time.monotonic()-started
        attempts.append(record);write(attempt/'review.json',record)
        print(json.dumps({k:v for k,v in record.items() if k!='metadata'}),flush=True)
        if selected:break
    admitted=False;after_val=[];newskills=parent['skills']
    if selected:
        skill,candidate,record=selected
        after_val=run_suite(validation,candidate,folder/'selected_validation')
        admitted=prior.acceptable(baseline_val,after_val)
        if admitted:
            skill['validation']={'before':prior.score(baseline_val),'after':prior.score(after_val),
                                'criterion':'No success regression, no extra final removals, no runtime error; strictly improved successful check cost or success count.'}
            newskills=[*parent['skills'],skill]
    bank=create_bank(ROOT/'memory/banks/S2.json','S2',newskills,parent=parent['bank_sha256'],
        provenance={'admitted_new_skill':admitted,'parent_source_preserved':True,'development_only_proposal':True,
                    'validation_feedback_returned_to_proposer':False,'heldout_seen':False})
    assert bank['skills'][:len(parent['skills'])]==parent['skills']
    ledger={'status':'complete','admitted':admitted,'attempts':attempts,'model':MODEL,'reasoning_effort':EFFORT,
        'limits':LIMITS,'before_bank_sha256':parent['bank_sha256'],'after_bank_sha256':bank['bank_sha256'],
        'skill_count_before':len(parent['skills']),'skill_count_after':len(newskills),
        'development_before':prior.score(baseline),'validation_before':prior.score(baseline_val),
        'validation_after':prior.score(after_val) if after_val else None,
        'development_cases':dev,'validation_cases':validation,'validation_feedback_used_for_proposal':False,
        'heldout_seen':False,'weights_changed':False,'controller_changed':False,
        'no_admission_policy':'S2 retains S1 unchanged if no candidate passes; report no learning improvement.'}
    write(folder/'ledger.json',ledger);print(json.dumps(ledger),flush=True)

if __name__=='__main__':learn()

"""Corrected development-only diagnostics after retained no-op acquisition round.

Round 1's summaries read feature keys at the wrong nesting level. This round
uses actual retrieval.features, trigger coverage, and concise observed failures.
No validation outcomes or evaluation geometry are given to proposal actors.
"""
import copy
import json
from pathlib import Path
import time
from . import discovery as first
from .common import *
from disassembly_learning_v1 import discovery as prior
from disassembly_learning_v1.memory import create_bank, validate_skill
from disassembly_mujoco.agent import CodexCLIProvider

def compact(result):
    obs=copy.deepcopy(result['initial_observation'])
    for key in ('history_feedback','current_state_feedback','common_probe_feedback'):
        obs.pop(key,None)
    failures=[t for t in result['trace'] if t.get('reason')=='unstable_remainder']
    keep=[]
    for trace in failures[:3]:
        keep.append({k:trace.get(k) for k in ('part_id','direction','reason','valid','committed',
            'physical_state_key_before','checker_call','stability')})
    observed=[];seen=set()
    for r in result['retrievals']:
        tags=r['retrieval']['features'];signature=tuple(tags)
        if signature in seen:continue
        seen.add(signature)
        observed.append({'features':tags,'checks_before':r['checks_before'],
            'state_key':r['state_key'],'skill_id':r['skill_id'],'restore_applied':r['restore_applied'],
            'returned_handle':r['returned_handle'],'executed_action':r.get('executed_action')})
    return {'initial_observation':obs,'track':result['track'],'checks':result['checker_calls'],
        'success':result['success'],'unstable_checks':keep,'actual_feature_states':observed,
        'backtracks':result['backtracks'],
        'checkpoints':[c['metadata'] for c in result['recovery_state']['checkpoints'].values()],
        'accepted_checks':[{k:t.get(k) for k in ('part_id','direction','checker_call','physical_state_key_before','physical_state_key_after')}for t in result['trace']if t.get('committed')]}

def run():
    folder=ROOT/'outputs/learning_round2';assert not folder.exists()
    index=read(ROOT/'outputs/input_audit/development_cases.json')
    parent=read(ROOT/'memory/banks/S2.json')
    dev=index['development']; val=index['validation']
    baseline=[read(ROOT/'outputs/learning/baseline_development'/c['case_id']/t/'result.json')for c in dev for t in ('normal','seeded')]
    baseline_val=[read(ROOT/'outputs/learning/baseline_validation'/c['case_id']/t/'result.json')for c in val for t in ('normal','seeded')]
    retained=read(ROOT/'outputs/learning/ledger.json')
    feedback=[{'candidate':a['candidate'],'development_before':a['development_before'],'development_after':a['development_after'],
               'triggers':read(ROOT/'outputs/learning'/f"candidate_{a['candidate']:02d}"/'skill.json')['triggers']}for a in retained['attempts']]
    explanation='''The prior summarizer accidentally supplied null features. The corrected actual feature lists below are authoritative.
All three prior candidates required target_is_sole_support. Earlier target-instability states actually contain alternate_support_available, target_supports_load, unstable_remainder, prior_checkpoint_available, accepted_branch, but NOT target_is_sole_support.
Those candidates only activated later, once another support was removed and the base already restored root; their exact-state guard then made no difference.
Inspect the actual stability dictionary keys below; do not invent an unstable_parts field. A contact edge does not establish load-bearing capacity.
Construct a narrow repair that reacts to observed failed target stability even when an alternate contact remains. Prefer an available earlier checkpoint restoring removed support, retaining useful progress if possible. This is soft rollback, not proof that a branch is impossible.
Runtime checkpoints use remaining_parts and creation_event_index, not observation parts. Trigger coverage is observable; choose triggers that actually occur at relevant failed states.
No reference route or validation feedback is supplied. Keep the existing candidate ranking as far as possible and let the existing S1 blocker skill run when repair is inapplicable.
'''
    selected=None;attempts=[]
    for number in range(1,4):
        attempt=folder/f'candidate_{number:02d}';started=time.monotonic()
        prompt=prior.INSTRUCTIONS+first.EXTRA+'\nACTUAL DEVELOPMENT DIAGNOSIS:\n'+explanation+\
            '\nCORRECTED DEVELOPMENT EVIDENCE:\n'+json.dumps([compact(r)for r in baseline],separators=(',',':'))+\
            '\nCURRENT RETAINED SKILL:\n'+json.dumps(parent['skills'],separators=(',',':'))+\
            '\nDEVELOPMENT CANDIDATE FEEDBACK:\n'+json.dumps(feedback,separators=(',',':'))
        provider=CodexCLIProvider(attempt/'llm',model=MODEL,reasoning_effort=EFFORT,timeout=120)
        record={'candidate':number,'admitted':False}
        try:
            response,meta=provider.complete(prompt,prior.SCHEMA,1)
            skill={k:response[k]for k in ('name','failure_signature','when_to_apply','strategy','triggers','source')}
            skill['id']='repair_'+digest(skill)[:12];skill['source_sha256']=validate_skill(skill)
            skill['provenance']={'model':MODEL,'reasoning_effort':EFFORT,'round':2,'candidate':number,
                'response_sha256':digest(response),'handwritten_repair':False,'corrected_feature_summary':True,
                'human_guidance':'development diagnosis and checkpoint-repair hypothesis; no source written by host',
                'validation_feedback_returned':False,'heldout_seen':False}
            write(attempt/'skill.json',skill)
            trial=copy.deepcopy(parent);trial.pop('bank_sha256');trial['skills'].append(skill)
            trial['version']=f'round2_candidate{number}';trial['bank_sha256']=digest(trial)
            results=first.run_suite(dev,trial,attempt/'development')
            ok=prior.acceptable(baseline,results)
            record.update(metadata=meta,syntax_ok=True,skill_id=skill['id'],development_improves=ok,
                development_before=prior.score(baseline),development_after=prior.score(results))
            feedback.append({'source':response['source'],'development_score':prior.score(results),
                'baseline_score':prior.score(baseline),'corrected_evidence':[compact(r)for r in results if r['track']=='seeded']})
            if ok:selected=(skill,trial,record)
        except Exception as error:
            record.update(syntax_ok=False,error={'type':type(error).__name__,'message':str(error)})
            feedback.append({'error':record['error']})
        record['elapsed_seconds']=time.monotonic()-started;attempts.append(record)
        write(attempt/'review.json',record)
        print(json.dumps({k:v for k,v in record.items()if k!='metadata'}),flush=True)
        if selected:break
    admitted=False;after_val=[];skills=parent['skills']
    if selected:
        skill,trial,record=selected
        after_val=first.run_suite(val,trial,folder/'selected_validation')
        admitted=prior.acceptable(baseline_val,after_val)
        record['admitted']=admitted;write(folder/f"candidate_{record['candidate']:02d}"/'review.json',record)
        if admitted:
            skill['validation']={'before':prior.score(baseline_val),'after':prior.score(after_val),
                'criterion':'No success regression, no extra final removals, no errors; improve successful check cost or successes.'}
            skills=[*parent['skills'],skill]
    bank=create_bank(ROOT/'memory/banks/S3.json','S3',skills,parent=parent['bank_sha256'],provenance={
        'round':2,'admitted_new_skill':admitted,'old_skill_source_unchanged':True,'heldout_seen':False})
    assert bank['skills'][:len(parent['skills'])]==parent['skills']
    ledger={'status':'complete','admitted':admitted,'attempts':attempts,'model':MODEL,'reasoning_effort':EFFORT,
        'limits':LIMITS,'skill_count_before':len(parent['skills']),'skill_count_after':len(skills),
        'before_bank_sha256':read(ROOT/'memory/banks/S1.json')['bank_sha256'],'after_bank_sha256':bank['bank_sha256'],
        'validation_before':prior.score(baseline_val),'validation_after':prior.score(after_val)if after_val else None,
        'previous_round':'outputs/learning/ledger.json','this_round':'outputs/learning_round2/ledger.json',
        'validation_feedback_used_for_proposal':False,'heldout_seen':False,'weights_changed':False,
        'note':'S2 is retained rejected-update bank, equal skill set to S1. Final comparison uses S1 vs S3.'}
    write(folder/'ledger.json',ledger);write(ROOT/'outputs/final_learning_ledger.json',ledger)
    print(json.dumps({k:v for k,v in ledger.items()if k!='attempts'}),flush=True)

if __name__=='__main__':run()

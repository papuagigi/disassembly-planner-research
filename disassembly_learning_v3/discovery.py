"""Bounded live-code revision using development failures; immutable heldout bank.

The coordinator diagnoses contracts and evaluates a generated pure procedure.
It never writes/replaces the repair's Python source. Validation feedback is not
returned to proposal actors. References are coordinator-only admission checks.
"""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from disassembly_learning_v1.discovery import INSTRUCTIONS, SCHEMA, score
from disassembly_mujoco.agent import CodexCLIProvider
from .common import ROOT, MODEL, EFFORT, LIMITS, prepare, solve_case, read
from .memory import SkillBank, digest, validate_skill, write


def progress(phase, **details):
    write(ROOT/'outputs/progress.json', dict(phase=phase, owner='Codex',
          claude_assigned=False, updated_utc=datetime.now(timezone.utc).isoformat(), **details))


def suite(cases, bank, folder):
    results=[]
    for case in cases:
        for track in ('normal','seeded'):
            path=Path(folder)/case['case_id']/track
            if (path/'result.json').exists():
                raise FileExistsError('Retained development result must not be overwritten: '+str(path))
            result=solve_case(case,bank,track,path,llm_rank=False)
            result.update(case_id=case['case_id'])
            write(path/'result.json',result)
            results.append((case,track,result))
    return results


def nearest_evidence(case, result):
    events=[e for e in result['recovery_state']['events']
            if e['operation']=='restore' and e.get('restored') and e['state_key_before']!=e['state_key_after']]
    if not events:return {'actual_restores':0,'retained_prefix':None,'restored_parts':[],'nearest_verified':False}
    first=events[0];cp=result['recovery_state']['checkpoints'][first['handle']]
    prefix=case['seed_setup']['prefix_actions']
    current_prefix=cp['metadata'].get('accepted_action_prefix',[])
    failed_key=first['state_key_before']
    prior=next((r for r in reversed(result['trace'])
                if r.get('physical_state_key_after')==failed_key),None)
    prior_remaining=set(prior['remaining_after']) if prior else set()
    restored=set(cp['metadata']['remaining_parts'])-prior_remaining
    wrong=case['seed_setup']['wrong_action']['part_id']
    compatible=[x for x in result['recovery_state']['checkpoints'].values()
                if x['metadata']['creation_event_index']<first['event_index']
                and wrong in x['metadata']['remaining_parts']
                and x['metadata'].get('accepted_action_prefix')==prefix]
    nearest=bool(compatible and current_prefix==prefix and wrong in restored
                 and cp['metadata']['creation_event_index']==max(x['metadata']['creation_event_index'] for x in compatible))
    return {'actual_restores':len(events),'first_restore_checks':first['checks_after'],
            'checkpoint_event_index':cp['metadata']['creation_event_index'],
            'retained_prefix':sum(a in current_prefix for a in prefix),
            'restored_parts':sorted(restored),'nearest_verified':nearest,
            'checks_refunded':first['checks_after']!=first['checks_before']}


def compact(case, track, result):
    obs=copy.deepcopy(result['initial_observation'])
    for key in ('history_feedback','current_state_feedback','common_probe_feedback'):
        obs.pop(key,None)
    return {'track':track,'observation':obs,
            'accepted_prefix':result['initial_observation']['accepted_action_prefix'],
            'failures':[{k:t.get(k) for k in ('part_id','direction','reason','committed','valid',
                'api_event_index','checker_call','physical_state_key_before','remaining_before','stability')}
                for t in result['trace'] if t.get('reason')=='unstable_remainder'][:2],
            'committed_history':[{k:t.get(k) for k in ('part_id','direction','api_event_index',
                'physical_state_key_before','physical_state_key_after','remaining_before','remaining_after')}
                for t in result['trace'][:result['preparation_checks']] if t.get('committed')],
            'first_restore':result['backtracks'][:1],
            'checks':result['checker_calls'],'success':result['success'],
            'features_at_start':result['retrievals'][0]['retrieval']['features'] if result['retrievals'] else []}


EXTRA='''
Revise the earlier support-rollback skill, not the retained ordering skill.
Actual prior source maximized restored count and returned root; it also compared
different counter spaces. Runtime now executes ORDER then RESTORE as separate
roles, and ignores any ordering change from RESTORE. Return candidates unchanged.
Keep triggers exactly unstable_remainder, prior_checkpoint_available,
alternate_support_available (all three actually observed), so the new restore
revision supersedes the prior restore entry at equal specificity.

New public checkpoint context:
- creation_event_index uses the SAME API-event counter as history.api_event_index.
  checker_call counts only physics checks and MUST NOT be used for that comparison.
- accepted_action_prefix is the observed committed path, action dicts only.
- support_edges is the contact graph observed WHEN that checkpoint was saved.
- remaining_parts is the saved set; removed_count is saved path length.
observation.accepted_action_prefix is the CURRENT accepted path.
All saved equilibria may be stable, including strategically bad branch states.
The nearest checkpoint before the failed CHECK may still be after wrong removal.
Require a current-state target unstable_remainder failure. Its stability.unstable_parts
is an actually available list of displaced residual bodies. Use historical contact
edges to infer a currently absent supporter of those loads, and history of committed
removals to identify the causative removal on the current branch. Then choose a
compatible ancestor BEFORE that removal restoring the implicated support while
retaining the longest useful current prefix. Skip same-state and incompatible-branch
checkpoints. Break ties consistently by observed API-event index, not a hard-coded
handle or part ID. If evidence cannot identify a supported repair, return no hint.
Contact evidence is heuristic, not global future stability proof. The normal physical
checker still validates every subsequent action. No physics or certificate oracle
is available to repair(). No reference sequence, semantic role table or validation
outcome is in the supplied development evidence. Keep implementation small/efficient.
'''


def admission(before, after):
    b=[r for _,_,r in before];a=[r for _,_,r in after]
    success=all(not x['success'] or y['success'] for x,y in zip(b,a))
    paths=all(not(x['success'] and y['success']) or len(y['actions'])<=len(x['actions']) for x,y in zip(b,a))
    recovery=[nearest_evidence(c,r) for c,t,r in after if t=='seeded']
    nearest=bool(recovery) and all(x['nearest_verified'] and not x['checks_refunded'] for x in recovery)
    no_errors=not any(r.get('error') or any(z.get('error') for z in r['retrievals']) for r in a)
    cost=score(a)['checks']<score(b)['checks']
    return success and paths and nearest and no_errors and cost, dict(
        success_nonregression=success,final_path_nonregression=paths,nearest_prefix_recovery=nearest,
        no_errors=no_errors,checks_improve=cost,before=score(b),after=score(a),recovery=recovery)


def run():
    folder=ROOT/'outputs/learning'
    if folder.exists():raise FileExistsError('Learning round already started. Audit before resuming.')
    folder.mkdir(parents=True)
    index=read(ROOT/'outputs/input_audit/development_cases.json')
    parent=read(ROOT/'memory/banks/S3.json')
    progress('development_baseline',new_model_calls=0,evaluation_started=False)
    baseline=suite(index['development'],parent,folder/'baseline_development')
    baseline_val=suite(index['validation'],parent,folder/'baseline_validation')
    prompt_base=INSTRUCTIONS+EXTRA+'\nRETAINED PROCEDURES:\n'+json.dumps(
        [{'id':s['id'],'role':parent['skill_roles'][s['id']],'triggers':s['triggers'],'source':s['source']}
         for s in parent['skills']],separators=(',',':'))+'\nACTUAL DEVELOPMENT EVIDENCE:\n'+json.dumps(
        [compact(c,t,r) for c,t,r in baseline if t=='seeded'],separators=(',',':'))
    attempts=[];feedback=[];selected=None
    for number in range(1,4):
        path=folder/('candidate_%02d'%number);start=time.monotonic()
        prompt=prompt_base+'\nDEVELOPMENT FEEDBACK FROM EARLIER CANDIDATES:\n'+json.dumps(feedback,separators=(',',':'))
        write(path/'started.json',{'model':MODEL,'effort':EFFORT,'input_chars':len(prompt)})
        progress('skill_proposal',candidate=number,new_model_calls=number,evaluation_started=False)
        provider=CodexCLIProvider(path/'llm',model=MODEL,reasoning_effort=EFFORT,timeout=120)
        record={'candidate':number,'admitted':False}
        try:
            response,metadata=provider.complete(prompt,SCHEMA,1)
            skill={k:response[k] for k in ('name','failure_signature','when_to_apply','strategy','triggers','source')}
            skill['id']='repair_'+digest(skill)[:12];skill['source_sha256']=validate_skill(skill)
            skill['provenance']={'model':MODEL,'reasoning_effort':EFFORT,'live_response_sha256':digest(response),
                'handwritten_repair':False,'guided_diagnosis':True,'heldout_seen':False,'validation_feedback_used':False}
            write(path/'skill.json',skill)
            trial=copy.deepcopy(parent);trial.pop('bank_sha256');trial['version']='S4_candidate_%02d'%number
            trial['skills'].append(skill);trial['skill_roles'][skill['id']]='restore';trial['bank_sha256']=digest(trial)
            write(path/'bank.json',trial)
            after=suite(index['development'],trial,path/'development')
            ok,checks=admission(baseline,after)
            record.update(skill_id=skill['id'],metadata=metadata,development=checks,syntax_ok=True)
            feedback.append({'source':skill['source'],'development_admission':checks})
            if ok:selected=(skill,trial,record)
        except Exception as exc:
            record.update(error={'type':type(exc).__name__,'message':str(exc)},syntax_ok=False)
            feedback.append(record['error'])
        record['elapsed_seconds']=time.monotonic()-start;attempts.append(record);write(path/'review.json',record)
        print(json.dumps({k:v for k,v in record.items() if k!='metadata'}),flush=True)
        if selected:break
    admitted=False;validation=None;skills=parent['skills'];roles=dict(parent['skill_roles'])
    if selected:
        skill,trial,record=selected
        progress('independent_validation',new_model_calls=len(attempts),evaluation_started=False)
        after_val=suite(index['validation'],trial,folder/'selected_validation')
        admitted,validation=admission(baseline_val,after_val)
        if admitted:
            skill['validation']=validation;skills=[*skills,skill];roles[skill['id']]='restore';record['admitted']=True
        write(folder/('candidate_%02d'%record['candidate'])/'review.json',record)
    bank=copy.deepcopy(parent);bank.pop('bank_sha256');bank.update(version='S4',
        created_utc=datetime.now(timezone.utc).isoformat(),parent_sha256=parent['bank_sha256'],skills=skills,skill_roles=roles,
        provenance={'kind':'Validated live-code recovery revision in shared composed host','admitted':admitted,
                    'old_records_unchanged':True,'heldout_seen':False})
    bank['bank_sha256']=digest(bank);write(ROOT/'memory/banks/S4.json',bank);SkillBank(bank)
    ledger={'status':'complete','admitted':admitted,'attempts':attempts,'validation':validation,
            'model':MODEL,'reasoning_effort':EFFORT,'limits':LIMITS,
            'before_bank_sha256':parent['bank_sha256'],'after_bank_sha256':bank['bank_sha256'],
            'skill_count_before':len(parent['skills']),'skill_count_after':len(bank['skills']),
            'old_records_unchanged':bank['skills'][:len(parent['skills'])]==parent['skills'],
            'validation_feedback_used_for_proposal':False,'heldout_seen':False,'weights_changed':False,
            'before_runtime_equals_after_runtime':True}
    write(folder/'ledger.json',ledger);write(ROOT/'outputs/final_learning_ledger.json',ledger)
    progress('development_complete',admitted=admitted,new_model_calls=len(attempts),evaluation_started=False)
    print(json.dumps({k:v for k,v in ledger.items() if k!='attempts'}),flush=True)


if __name__=='__main__':run()

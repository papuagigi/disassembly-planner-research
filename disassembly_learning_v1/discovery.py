"""LLM repair proposal, execution validation, and append-only memory admission.

The coding agent never supplies the learned repair source. Actual provider
responses, rejected candidates, development rollouts and admission decisions are
retained. Discovery/validation expenditure is separate from held-out inference.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import time

from disassembly_mujoco.agent import CodexCLIProvider
from disassembly_recovery import library_functions
from disassembly_recovery.common import prepare_shared
from .memory import FEATURES,SkillBank,create_bank,digest,write,validate_skill

ROOT=Path(__file__).resolve().parent
MODEL='gpt-6-luna';EFFORT='low'
LIMITS=dict(max_calls=8,max_checks=120,max_steps=10000000,timeout_seconds=480.,
            max_checkpoints=128,max_restores=256)
SCHEMA={'type':'object','properties':{
    **{k:{'type':'string'}for k in ['name','failure_signature','when_to_apply','strategy','source','rationale']},
    'triggers':{'type':'array','minItems':1,'items':{'type':'string','enum':list(FEATURES)}}},
    'required':['name','failure_signature','when_to_apply','strategy','triggers','source','rationale'],
    'additionalProperties':False}
INSTRUCTIONS='''You are a procedural-memory discovery actor for selective disassembly of anonymous synthetic 3D OBJ assemblies.
Inspect actual failed physical checks and current baseline search code. Propose one reusable executable repair,
not a case-specific sequence. The coordinator runs it in MuJoCo and admits it only after validation.
Return JSON containing compact failure signature, applicability, strategy, observed-feature triggers and Python source.
Required function: repair(observation,candidates,history,checkpoints,model_order).
Return {'ordered_actions': list_of_action_dicts, 'restore_handle': existing_handle_or_empty_string}.
candidates is the current complete legal candidate set already ordered by the baseline heuristic.
Each action has part_id and direction; directions are +x,-x,+y,-y,+z,-z. Omitted actions are appended: ranking is soft.
observation contains target_id, remaining_parts(id,bounds,center,fixed,mass,allowed_directions), support_edges,
state_key, current_state_feedback/history_feedback, remaining_checks, recovery(checkpoint metadata).
history records actual checks with part_id,direction,reason,blockers,valid,committed,physical_state_key_before.
checkpoints contain handle,state_key,remaining_parts,removed_count. Restore is hypothetical state rollback, never refunds budget.
Use geometry, contact relations and failure signatures available at runtime. Never hard-code numeric part IDs,
case names, coordinate-specific thresholds or a reference removal sequence. IDs are strings and randomly assigned.
The initial target probes cover six directions; different exit directions can have different blocker sets.
Past state collisions are hints only, not proof at a new state. Fixed blockers cannot be removed.
It is often useful to commit to an economical exit direction, then resolve blockers recursively using available evidence.
But choose your repair from the supplied failure evidence; do not assume this suggestion is always correct.
Preserve supports needed by target-supported loads. Removing a falling load is not automatically a repair.
Do not call tools, files, imports, physics or API methods. You only return executable pure data-processing code.
Allowed: functions, loops, recursion, lambdas, lists/dicts/sets, literals, basic public methods and safe builtins.
Builtins: abs,min,max,sum,len,range,enumerate,zip,list,tuple,set,frozenset,dict,sorted,all,any,bool,int,float,str,round,reversed.
Unavailable: isinstance,type,exceptions,classes,annotations,fstrings,private attributes,slice assignment,subscript +=.
Function defaults must be literals. Use x[i]=x[i]+1. All arithmetic must remain finite within1e12.
Keep code efficient under150000 opcodes per use and0.3sec. Model ordering is an optional tie-break, empty when rankOFF.
Choose triggers only from the observed-feature registry. All selected triggers must match for retrieval.
Success first, then fewer irrelevant removals, failed physical checks and model calls. Do not alter physics or validation rules.
'''

def compact_episode(r):
    # Anonymous geometric task data only; no file paths, role table, certificate or reference order.
    observation=copy.deepcopy(r['initial_observation'])
    for p in observation.get('remaining_parts',[]):
        for k in list(p):
            if k not in {'id','bounds','center','mass','fixed','allowed_directions'}:p.pop(k)
    return {'initial_observation':observation,'success':r['success'],
        'termination':r['termination'],'checker_calls':r['checker_calls'],
        'actions':[{k:a.get(k)for k in ['part_id','direction']}for a in r.get('actions',[])],
        'failed_checks':[ {k:t.get(k) for k in ['part_id','direction','reason','blockers',
           'valid','committed','physical_state_key_before','stability']}for t in r['trace']if not t.get('valid')][:100],
        'note':'An action-check failure can be training evidence even when the overall target recovery eventually succeeds.'}

def solve_case(case,bank,folder):
    from .controller import solve
    state,obs,reg=prepare_shared(case,max_checks=120)
    result=solve(case,None,SkillBank(bank),llm_rank=False,initial_state=state,
                 initial_observation=obs,recovery_state=reg,**LIMITS)
    write(Path(folder)/'result.json',result);return result

def score(results):
    return {'successes':sum(bool(r['success'])for r in results),
            'checks':sum(r['checker_calls']for r in results),
            'failed_checks':sum(sum(not t.get('valid')for t in r['trace'])for r in results),
            'committed':sum(sum(bool(t.get('committed'))for t in r['trace'])for r in results)}

def acceptable(before,after):
    a,b=score(before),score(after)
    no_regression=all(not x['success'] or y['success'] for x,y in zip(before,after))
    no_extra_removal=all(not(x['success']and y['success']) or len(y['actions'])<=len(x['actions'])for x,y in zip(before,after))
    successful_pairs=[(x,y)for x,y in zip(before,after)if x['success']and y['success']]
    less_success_cost=bool(successful_pairs)and sum(y['checker_calls']for x,y in successful_pairs)<sum(x['checker_calls']for x,y in successful_pairs)
    return no_regression and no_extra_removal and not any(r.get('error')for r in after) and \
           (b['successes']>a['successes'] or less_success_cost)

def bootstrap():
    p=ROOT/'memory/banks/S0.json'
    if not p.exists():create_bank(p,'S0',provenance={'kind':'Frozen pre-existing recovery procedures; no learned repair entries.'})
    return p

def learn_round(round_index,development_cases,validation_cases,parent_path,max_candidates=3):
    folder=ROOT/'outputs/learning'/('round_%02d'%round_index)
    if (folder/'admission.json').exists():raise FileExistsError('Learning round already retained')
    parent=json.loads(Path(parent_path).read_text())
    base_results=[solve_case(c,parent,folder/'baseline_development'/('case_%02d'%i))for i,c in enumerate(development_cases,1)]
    baseline_validation=[solve_case(c,parent,folder/'baseline_validation'/('case_%02d'%i))for i,c in enumerate(validation_cases,1)]
    baseline_score=score(baseline_validation);attempts=[];selected=None
    previous=[]
    for index in range(1,max_candidates+1):
        attempt=folder/('candidate_%02d'%index);started=time.monotonic()
        prompt=INSTRUCTIONS+'\nBASELINE PROCEDURES:\n'+Path(library_functions.__file__).read_text()+\
            '\nACTUAL DEVELOPMENT FAILURE EVIDENCE:\n'+json.dumps([compact_episode(r)for r in base_results],ensure_ascii=False)+\
            '\nCURRENT REUSABLE REPAIRS:\n'+json.dumps([{k:s[k]for k in ['name','failure_signature','when_to_apply','strategy','triggers','source']}for s in parent['skills']],ensure_ascii=False)+\
            '\nPREVIOUS CANDIDATE FEEDBACK:\n'+json.dumps(previous,ensure_ascii=False)
        provider=CodexCLIProvider(attempt/'llm',model=MODEL,reasoning_effort=EFFORT,timeout=120)
        try:
            response,metadata=provider.complete(prompt,SCHEMA,1)
            skill={k:response[k]for k in ['name','failure_signature','when_to_apply','strategy','triggers','source']}
            skill['id']='repair_'+digest(skill)[:12]
            skill['source_sha256']=validate_skill(skill)
            skill['provenance']={'round':round_index,'candidate':index,'response_sha256':digest(response),
                'model':MODEL,'reasoning_effort':EFFORT,'development_source_count':len(base_results)}
            write(attempt/'skill.json',skill)
            trial_bank=copy.deepcopy(parent);trial_bank.pop('bank_sha256');trial_bank['skills'].append(skill)
            trial_bank['version']='candidate_r%d_c%d'%(round_index,index);trial_bank['bank_sha256']=digest(trial_bank)
            candidate_dev=[solve_case(c,trial_bank,attempt/'development'/('case_%02d'%i))for i,c in enumerate(development_cases,1)]
            ds=score(candidate_dev);bs=score(base_results)
            # Candidate exploration uses development feedback only. Validation is not shown back to proposal actors.
            development_ok=acceptable(base_results,candidate_dev)
            record={'candidate':index,'skill_id':skill['id'],'metadata':metadata,'development_score':ds,
                'baseline_development_score':bs,'development_improves':development_ok,
                'elapsed_seconds':time.monotonic()-started,'syntax_ok':True}
            if development_ok:
                selected=(skill,trial_bank,record);record['selected_for_validation']=True
            else:record['selected_for_validation']=False
            previous.append({'rationale':response['rationale'],'source':response['source'],
                'development_score':ds,'baseline_score':bs,
                'failure_evidence':[compact_episode(r)for r in candidate_dev]})
        except Exception as exc:
            record={'candidate':index,'syntax_ok':False,'error':{'type':type(exc).__name__,'message':str(exc)},
                    'elapsed_seconds':time.monotonic()-started}
            previous.append({'candidate_error':record['error']})
        attempts.append(record);write(attempt/'review.json',record)
        if selected:break
    admitted=False;new_path=Path(parent_path);validation=[];validation_score=None
    if selected:
        skill,trial_bank,record=selected
        validation=[solve_case(c,trial_bank,folder/'selected_validation'/('case_%02d'%i))for i,c in enumerate(validation_cases,1)]
        validation_score=score(validation)
        admitted=acceptable(baseline_validation,validation)
        if admitted:
            skill['validation']={'baseline':baseline_score,'candidate':validation_score,
                                  'criteria':'No success regression and strictly more success or fewer checks.'}
            new_path=ROOT/'memory/banks'/('learned_round_%02d.json'%round_index)
            create_bank(new_path,'learned_round_%02d'%round_index,[*parent['skills'],skill],parent=parent['bank_sha256'],
                        provenance={'admission':str((folder/'admission.json').relative_to(ROOT)),
                            'validation_feedback_returned_to_proposer':False})
    admission={'round':round_index,'admitted':admitted,'parent_bank_sha256':parent['bank_sha256'],
        'result_bank_path':str(new_path),'result_bank_sha256':SkillBank(new_path).sha256,
        'attempts':attempts,'baseline_validation':baseline_score,'candidate_validation':validation_score,
        'validation_feedback_used_for_proposal':False,'final_test_cases_seen':False,
        'development_cases':[str(c)for c in development_cases],'validation_cases':[str(c)for c in validation_cases]}
    write(folder/'admission.json',admission)
    return new_path,admission

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['bootstrap','probe']);a=p.parse_args()
    if a.command=='bootstrap':print(bootstrap())
    else:
        provider=CodexCLIProvider(ROOT/'outputs/provider_probe',model=MODEL,reasoning_effort=EFFORT,timeout=90)
        value,meta=provider.complete('Return exactly status ok; no tools. Synthetic3D learning study provider connectivity check.',
            {'type':'object','properties':{'status':{'type':'string','enum':['ok']}},'required':['status'],'additionalProperties':False},1)
        write(ROOT/'outputs/provider_probe/verified.json',{'response':value,'metadata':meta});print({'response':value,'provider':'codex_cli_live','model':MODEL})

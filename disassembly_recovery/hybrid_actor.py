"""LLM generator priorities + exact-state DFS + common executable repair skills.

Physics outcomes and checkpoints are obtained only through the same SharedAPI
available to the generated-code arms. Heuristic early recovery is not a proof
of an exhausted subtree; deferred nodes remain available to the search.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time

from disassembly_hybrid.graph import (ConditionalBlockingGraph, canonical_candidates,
                                      physical_state_key, action_key, DIRECTIONS)
from disassembly_hybrid.common import digest
from disassembly_mujoco.simulator import DisassemblySim
from .shared_api import SharedAPI, RecoveryBudgetLimit
from . import library_functions

SKILLS = ('support_dependency_order', 'preserve_goal_support')
SCHEMA = {'type':'object','properties':{
    'ordered_actions':{'type':'array','items':{'type':'object','properties':{
        'part_id':{'type':'string'},'direction':{'type':'string','enum':list(DIRECTIONS)}},
        'required':['part_id','direction'],'additionalProperties':False}},
    'skills':{'type':'array','items':{'type':'string','enum':list(SKILLS)}},
    'summary':{'type':'string'}},'required':['ordered_actions','skills','summary'],
    'additionalProperties':False}
INSTRUCTIONS = '''Return JSON priorities for selective disassembly of the given 3D OBJ assembly.
You choose a global reusable part/direction order and executable skill names.
The host generates a full legal candidate set, runs depth-first search, caches exact-state
outcomes, and uses the shared physics validator and checkpoint/restore API. Unknown actions
remain possible. The graph forbids only actions already rejected at this exact physical state.
Current vertical contact edges are hints about support, not guaranteed loads or future stability.
Every check/remove consumes the same physics budget. Restore changes physical state but never
refunds queries, model calls, opcodes, history, or restore allowances. It is hypothetical search.
Skills: support_dependency_order calls rank_candidates to prioritize useful blockers while
preserving alternate supports of target-supported parts. preserve_goal_support calls
recovery_hint to suggest an earlier checkpoint when the target becomes a sole supporter.
The hint is a soft early recovery heuristic; its abandoned nodes are not marked impossible.
Select zero or more skill names. Skills only reorder candidates or suggest a recorded checkpoint;
they cannot bypass the common validator or hide checker/restore costs.
Your ordering is reused after accepted steps. The host may ask again after twelve rejections or
a restoration needing changed priorities. It does not call you for every child state.
Return ordered_actions from current candidates; omitted legal actions are appended. Removed,
filtered, duplicate or malformed entries are dropped individually while valid entries survive.
Optimize successful target recovery, then fewer removals, physical queries and model calls.
Do not use tools, inspect files, run code, or infer semantic part roles from numeric IDs.
'''


class PlannerInstructionLimit(RuntimeError):
    pass


def normalize_ranking(response, candidates, previous_order=(), previous_skills=()):
    allowed = {action_key(a): a for a in candidates}
    if not isinstance(response,dict) or not isinstance(response.get('ordered_actions'),list):
        return list(previous_order), list(previous_skills), {'error':'ranking is not an object with ordered_actions list','dropped':[]}
    accepted=[];seen=set();dropped=[]
    for action in response['ordered_actions']:
        if (not isinstance(action,dict) or set(action)!={'part_id','direction'}
                or not all(isinstance(v,str) for v in action.values())):
            dropped.append({'action':action,'reason':'malformed'});continue
        key=action_key(action)
        if key not in allowed:
            dropped.append({'action':action,'reason':'removed_or_currently_filtered'});continue
        if key in seen:
            dropped.append({'action':action,'reason':'duplicate'});continue
        accepted.append(dict(allowed[key]));seen.add(key)
    accepted.extend(dict(a) for a in candidates if action_key(a) not in seen)
    selected=response.get('skills')
    if not isinstance(selected,list):
        selected=list(previous_skills)
    selected=list(dict.fromkeys(name for name in selected if isinstance(name,str) and name in SKILLS))
    return accepted,selected,{'dropped':dropped,'accepted_entries':len(seen),
                              'appended_candidates':len(candidates)-len(seen)}


def _model_sorted(candidates, model_order):
    ranks={action_key(a):i for i,a in enumerate(model_order)}
    return sorted(candidates,key=lambda a:ranks.get(action_key(a),len(ranks)))


def _frame(sim,api,context):
    key=physical_state_key(sim.export_state())
    if key in context['nodes']:
        return context['nodes'][key]
    handles=[c for c in api.checkpoints() if c['state_key']==key]
    handle=handles[0]['handle'] if handles else api.checkpoint()
    attempted={action_key(t) for t in sim.trace
               if t.get('physical_state_key_before')==key and t.get('operation')=='remove'}
    frame={'key':key,'handle':handle,'attempted':attempted}
    context['nodes'][key]=frame
    context['visited'].add(key)
    return frame


def _candidates(sim,api,context,frame):
    candidates=context['graph'].filter(frame['key'],canonical_candidates(api.snapshot()))
    return [a for a in candidates if action_key(a) not in frame['attempted']
            and context['edge_cache'].get((frame['key'],*action_key(a)),{}).get('to_state') not in context['exhausted']]


def _rank(sim,api,context,candidates,trigger):
    if context['calls']>=context['limits']['max_calls']:
        return True
    payload={'observation':api.snapshot(), 'candidate_actions':candidates,
             'previous_priority':context['model_order'], 'selected_skills':context['selected_skills'],
             'directed_graph':context['graph'].describe(physical_state_key(sim.export_state())),
             'limits':context['limits'], 'remaining_model_calls_after_this':context['limits']['max_calls']-context['calls']-1,
             'search':{'visited_states':len(context['visited']),'proven_exhausted_states':len(context['exhausted']),
                       'heuristically_deferred_states':len(context['deferred']), 'restorations':len(context['backtracks'])}}
    prompt=INSTRUCTIONS+'\nTASK AND FEEDBACK:\n'+json.dumps(payload,ensure_ascii=False)
    context['calls']+=1
    decision={'call':context['calls'],'trigger':trigger,'checks_before':sim.checks,
              'state_key':physical_state_key(sim.export_state()),'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
    context['decisions'].append(decision)
    provider=context['provider'];remaining=context['deadline']-time.monotonic()
    if remaining<=0:
        context['termination']='wall_time_budget_exhausted';return False
    old_timeout=getattr(provider,'timeout',None)
    if isinstance(old_timeout,(int,float)):provider.timeout=min(old_timeout,remaining)
    try:
        response,metadata=provider.complete(prompt,SCHEMA,context['calls'])
    except PlannerInstructionLimit:
        raise
    except Exception as exc:
        decision['provider_error']=str(exc);context['provider_error']=str(exc)
        context['termination']='provider_error';return False
    finally:
        if isinstance(old_timeout,(int,float)):provider.timeout=old_timeout
    decision.update(response=response,metadata=metadata)
    for key,value in metadata.get('usage',{}).items():
        if isinstance(value,(int,float)):context['usage'][key]=context['usage'].get(key,0)+value
    if time.monotonic()>=context['deadline']:
        context['termination']='wall_time_budget_exhausted';return False
    context['model_order'],context['selected_skills'],normalization=normalize_ranking(
        response,candidates,context['model_order'],context['selected_skills'])
    decision['normalization']=normalization
    if normalization.get('error'):decision['ranking_error']=normalization['error']
    decision['selected_skill_metadata']=[{'name':name,'function':'rank_candidates' if name==SKILLS[0] else'recovery_hint'}
                                         for name in context['selected_skills']]
    context['rejections_since_rank']=0
    context['need_restore_rank']=False
    return True


def _restore(sim,api,context,handle,reason):
    before=physical_state_key(sim.export_state());checks=sim.checks
    snapshot=api.restore(handle)
    key=physical_state_key(sim.export_state())
    event=api.export_recovery_state()['events'][-1]
    context['backtracks'].append({'from_state':before,'to_state':key,'checker_calls':sim.checks,
                                 'api_event_index':event['event_index'],'handle':handle,'reason':reason,
                                 'remaining':list(sim.remaining),'budget_refunded':False})
    assert sim.checks==checks
    # Re-rank only when a restore reveals actions absent from the global list,
    # or the twelve-rejection threshold has been reached.
    known={action_key(a)for a in context['model_order']}
    context['need_restore_rank']=context['rejections_since_rank']>=12 or any(
        action_key(a)not in known for a in canonical_candidates(snapshot))
    return _frame(sim,api,context)


def _search(sim,api,context):
    context['stack']=[_frame(sim,api,context)]
    while not sim.success:
        if time.monotonic()>=context['deadline']:
            context['termination']='wall_time_budget_exhausted';break
        if sim.checks>=context['limits']['max_checks']:
            context['termination']='check_budget_exhausted';break
        if not context['stack']:
            pending=next((key for key in context['deferred'] if key not in context['exhausted']),None)
            if pending is None:
                context['termination']='search_frontier_exhausted';break
            saved=context['deferred'].pop(pending)
            restored=_restore(sim,api,context,saved['handle'],'resume_heuristically_deferred_branch')
            context['stack']=[restored]
        frame=context['stack'][-1]
        candidates=_candidates(sim,api,context,frame)
        if not candidates:
            context['exhausted'].add(frame['key']);context['deferred'].pop(frame['key'],None)
            context['stack'].pop()
            if context['stack']:
                _restore(sim,api,context,context['stack'][-1]['handle'],'dfs_exhausted_frontier')
            continue
        trigger=('initial_global_priority' if not context['calls'] else
                 'twelve_new_rejections' if context['rejections_since_rank']>=12 else
                 'restored_state_needs_priority' if context['need_restore_rank'] else None)
        if trigger and not _rank(sim,api,context,candidates,trigger):break
        observation=api.snapshot()
        if 'preserve_goal_support' in context['selected_skills']:
            checkpoints=api.checkpoints();hint=library_functions.recovery_hint(observation,checkpoints)
            pair=(frame['key'],hint)
            used=bool(hint and pair not in context['used_recovery_hints'] and
                      any(c['handle']==hint and c['state_key']!=frame['key'] for c in checkpoints))
            context['skill_calls'].append({'name':'preserve_goal_support','function':'recovery_hint',
                'state_key':frame['key'],'checks_before':sim.checks,'checks_after':sim.checks,
                'llm_call':context['calls'],'selected_by_model':True,'returned_handle':hint,'applied':used,
                'semantics':'soft early recovery; not an impossibility proof'})
            if used:
                context['used_recovery_hints'].add(pair)
                context['deferred'][frame['key']]=frame
                destination=_restore(sim,api,context,hint,'skill_soft_support_risk')
                matching=next((i for i,n in enumerate(context['stack']) if n['key']==destination['key']),None)
                if matching is None:context['stack']=[destination]
                else:context['stack']=context['stack'][:matching+1]
                continue
        ordered=_model_sorted(candidates,context['model_order'])
        if 'support_dependency_order' in context['selected_skills']:
            returned=library_functions.rank_candidates(observation,ordered,sim.trace,context['model_order'])
            allowed={action_key(a):a for a in ordered};seen=set();ranked=[]
            for action in returned:
                key=action_key(action)
                if key in allowed and key not in seen:ranked.append(allowed[key]);seen.add(key)
            ranked.extend(a for a in ordered if action_key(a)not in seen)
            ordered=ranked
            context['skill_calls'].append({'name':'support_dependency_order','function':'rank_candidates',
                'state_key':frame['key'],'checks_before':sim.checks,'checks_after':sim.checks,
                'llm_call':context['calls'],'selected_by_model':True,'candidate_count':len(candidates),
                'first_action':ordered[0] if ordered else None,'hard_pruning':False})
        # A deferred successor is tried after other available alternatives; it
        # remains legal and can be resumed if those alternatives exhaust.
        ordered.sort(key=lambda a:context['edge_cache'].get((frame['key'],*action_key(a)),{}).get('to_state') in context['deferred'])
        action=ordered[0];frame['attempted'].add(action_key(action));before=sim.checks
        result=api.remove(**action)
        assert sim.checks==before+1
        context['graph'].add(frame['key'],result)
        childkey=physical_state_key(sim.export_state())if result.get('committed')else None
        context['edge_cache'][(frame['key'],*action_key(action))]={'valid':bool(result.get('valid')),'to_state':childkey}
        sim.trace[-1].update(search_state_key=frame['key'],search_depth=len(context['stack'])-1)
        if result.get('committed'):
            context['explored_actions'].append({**copy.deepcopy(sim.actions[-1]),'checker_call':sim.checks,
                                                'from_state':frame['key'],'to_state':childkey})
            if sim.success:
                context['termination']='goal_reached';break
            if childkey in context['exhausted']:
                _restore(sim,api,context,frame['handle'],'cached_exhausted_successor')
            elif childkey in {n['key']for n in context['stack']}:
                _restore(sim,api,context,frame['handle'],'active_state_cycle_guard')
            else:
                context['deferred'].pop(childkey,None)
                context['stack'].append(_frame(sim,api,context))
        else:
            context['rejections_since_rank']+=1


def solve_hybrid(case_path,provider,initial_state=None,initial_observation=None,recovery_state=None,
                 max_calls=8,max_checks=120,max_steps=10000000,timeout_seconds=480,
                 max_checkpoints=128,max_restores=256):
    started=time.monotonic()
    limits={'max_calls':max_calls,'max_checks':max_checks,'max_steps':max_steps,
            'timeout_seconds':timeout_seconds,'max_checkpoints':max_checkpoints,'max_restores':max_restores}
    if any(type(v)is not int or v<1 for v in (max_calls,max_checks,max_steps,max_checkpoints,max_restores)):
        raise ValueError('count limits must be positive integers')
    if isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float)) or not math.isfinite(timeout_seconds) or timeout_seconds<=0:
        raise ValueError('timeout_seconds must be positive and finite')
    sim=DisassemblySim(case_path,max_checks=max_checks,state=initial_state)
    api=SharedAPI(sim,recovery_state=recovery_state,max_checks=max_checks,
                  max_checkpoints=max_checkpoints,max_restores=max_restores,raise_goal=False)
    initial_event_count=len(api.export_recovery_state()['events'])
    observation=copy.deepcopy(initial_observation)if initial_observation is not None else api.snapshot()
    context={'limits':limits,'provider':provider,'deadline':started+timeout_seconds,
             'calls':0,'steps':0,'decisions':[],'skill_calls':[],'usage':{},'model_order':[],
             'selected_skills':[],'nodes':{},'visited':set(),'exhausted':set(),'deferred':{},
             'used_recovery_hints':set(),'backtracks':[],'explored_actions':[],
             'graph':ConditionalBlockingGraph(),'edge_cache':{},'rejections_since_rank':0,
             'need_restore_rank':False,'provider_error':None,'termination':'not_started'}
    for record in sim.trace:
        key=record.get('physical_state_key_before')
        if key:
            context['graph'].add(key,record)
            if record.get('committed'):
                context['edge_cache'][(key,*action_key(record))]={'valid':True,'to_state':record.get('physical_state_key_after')}
    traced_files={str(Path(__file__).resolve()),str(Path(library_functions.__file__).resolve())}
    def instruction_trace(frame,event,arg):
        if frame.f_code.co_filename not in traced_files:return None
        if event=='call':frame.f_trace_opcodes=True;frame.f_trace_lines=False
        elif event=='opcode':
            if context['steps']>=max_steps:raise PlannerInstructionLimit('planner/library instruction budget exhausted')
            context['steps']+=1
        return instruction_trace
    previous=sys.gettrace();error=None
    try:
        sys._getframe().f_trace_opcodes=True;sys.settrace(instruction_trace)
        _search(sim,api,context)
    except PlannerInstructionLimit as exc:
        context['termination']='execution_step_budget_exhausted';error={'type':type(exc).__name__,'message':str(exc)}
    except RecoveryBudgetLimit as exc:
        context['termination']='recovery_budget_exhausted';error={'type':type(exc).__name__,'message':str(exc)}
    except Exception as exc:
        context['termination']='planner_error';error={'type':type(exc).__name__,'message':str(exc)}
    finally:sys.settrace(previous)
    late=time.monotonic()>context['deadline'];success=bool(sim.success)and not late
    if success:context['termination']='goal_reached'
    elif late and context['termination']!='provider_error':context['termination']='wall_time_budget_exhausted'
    recorded={a['checker_call']for a in context['explored_actions']}
    for t in sim.trace:
        if t.get('committed')and t['checker_call']not in recorded:
            context['explored_actions'].append({'part_id':t['part_id'],'direction':t['direction'],
                'checker_call':t['checker_call'],'stability':t.get('stability'),
                'from_state':t.get('physical_state_key_before'),'to_state':t.get('physical_state_key_after'),
                'preexisting_or_interrupted_record':True})
    recovery=api.export_recovery_state()
    logged_restores={event['api_event_index'] for event in context['backtracks']}
    for event in recovery['events'][initial_event_count:]:
        if event['operation']=='restore' and event.get('restored') and event['event_index'] not in logged_restores:
            checkpoint=recovery['checkpoints'][event['handle']]
            context['backtracks'].append({'from_state':event['state_key_before'],'to_state':event['state_key_after'],
                'checker_calls':event['checks_after'],'api_event_index':event['event_index'],
                'handle':event['handle'],'reason':'interrupted_bookkeeping',
                'remaining':checkpoint['metadata']['remaining_parts'],'budget_refunded':False})
    context['backtracks'].sort(key=lambda event:event['api_event_index'])
    return {'case_id':sim.case['id'],'case_path':str(Path(case_path).resolve()),'method':'graph_llm_dfs_library',
        'success':success,'status':'PASS'if success else'UNKNOWN','termination':context['termination'],
        'initial_observation':observation,'initial_observation_sha256':digest(observation),'observation':api.snapshot(),
        'state':sim.export_state(),'recovery_state':recovery,'trace':copy.deepcopy(sim.trace),'actions':copy.deepcopy(sim.actions),
        'backtracks':context['backtracks'],'explored_actions':context['explored_actions'],
        'decisions':context['decisions'],'skill_calls':context['skill_calls'],'llm_calls':context['calls'],
        'checker_calls':sim.checks,'execution_steps':context['steps'],'token_usage':context['usage'],
        'elapsed_seconds':time.monotonic()-started,'limits':limits,'provider_error':context['provider_error'],
        'error':error,'goal_reached_after_deadline':bool(sim.success)and late,
        'removed_count':len(sim.actions)if success else None,'accepted_removals':len(sim.actions),
        'library_sha256':hashlib.sha256(Path(library_functions.__file__).read_bytes()).hexdigest(),
        'search':{'visited_states':len(context['visited']),'exhausted_states':len(context['exhausted']),
                  'deferred_states':len(context['deferred']),'cached_edges':len(context['edge_cache']),
                  'algorithm':'exact-state DFS with reusable LLM global priorities and soft support-risk deferral',
                  'complete_under_finite_budget':False,'heuristic_recovery_is_not_impossibility_proof':True}}

"""C: fixed Graph/LLM-ranked DFS with the same explicit S5 frontier as B.

C invokes stored bookkeeping automatically; B must call it from generated code.
Both execute physical operations through the unchanged v3 SharedAPI.
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
from disassembly_hybrid import graph as graph_module
from disassembly_hybrid.common import neutral_observation_hash
from disassembly_real_v2.simulator import FullDisassemblySim
from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_recovery.shared_api import RecoveryBudgetLimit


SCHEMA = {'type': 'object', 'properties': {
    'ordered_actions': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'part_id': {'type': 'string'}, 'direction': {'type': 'string', 'enum': list(DIRECTIONS)}},
        'required': ['part_id', 'direction'], 'additionalProperties': False}},
    'summary': {'type': 'string'}},
    'required': ['ordered_actions', 'summary'], 'additionalProperties': False}

INSTRUCTIONS = '''Return JSON priorities for full disassembly of the supplied 3D OBJ observation.
Return ordered_actions and a short summary. Your role is candidate ranking only.
The fixed controller generates legal candidates, filters already rejected exact-state actions,
and performs depth-first search through the common check/remove/checkpoint/restore API.
Unknown actions remain candidates. Support contacts are current geometric hints, not future proof.
C automatically invokes the frozen S5 executable bank, including exact-state frontier bookkeeping.
B has the same bank through explicit generated-policy calls; A has no library.
This experiment has no ranking-OFF condition. Your role in C is online priorities only.
Ordering and recovery skills compose as separate roles: recovery never overwrites earlier action priority.
Checkpoint support_edges and accepted_action_prefix are observed past state context, not a future stability oracle.
You cannot enable or disable skills. Your order is supplied to that bank: its priority rules
may dominate your order and use it only to resolve ties. Do not claim your ranking overrides it.
The controller applies deterministic recovery before considering a model call. It protects
all meaningful skill priorities, including category, needed-part height, and direction.
Your order can break genuinely equal semantic-priority ties only; arbitrary numeric IDs
are not protected preferences. No ambiguity means no model call. It reuses priorities
after accepted steps and may refresh after twelve rejected actions or new tied candidates.
Every physics check or removal consumes the shared allowance; restore never refunds any cost.
Removed, filtered, malformed and duplicate returned entries are dropped individually, while
omitted legal candidates remain available. Optimize full-sequence success, then fewer failed checks/calls.
The goal is n-1 verified removals leaving at most one product part; an anchored base remains.
snapshot.target_id is a deterministic compatibility focus, not the success condition:
initial_focus_id while present, then the first remaining nonfixed string ID in sorted order.
Removing it does not finish or reset the episode, costs, checkpoints, or S5 frontier ledger.
The controller stops only at the full-disassembly goal shown by remaining_part_count <= 1.
No model weights change. There is no cross-evaluation episode learning or bank modification.
Do not use tools, inspect files, or infer semantic part roles from numeric identifiers.
'''


class PlannerInstructionLimit(RuntimeError):
    pass


def normalize_order(proposed, candidates, previous_order=()):
    """Complete a possibly partial ranking without deleting any legal candidate."""
    allowed = {action_key(a): a for a in candidates}
    information = {'dropped': [], 'accepted_entries': 0, 'appended_candidates': 0}
    if not isinstance(proposed, list):
        information['error'] = 'ordered_actions is not a list'
        proposed = list(previous_order)
    accepted, seen = [], set()
    for action in proposed:
        if (not isinstance(action, dict) or set(action) != {'part_id', 'direction'} or
                not all(isinstance(v, str) for v in action.values())):
            information['dropped'].append({'action': action, 'reason': 'malformed'})
            continue
        key = action_key(action)
        if key not in allowed:
            information['dropped'].append({'action': action, 'reason': 'removed_or_currently_filtered'})
        elif key in seen:
            information['dropped'].append({'action': action, 'reason': 'duplicate'})
        else:
            accepted.append(dict(allowed[key]))
            seen.add(key)
    information['accepted_entries'] = len(seen)
    information['appended_candidates'] = len(candidates) - len(seen)
    accepted.extend(dict(a) for a in candidates if action_key(a) not in seen)
    return accepted, information


def _model_sorted(candidates, order):
    ranks = {action_key(a): i for i, a in enumerate(order)}
    return sorted(candidates, key=lambda a: ranks.get(action_key(a), len(ranks)))


def _frame(sim, api, ctx):
    key = physical_state_key(sim.export_state())
    if key in ctx['nodes']:
        return ctx['nodes'][key]
    checkpoints = [c for c in api.checkpoints() if c['state_key'] == key]
    handle = checkpoints[0]['handle'] if checkpoints else api.checkpoint()
    attempted = {action_key(t) for t in sim.trace if t.get('physical_state_key_before') == key
                 and t.get('operation') == 'remove'}
    frame = {'key': key, 'handle': handle, 'attempted': attempted}
    ctx['nodes'][key] = frame
    ctx['visited'].add(key)
    return frame


def _candidates(api, ctx, frame):
    candidates = ctx['graph'].filter(frame['key'], canonical_candidates(api.snapshot()))
    return [a for a in candidates if action_key(a) not in frame['attempted'] and
            ctx['edge_cache'].get((frame['key'], *action_key(a)), {}).get('to_state') not in ctx['exhausted']]


def _rank(sim, api, ctx, candidates, trigger, policy=None):
    if not ctx['llm_rank'] or ctx['calls'] >= ctx['limits']['max_calls']:
        return True
    payload = {'observation': api.snapshot(), 'candidate_actions': candidates,
               'previous_priority': ctx['model_order'],
               'directed_graph': ctx['graph'].describe(physical_state_key(sim.export_state())),
               'limits': ctx['limits'],
               'remaining_model_calls_after_this': ctx['limits']['max_calls'] - ctx['calls'] - 1,
               'skill_activation': 'fixed bank application; model has no activation choice',
               'protected_skill_priorities': copy.deepcopy(policy or {}),
               'search': {'visited_states': len(ctx['visited']), 'proven_exhausted_states': len(ctx['exhausted']),
                          'heuristically_deferred_states': len(ctx['deferred']), 'restorations': len(ctx['backtracks'])}}
    prompt = INSTRUCTIONS + '\nTASK AND FEEDBACK:\n' + json.dumps(payload, ensure_ascii=False)
    ctx['calls'] += 1
    decision = {'call': ctx['calls'], 'trigger': trigger, 'checks_before': sim.checks,
                'state_key': physical_state_key(sim.export_state()),
                'api_event_index_before':len(api.export_recovery_state()['events']),
                'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                'ranking_policy': copy.deepcopy(policy or {}),
                'recovery_preflight_completed': True}
    ctx['decisions'].append(decision)
    remaining = ctx['deadline'] - time.monotonic()
    if remaining <= 0:
        ctx['termination'] = 'wall_time_budget_exhausted'
        return False
    provider = ctx['provider']
    timeout = getattr(provider, 'timeout', None)
    if isinstance(timeout, (int, float)):
        provider.timeout = min(timeout, remaining)
    try:
        response, metadata = provider.complete(prompt, SCHEMA, ctx['calls'])
    except PlannerInstructionLimit:
        raise
    except Exception as exc:
        decision['provider_error'] = str(exc)
        ctx['provider_error'] = str(exc)
        ctx['termination'] = 'provider_error'
        return False
    finally:
        if isinstance(timeout, (int, float)):
            provider.timeout = timeout
    decision.update(response=response, metadata=metadata)
    for key, value in metadata.get('usage', {}).items():
        if isinstance(value, (int, float)):
            ctx['usage'][key] = ctx['usage'].get(key, 0) + value
    if time.monotonic() >= ctx['deadline']:
        ctx['termination'] = 'wall_time_budget_exhausted'
        return False
    proposed = response.get('ordered_actions') if isinstance(response, dict) else None
    ctx['model_order'], information = normalize_order(proposed, candidates, ctx['model_order'])
    decision['normalization'] = information
    if information.get('error'):
        decision['ranking_error'] = information['error']
    ctx['rejections_since_rank'] = 0
    ctx['need_restore_rank'] = False
    return True


def _invoke_bank(ctx, observation, candidates, history, checkpoints, record, phase='prepare', prepared=None):
    """Trusted accounting boundary, excluded from planner opcode counting.

Bank internals enforce and report their own remaining allowance. This wrapper
does not make planning decisions; it atomically retains that cost and result.
"""
    setter = getattr(ctx['bank'], 'set_execution_budget', None)
    remaining = ctx['limits']['max_steps'] - ctx['steps'] - ctx['bank_steps']
    if callable(setter):
        setter(max(0, remaining))
    try:
        if phase=='prepare':
            result=ctx['bank'].prepare_plan(copy.deepcopy(observation),copy.deepcopy(candidates),
                                           copy.deepcopy(history),copy.deepcopy(checkpoints))
        else:
            result=ctx['bank'].finish_plan(prepared,copy.deepcopy(observation),copy.deepcopy(history),
                                          copy.deepcopy(checkpoints),copy.deepcopy(ctx['model_order']))
    except PlannerInstructionLimit:
        raise
    except Exception as exc:
        result = {'ordered_actions': candidates, 'restore_handle': '', 'skill_id': None,
                  'retrieval': {}, 'execution_steps': 0,
                  'error': {'type': type(exc).__name__, 'message': str(exc)}}
    if not isinstance(result, dict):
        result = {'error': {'type': 'BankContractError', 'message': 'bank.apply did not return a dict'}}
    total_steps = result.get('execution_steps', 0)
    previous_steps=record.get('execution_steps',0) if phase=='finish' else 0
    steps=total_steps-previous_steps
    if type(steps) is not int or steps < 0:
        raise ValueError('bank execution_steps must be a nonnegative integer')
    ctx['bank_steps'] += steps
    record.update(next_step=copy.deepcopy(result.get('next_step')), skill_id=result.get('skill_id'), retrieval=copy.deepcopy(result.get('retrieval', {})),
                  execution_steps=total_steps, error=copy.deepcopy(result.get('error')))
    record[phase+'_bank_steps']=steps
    record.setdefault('bank_phase_costs',[]).append({'phase':phase,'execution_steps':steps,'cumulative_execution_steps':total_steps})
    record['skill_applied'] = bool(result.get('skill_id') is not None and not result.get('error') and
                                  result.get('retrieval', {}).get('applied', True))
    if ctx['steps'] + ctx['bank_steps'] > ctx['limits']['max_steps']:
        raise PlannerInstructionLimit('aggregate controller and bank instruction budget exhausted')
    return result


def _priority_tiers(result, candidates):
    """Compose actual skill keys, retaining all meaningful fields and all actions.

The trusted bank exposes keys from its single metered execution. This controller
work is opcode-counted. An unsupported/incomplete contract disables model
ranking rather than guessing equivalence or pruning unknown actions.
"""
    contract=result.get('priority_contract') or {}
    base={};learned={};order_active=False
    for basis in contract.get('basis',[]):
        destination=base if basis.get('role')=='base' else learned
        if basis.get('role')=='order':order_active=True
        for row in basis.get('rows',[]):
            action=row.get('action',{});key=row.get('key',[])
            if isinstance(action,dict) and isinstance(key,list):
                destination[action_key(action)]=tuple(key)
    keys={}
    for action in candidates:
        pair=action_key(action)
        if pair not in base or len(base[pair])!=3 or (order_active and (pair not in learned or len(learned[pair])!=1)):
            return {},[],'incomplete_semantic_priority_contract'
        keys[pair]=(learned[pair] if order_active else ())+base[pair]
    tiers=[]
    for action in result.get('ordered_actions',[]):
        pair=action_key(action)
        if pair not in keys:return {},[],'unrecognized_skill_action'
        key=list(keys[pair])
        if not tiers or tiers[-1]['semantic_key']!=key:
            tiers.append({'semantic_key':key,'actions':[]})
        tiers[-1]['actions'].append(copy.deepcopy(action))
    if sum(len(t['actions']) for t in tiers)!=len(candidates):
        return {},[],'skill_order_not_complete'
    ordered_keys=[keys[action_key(a)] for a in result.get('ordered_actions',[])]
    if ordered_keys!=sorted(ordered_keys):
        return {},[],'neutral_skill_order_not_monotone_under_contract'
    return keys,tiers,None


def _protected_merge(ordered, model_order, keys):
    """LLM may change only arbitrary tie order, never a semantic skill key."""
    if not model_order:return list(ordered),[]
    ranks={action_key(a):i for i,a in enumerate(model_order)}
    original={action_key(a):i for i,a in enumerate(ordered)}
    merged=sorted(ordered,key=lambda a:(keys[action_key(a)],ranks.get(action_key(a),len(ranks)),original[action_key(a)]))
    rejected=[];highest=None
    for action in model_order:
        pair=action_key(action)
        if pair not in keys:continue
        key=keys[pair]
        if highest is not None and key<highest:
            rejected.append({'action':copy.deepcopy(action),'semantic_key':list(key),'preceded_by_lower_priority_key':list(highest)})
        if highest is None or key>highest:highest=key
    return merged,rejected


def _apply_bank(sim, api, ctx, candidates):
    observation = api.snapshot()
    # A single model-neutral ordering/recovery application runs first. The
    # existing S5 frontier memory is not mutated during this preparation.
    model_sorted = list(candidates)
    record = {'application_index': len(ctx['retrievals']) + 1, 'state_key': observation['state_key'],
              'checks_before': sim.checks, 'checks_after': sim.checks, 'llm_call': ctx['calls'],
              'api_event_index_before':len(api.export_recovery_state()['events']),
              'candidate_count': len(candidates), 'activation': 'fixed_controller',
              'selected_by_model': False, 'restore_applied': False}
    ctx['retrievals'].append(record)
    checkpoints=api.checkpoints()
    record['preflight_llm_calls']=ctx['calls']
    record['preflight_before_provider']=True
    result = _invoke_bank(ctx, observation, model_sorted, sim.trace, checkpoints, record)
    error_message = str((result.get('error') or {}).get('message', '')).lower()
    if (result.get('error') or {}).get('type') in ('MemoryTransportError','MemoryTransportLimit'):
        ctx['bank_error'] = copy.deepcopy(result['error'])
        ctx['termination'] = 'bank_memory_transport_rejected'
        return model_sorted, '', record
    if 'opcode limit' in error_message or 'instruction budget' in error_message:
        ctx['bank_error'] = copy.deepcopy(result['error'])
        ctx['termination'] = 'bank_execution_step_budget_exhausted'
        return model_sorted, '', record
    if 'deadline exceeded' in error_message:
        ctx['bank_error'] = copy.deepcopy(result['error'])
        ctx['termination'] = 'bank_time_budget_exhausted'
        return model_sorted, '', record
    if time.monotonic() >= ctx['deadline']:
        ctx['termination'] = 'wall_time_budget_exhausted'
        return model_sorted, '', record
    # Resolve the actual frontier proposal, including DFS-only restore hints,
    # before a provider can run. This is a charged real invocation, not preview.
    if not result.get('error'):
        result=_invoke_bank(ctx,observation,candidates,sim.trace,checkpoints,record,'finish',result)
    preflight_proposal=copy.deepcopy(result.get('next_step') or {})
    record['preflight_proposal']=preflight_proposal
    operation=preflight_proposal.get('operation')
    deterministic=('deterministic_'+operation if operation in ('restore','checkpoint','exhausted') else None)
    keys,tiers,contract_error=_priority_tiers(result,candidates)
    record['priority_contract']=copy.deepcopy(result.get('priority_contract',{}))
    attempted={tuple(a) for a in ctx['bank'].export_state().get('attempted',{}).get(observation['state_key'],[])}
    available_tiers=[]
    for tier in tiers:
        available=[a for a in tier['actions'] if action_key(a) not in attempted]
        if available:available_tiers.append({'semantic_key':tier['semantic_key'],'actions':available})
    top=available_tiers[0]['actions'] if available_tiers else []
    unknown=any(action_key(a) not in {action_key(v) for v in ctx['model_order']} for a in top)
    trigger=('initial_ambiguous_skill_tie' if not ctx['calls'] else
             'twelve_new_rejections_in_ambiguous_tie' if ctx['rejections_since_rank']>=12 else
             'new_ambiguous_skill_tie' if unknown else None)
    policy={'protected_tiers':tiers,'semantic_contract_error':contract_error,
            'top_available_tie_count':len(top),'trigger':trigger,
            'deterministic_preflight':deterministic,'before_order':copy.deepcopy(result.get('ordered_actions',[])),
            'model_can_only_break_semantically_equal_ties':True}
    record['ranking_policy']=policy
    if result.get('error'):
        policy.update(decision='skip',skip_reason='bank_error')
    elif deterministic:
        policy.update(decision='skip',skip_reason=deterministic)
    elif contract_error:
        policy.update(decision='skip',skip_reason=contract_error)
    elif len(top)<2:
        policy.update(decision='skip',skip_reason='strict_skill_priority')
    elif not ctx['llm_rank']:
        policy.update(decision='skip',skip_reason='ranking_disabled')
    elif ctx['calls']>=ctx['limits']['max_calls']:
        policy.update(decision='reuse',skip_reason='model_call_budget_exhausted')
    elif trigger:
        policy.update(decision='call',skip_reason=None)
        if not _rank(sim,api,ctx,candidates,trigger,policy):
            return model_sorted,'',record
    else:
        policy.update(decision='reuse',skip_reason='covered_ambiguous_tie')
    if keys and not deterministic and not result.get('error'):
        result['ordered_actions'],rejected=_protected_merge(result['ordered_actions'],ctx['model_order'],keys)
        policy['rejected_cross_tier_promotions']=rejected
    else:policy['rejected_cross_tier_promotions']=[]
    policy['after_order']=copy.deepcopy(result.get('ordered_actions',[]))
    record['llm_calls_after_preflight']=ctx['calls']
    # If a legitimate tie resolution changes the proposed remove, invoke only
    # the frontier again and charge it. S5 explicitly tolerates unexecuted
    # pending intents. No baseline/repair rerun or host-written ledger mutation.
    selected=next((a for a in result.get('ordered_actions',[]) if action_key(a) not in attempted),None)
    refine=bool(operation=='remove' and selected and selected!=preflight_proposal.get('action') and not result.get('error'))
    record['frontier_refinement_required']=refine
    if refine:
        record['ignored_preflight_remove_proposal']=copy.deepcopy(preflight_proposal)
        result=_invoke_bank(ctx,observation,candidates,sim.trace,checkpoints,record,'finish',result)
    error_message=str((result.get('error') or {}).get('message','')).lower()
    if (result.get('error') or {}).get('type') in ('MemoryTransportError','MemoryTransportLimit'):
        ctx['bank_error']=copy.deepcopy(result['error']);ctx['termination']='bank_memory_transport_rejected'
        return model_sorted,'',record
    if 'opcode limit' in error_message or 'instruction budget' in error_message:
        ctx['bank_error']=copy.deepcopy(result['error']);ctx['termination']='bank_execution_step_budget_exhausted'
        return model_sorted,'',record
    if 'deadline exceeded' in error_message:
        ctx['bank_error']=copy.deepcopy(result['error']);ctx['termination']='bank_time_budget_exhausted'
        return model_sorted,'',record
    # An errored learned repair may still return the valid baseline ordering.
    proposed = result.get('ordered_actions')
    ordered, information = normalize_order(proposed, model_sorted, model_sorted)
    record['normalization'] = information
    record['first_action'] = ordered[0] if ordered else None
    record['hard_pruning'] = False
    step = result.get('next_step') or {}
    record['next_step'] = copy.deepcopy(step)
    if step.get('operation') == 'remove':
        action = step.get('action')
        if action not in ordered:raise ValueError('frontier selected unavailable action')
        ordered = [action] + [a for a in ordered if a != action]
    elif step.get('operation') == 'exhausted':
        ordered = []
    elif step.get('operation') == 'checkpoint':
        ordered = []
    hint = step.get('handle', '') if step.get('operation') == 'restore' else ''
    record['returned_handle'] = hint
    if not isinstance(hint, str):
        record['restore_rejection'] = 'malformed_handle'
        hint = ''
    if record.get('skill_id') is not None:
        ctx['skill_calls'].append(record)
    return ordered, hint, record


def _restore(sim, api, ctx, handle, reason):
    before = physical_state_key(sim.export_state())
    checks = sim.checks
    observation = api.restore(handle)
    event = api.export_recovery_state()['events'][-1]
    ctx['backtracks'].append({'from_state': before, 'to_state': observation['state_key'],
                             'checker_calls': sim.checks, 'api_event_index': event['event_index'],
                             'handle': handle, 'reason': reason, 'remaining': list(sim.remaining),
                             'budget_refunded': False})
    assert sim.checks == checks
    known = {action_key(a) for a in ctx['model_order']}
    ctx['need_restore_rank'] = ctx['rejections_since_rank'] >= 12 or any(
        action_key(a) not in known for a in canonical_candidates(observation))
    return _frame(sim, api, ctx)


def _dispatch_action(ordered,proposal,edge_cache,state,deferred):
    if proposal.get('operation') == 'remove':
        action=proposal['action']
        if action not in ordered:raise ValueError('frontier proposed unavailable action')
        return action
    # Legacy fallback applies only when a bank error produced no frontier proposal.
    ordered.sort(key=lambda a: edge_cache.get((state,*action_key(a)),{}).get('to_state') in deferred)
    return ordered[0]


def _save_frontier_checkpoint(api,frame,record):
    # Same physical state reached through a commuted accepted prefix may need
    # a context-compatible checkpoint even when the fixed DFS node already exists.
    handle=api.checkpoint()
    frame['handle']=handle
    record['frontier_checkpoint_applied']=True
    record['frontier_checkpoint_handle']=handle
    record['checkpoint_api_event_index']=api.export_recovery_state()['events'][-1]['event_index']
    return handle


def _search(sim, api, ctx):
    ctx['stack'] = [_frame(sim, api, ctx)]
    while not sim.success:
        if time.monotonic() >= ctx['deadline']:
            ctx['termination'] = 'wall_time_budget_exhausted'
            break
        if sim.checks >= ctx['limits']['max_checks']:
            ctx['termination'] = 'check_budget_exhausted'
            break
        if not ctx['stack']:
            key = next((k for k in ctx['deferred'] if k not in ctx['exhausted']), None)
            if key is None:
                ctx['termination'] = 'search_frontier_exhausted'
                break
            saved = ctx['deferred'].pop(key)
            ctx['stack'] = [_restore(sim, api, ctx, saved['handle'], 'resume_heuristically_deferred_branch')]
        frame = ctx['stack'][-1]
        candidates = _candidates(api, ctx, frame)
        if not candidates:
            ctx['exhausted'].add(frame['key'])
            ctx['deferred'].pop(frame['key'], None)
            ctx['stack'].pop()
            if ctx['stack']:
                _restore(sim, api, ctx, ctx['stack'][-1]['handle'], 'dfs_exhausted_frontier')
            continue
        ordered, hint, record = _apply_bank(sim, api, ctx, candidates)
        if ctx['termination'] in ('wall_time_budget_exhausted', 'bank_execution_step_budget_exhausted',
                                  'bank_time_budget_exhausted', 'bank_memory_transport_rejected','provider_error'):
            break
        if (record.get('next_step') or {}).get('operation') == 'checkpoint':
            _save_frontier_checkpoint(api,frame,record)
            continue
        if not ordered and not hint:
            ctx['exhausted'].add(frame['key']);ctx['deferred'].pop(frame['key'],None);ctx['stack'].pop()
            if ctx['stack']:_restore(sim,api,ctx,ctx['stack'][-1]['handle'],'frontier_ledger_exhausted')
            continue
        pair = (frame['key'], hint)
        known_checkpoints = {c['handle']: c for c in api.checkpoints()}
        if hint and hint not in known_checkpoints:
            record['restore_rejection'] = 'unknown_handle'
        elif hint and known_checkpoints[hint]['state_key'] == frame['key']:
            record['restore_rejection'] = 'same_physical_state'
        elif hint and pair in ctx['used_recovery_hints']:
            record['restore_rejection'] = 'already_used_for_this_exact_state'
        elif hint:
            ctx['used_recovery_hints'].add(pair)
            ctx['deferred'][frame['key']] = frame
            destination = _restore(sim, api, ctx, hint, 'bank_soft_recovery_hint')
            record['restore_applied'] = True
            record['restore_event_index'] = ctx['backtracks'][-1]['api_event_index']
            match = next((i for i, node in enumerate(ctx['stack']) if node['key'] == destination['key']), None)
            ctx['stack'] = [destination] if match is None else ctx['stack'][:match + 1]
            continue
        action = _dispatch_action(ordered,record.get('next_step') or {},ctx['edge_cache'],frame['key'],ctx['deferred'])
        frame['attempted'].add(action_key(action))
        before = sim.checks
        result = api.remove(**action)
        assert sim.checks == before + 1
        record['executed_action'] = copy.deepcopy(action)
        record['api_event_index'] = result['api_event_index']
        ctx['graph'].add(frame['key'], result)
        childkey = physical_state_key(sim.export_state()) if result.get('committed') else None
        ctx['edge_cache'][(frame['key'], *action_key(action))] = {'valid': bool(result.get('valid')), 'to_state': childkey}
        sim.trace[-1].update(search_state_key=frame['key'], search_depth=len(ctx['stack']) - 1)
        if result.get('committed'):
            ctx['explored_actions'].append({**copy.deepcopy(sim.actions[-1]), 'checker_call': sim.checks,
                                           'from_state': frame['key'], 'to_state': childkey})
            if sim.success:
                ctx['termination'] = 'goal_reached'
                break
            if childkey in ctx['exhausted']:
                _restore(sim, api, ctx, frame['handle'], 'cached_exhausted_successor')
            elif childkey in {n['key'] for n in ctx['stack']}:
                _restore(sim, api, ctx, frame['handle'], 'active_state_cycle_guard')
            else:
                ctx['deferred'].pop(childkey, None)
                ctx['stack'].append(_frame(sim, api, ctx))
        else:
            ctx['rejections_since_rank'] += 1


def solve(case_path, provider, bank, llm_rank=True, initial_state=None, initial_observation=None,
          recovery_state=None, max_calls=8, max_checks=120, max_steps=10000000,
          timeout_seconds=480, max_checkpoints=128, max_restores=256):
    started = time.monotonic()
    limits = dict(max_calls=max_calls, max_checks=max_checks, max_steps=max_steps,
                  timeout_seconds=timeout_seconds, max_checkpoints=max_checkpoints, max_restores=max_restores)
    if any(type(v) is not int or v < 1 for v in (max_calls, max_checks, max_steps, max_checkpoints, max_restores)):
        raise ValueError('count limits must be positive integers')
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('timeout_seconds must be positive and finite')
    if type(llm_rank) is not bool or (llm_rank and provider is None):
        raise ValueError('llm_rank must be bool and ranking ON requires a provider')
    if not callable(getattr(bank, 'apply', None)):
        raise TypeError('bank must supply apply(observation,candidates,history,checkpoints,model_order)')
    sim = FullDisassemblySim(case_path, max_checks=max_checks, state=initial_state)
    api = SharedAPI(sim, recovery_state=recovery_state, max_checks=max_checks,
                    max_checkpoints=max_checkpoints, max_restores=max_restores, raise_goal=False)
    initial_event_count = len(api.export_recovery_state()['events'])
    observation = copy.deepcopy(initial_observation) if initial_observation is not None else api.snapshot()
    ctx = dict(limits=limits, provider=provider, bank=bank, llm_rank=llm_rank,
               deadline=started + timeout_seconds, calls=0, steps=0, bank_steps=0,
               decisions=[], retrievals=[], skill_calls=[], usage={}, model_order=[],
               nodes={}, visited=set(), exhausted=set(), deferred={}, used_recovery_hints=set(),
               backtracks=[], explored_actions=[], graph=ConditionalBlockingGraph(), edge_cache={},
               rejections_since_rank=0, need_restore_rank=False, provider_error=None, bank_error=None,
               termination='not_started')
    for record in sim.trace:
        key = record.get('physical_state_key_before')
        if key:
            ctx['graph'].add(key, record)
            if record.get('committed'):
                ctx['edge_cache'][(key, *action_key(record))] = {'valid': True, 'to_state': record.get('physical_state_key_after')}
    traced_file = str(Path(__file__).resolve())
    traced_files = {traced_file, str(Path(graph_module.__file__).resolve())}
    def instruction_trace(frame, event, arg):
        if frame.f_code.co_filename not in traced_files:
            return None
        if frame.f_code.co_filename == traced_file and frame.f_code.co_name == '_invoke_bank':
            return None
        if event == 'call':
            frame.f_trace_opcodes = True
            frame.f_trace_lines = False
        elif event == 'opcode':
            if ctx['steps'] + ctx['bank_steps'] >= max_steps:
                raise PlannerInstructionLimit('aggregate controller and bank instruction budget exhausted')
            ctx['steps'] += 1
        return instruction_trace
    previous = sys.gettrace()
    error = None
    try:
        sys._getframe().f_trace_opcodes = True
        sys.settrace(instruction_trace)
        _search(sim, api, ctx)
    except PlannerInstructionLimit as exc:
        ctx['termination'] = 'execution_step_budget_exhausted'
        error = {'type': type(exc).__name__, 'message': str(exc)}
    except RecoveryBudgetLimit as exc:
        ctx['termination'] = 'recovery_budget_exhausted'
        error = {'type': type(exc).__name__, 'message': str(exc)}
    except Exception as exc:
        ctx['termination'] = 'planner_error'
        error = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        sys.settrace(previous)
    late = time.monotonic() > ctx['deadline']
    success = bool(sim.success) and not late
    if success:
        ctx['termination'] = 'goal_reached'
    elif late and ctx['termination'] != 'provider_error':
        ctx['termination'] = 'wall_time_budget_exhausted'
    registry = api.export_recovery_state()
    recorded = {a['checker_call'] for a in ctx['explored_actions']}
    for trace in sim.trace:
        if trace.get('committed') and trace['checker_call'] not in recorded:
            ctx['explored_actions'].append({'part_id': trace['part_id'], 'direction': trace['direction'],
                'checker_call': trace['checker_call'], 'stability': trace.get('stability'),
                'from_state': trace.get('physical_state_key_before'), 'to_state': trace.get('physical_state_key_after'),
                'preexisting_or_interrupted_record': True})
    logged = {e['api_event_index'] for e in ctx['backtracks']}
    for event in registry['events'][initial_event_count:]:
        if event['operation'] == 'restore' and event.get('restored') and event['event_index'] not in logged:
            ctx['backtracks'].append({'from_state': event['state_key_before'], 'to_state': event['state_key_after'],
                'checker_calls': event['checks_after'], 'api_event_index': event['event_index'], 'handle': event['handle'],
                'reason': 'interrupted_bookkeeping', 'remaining': registry['checkpoints'][event['handle']]['metadata']['remaining_parts'],
                'budget_refunded': False})
    ctx['backtracks'].sort(key=lambda event: event['api_event_index'])
    return {'case_id': sim.case['id'], 'case_path': str(Path(case_path).resolve()),
            'method': 'fixed_graph_dfs_bank', 'llm_rank': llm_rank, 'success': success,
            'bank_version': getattr(bank, 'version', None), 'bank_sha256': getattr(bank, 'sha256', None),
            'status': 'PASS' if success else 'UNKNOWN', 'termination': ctx['termination'],
            'initial_observation': observation, 'initial_observation_sha256': neutral_observation_hash(observation),
            'observation': api.snapshot(), 'state': sim.export_state(), 'recovery_state': registry,
            'trace': copy.deepcopy(sim.trace), 'actions': copy.deepcopy(sim.actions),
            'backtracks': ctx['backtracks'], 'explored_actions': ctx['explored_actions'],
            'decisions': ctx['decisions'], 'retrievals': ctx['retrievals'], 'skill_calls': ctx['skill_calls'],
            'llm_calls': ctx['calls'], 'checker_calls': sim.checks,
            'execution_steps': ctx['steps'] + ctx['bank_steps'], 'controller_execution_steps': ctx['steps'],
            'skill_state':bank.export_state(), 'bank_execution_steps': ctx['bank_steps'], 'token_usage': ctx['usage'],
            'elapsed_seconds': time.monotonic() - started, 'limits': limits,
            'provider_error': ctx['provider_error'], 'error': error or ctx['bank_error'],
            'goal_reached_after_deadline': bool(sim.success) and late,
            **sim.task_progress(),
            'removed_count': len(sim.actions) if success else None,
            'accepted_removals': sum(bool(t.get('committed')) for t in sim.trace),
            'successful_restores': registry['restore_count'],
            'search': {'visited_states': len(ctx['visited']), 'exhausted_states': len(ctx['exhausted']),
                       'deferred_states': len(ctx['deferred']), 'cached_edges': len(ctx['edge_cache']),
                       'algorithm': 'fixed exact-state DFS with optional LLM ranking and automatic bank application',
                       'complete_under_finite_budget': False, 'heuristic_recovery_is_not_impossibility_proof': True}}

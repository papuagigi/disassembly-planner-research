"""A/B: LLM-generated search and control over the common v3 physical API.

B's optional frozen bank provides the identical order/restore proposals used by
C. It cannot run a host search or perform an action for the generated policy.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import time

from disassembly_mujoco.agent import CODE_SCHEMA, API_SPEC, ProviderError
from disassembly_real_v2.simulator import FullDisassemblySim
from disassembly_hybrid.common import neutral_observation_hash
from disassembly_learning_v3.shared_api import SharedAPI
from .runtime import run_code
from .skill_adapter import describe_bank, load_bank
from .state_transport import clone_skill_state


SPEC = API_SPEC.replace('shared 24 checker calls', 'shared checker calls shown in limits')
SPEC = SPEC.replace('3D OBJ selective-disassembly environment', '3D OBJ full-disassembly environment')
SPEC = SPEC.replace('The goal is verified removal of the target while every accepted step leaves the remaining assembly stable.',
                    'The goal is verified removal of n-1 product parts, leaving at most one part; every accepted step must leave the remaining assembly stable.')
SPEC = SPEC.replace('The host stops code immediately upon verified target removal. Aim for success first, then fewer removed parts and calls.',
                    'The host stops code only when at most one part remains. Aim for full-sequence success first, then fewer failed checks and calls.')
SPEC = SPEC.replace('50000-opcode episode budget', 'cumulative opcode episode budget shown in limits')
SPEC = SPEC.replace('Each code turn has a 120-second wall limit including physics calls.',
                    'The remaining episode wall deadline bounds each code turn including physics calls.')
SPEC = SPEC.replace('A stability rejection may require removing a supported part first.',
                    'A stability rejection means required support may be missing. Use observed support contacts and checkpoints to diagnose it.')
SPEC += '''
Additional API, IDENTICAL in A, B and C:
  api.checkpoint() -> opaque string handle; saves exact state and accepted action prefix.
  api.checkpoints() -> LIST of DICT entries, not a dictionary. Each entry has handle, state_key,
     creation_event_index, remaining_parts, observed support_edges and accepted_action_prefix.
     These are past observations, not a future oracle. Datatype usage: for cp in api.checkpoints():
         handle = cp['handle']
  api.snapshot()['recovery'] -> DICT; its ['checkpoints'] field is that same LIST of DICT entries.
     Do not call .get('checkpoints') on api.checkpoints(), because it already returns the list.
  api.restore(handle) -> current snapshot; restores that saved state and path. It NEVER refunds
     physics checks, failures, instruction steps, elapsed time or model calls.
Checkpoint handles persist across model turns; policy variables do not. Read checkpoints() after a new turn.
snapshot provides state_key, current_state_feedback, history_feedback, support_edges and recovery metadata.
Hard exclusions justified by a rejected direction apply only to the exact same physical state.
Support edges are current vertical contacts, not a proven future extraction order.
An accepted stable removal may enter a branch from which the full sequence cannot finish.
You own all search, candidate generation, within-episode caching, checkpointing and backtracking.
The host NEVER supplies DFS, a search stack, a reference removal order, or automatic recovery for A/B.
Use observed allowed_directions and skip fixed parts when building candidate actions.
The host stops execution only after n-1 removals leave at most one part. Defining functions alone does nothing;
include a top-level call. A Python exception stops this turn and its physical prefix is retained.
snapshot.goal_type is full_disassembly; required_removals is n-1 and completed_removals
counts the current accepted prefix. snapshot.target_id is only a compatibility focus:
initial_focus_id while present, otherwise the first remaining nonfixed ID in string order.
It changes deterministically after removals or restores. Removing that focus is NOT success.
Continue using all remaining movable candidates until remaining_part_count <= 1.
An anchored base, when present, stays as the final part. Focus changes do not reset
the task, physical state, checkpoint registry, costs, feedback, or skill episode ledger.
Restricted builtins reminder: isinstance and type are UNAVAILABLE. Do not call them.
No model weights change. Banks are frozen during evaluation; repeats do not learn from other repeats.

Optional B-only reusable API, when reusable_library.available is true:
  skills.recommend(candidates, model_order=[]) ->
     {ordered_actions, restore_handle, skill_id, retrieval, execution_steps, error}
candidates is your list of distinct {'part_id': string, 'direction': one of six axis strings} actions
for remaining movable parts. model_order is an optional soft priority list in that same format.
The function runs the EXACT SAME frozen executable bank and order/restore role composition used in C.
Its sources and metadata appear below. It sees the current public observations, physics feedback and
checkpoint metadata, and returns a pure recommendation. It never checks/removes/restores a part or runs DFS.
You decide whether and when to call it and whether to call api.restore(proposal['restore_handle']) or
api.remove(action['part_id'], action['direction']). An empty restore_handle means no recovery suggestion.
All bank execution opcodes count against your same cumulative instruction allowance.
Order skills retain their established order; restore skills cannot overwrite that order.
A has no skills object, stored skill sources or external reusable memory. It may still define its own
functions and retain feedback/checkpoints within this episode. Avoid calling skills in A.
'''


NEXT_STEP_SPEC = """
B-only added executable skill API:
 skills.next_step(candidates, model_order=[]) -> {operation,action,handle,evidence}.
 operation is remove, restore, checkpoint, or exhausted. It invokes the same frozen
 order, nearest-restore and frontier procedure used in C. The pure procedure keeps
 an episode-local exact-state ledger across code turns, remembers accepted AND
 rejected edges, initializes child frames, and avoids arbitrary checkpoint cycles.
 It never executes an API operation. You must explicitly call it and then dispatch:
  remove -> api.remove(step['action']['part_id'],step['action']['direction'])
  restore -> api.restore(step['handle'])
  checkpoint -> api.checkpoint()
  exhausted -> stop
 Rebuild public remaining movable candidates each iteration; next_step filters
 attempted edges and returns a fresh proposal. Calling recommend alone does not
 activate the frontier procedure. There is no automatic host DFS or fallback.
 Its ledger resets for every evaluation trial. It does not learn across repeats.
"""

def _valid_response(value):
    return (isinstance(value, dict) and set(value) == {'code', 'summary'} and
            all(isinstance(value[k], str) for k in value))


def _feedback(decision):
    execution = decision.get('execution', {})
    records = execution.get('skill_calls', [])
    summary = {k: execution.get(k) for k in ('error', 'steps', 'halt_reason')}
    # Full stages/candidate arrays remain in raw results. They need not be
    # duplicated into every later model prompt; current physics feedback is
    # already available in the full current observation.
    summary['skill_recommendations'] = [
        {k: record.get(k) for k in ('application_index', 'state_key', 'checks_before',
                                    'returned_handle', 'restore_applied', 'execution_steps', 'error')}
        for record in records[-20:]]
    summary['earlier_recommendations_omitted'] = max(0, len(records) - 20)
    return {'call': decision['call'], 'response': decision.get('response'), 'execution': summary}


def solve_code(case_path, provider, library=None, initial_state=None, initial_observation=None,
               recovery_state=None, max_calls=8, max_checks=240, max_steps=10000000,
               timeout_seconds=480.0, max_checkpoints=128, max_restores=256):
    for label, value in (('max_calls', max_calls), ('max_checks', max_checks), ('max_steps', max_steps),
                         ('max_checkpoints', max_checkpoints), ('max_restores', max_restores)):
        if type(value) is not int or value < 1:
            raise ValueError(label + ' must be a positive integer')
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 480):
        raise ValueError('timeout_seconds must be finite and in (0, 480]')
    bank = load_bank(library) if library is not None else None
    condition_id = 'B_code_with_library' if bank is not None else 'A_code_no_library'
    guidance = describe_bank(bank) if bank is not None else {'available': False, 'exports': []}
    started = time.monotonic()
    sim = FullDisassemblySim(case_path, max_checks=max_checks, state=initial_state)
    api = SharedAPI(sim, recovery_state=recovery_state, max_checks=max_checks,
                    max_checkpoints=max_checkpoints, max_restores=max_restores)
    state, registry = sim.export_state(), api.export_recovery_state()
    initial_event_count = len(registry['events'])
    observation = copy.deepcopy(initial_observation) if initial_observation is not None else api.snapshot()
    initial = copy.deepcopy(observation)
    decisions, skill_calls, usage = [], [], {}
    skill_state = {}
    calls = steps = policy_steps = bank_steps = 0
    checks, success = state['checks'], bool(sim.success)
    termination, provider_error, last_error = 'call_budget_exhausted', None, None
    limits = dict(max_calls=max_calls, max_checks=max_checks, max_steps=max_steps,
                  timeout_seconds=timeout_seconds, max_checkpoints=max_checkpoints, max_restores=max_restores)
    while not success and calls < max_calls and checks < max_checks and steps < max_steps:
        left = timeout_seconds - (time.monotonic() - started)
        if left <= 0:
            termination = 'wall_time_budget_exhausted'
            break
        history = [_feedback(d) for d in decisions]
        condition_text = ('You are B. The reusable library is available through skills.recommend and skills.next_step. next_step is the stored failure-repair DFS ledger procedure; call it explicitly and execute its returned operation. It performs no physical action itself.'
                          if bank is not None else
                          'You are A. No reusable library or skills object is available.')
        prompt = SPEC + (NEXT_STEP_SPEC if bank is not None else '') + '\nCURRENT CONDITION: ' + condition_id + '. ' + condition_text + '\nTASK AND EXECUTION FEEDBACK:\n' + json.dumps({
            'condition_id': condition_id, 'observation': observation, 'limits': limits,
            'checks_remaining': max_checks - checks,
            'model_calls_remaining_including_this': max_calls - calls,
            'opcodes_remaining': max_steps - steps, 'wall_seconds_remaining': left,
            'history': history, 'reusable_library': guidance}, ensure_ascii=False)
        calls += 1
        decision = {'call': calls, 'checks_before': checks,
                    'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
        decisions.append(decision)
        old_timeout = getattr(provider, 'timeout', None)
        if isinstance(old_timeout, (int, float)):
            provider.timeout = min(old_timeout, left)
        try:
            value, metadata = provider.complete(prompt, CODE_SCHEMA, calls)
            if not _valid_response(value):
                raise ProviderError('Expected exactly code and summary string fields')
        except Exception as exc:
            provider_error = str(exc)
            decision.update(provider_error=provider_error)
            termination = 'provider_error'
            break
        finally:
            if isinstance(old_timeout, (int, float)):
                provider.timeout = old_timeout
        decision.update(response=value, metadata=metadata)
        for key, value_number in metadata.get('usage', {}).items():
            if isinstance(value_number, (int, float)):
                usage[key] = usage.get(key, 0) + value_number
        left = timeout_seconds - (time.monotonic() - started)
        if left <= 0:
            termination = 'wall_time_budget_exhausted'
            break
        result = run_code(case_path, value['code'], state=state, recovery_state=registry,
                          library_bank=bank, max_checks=max_checks, max_steps=max_steps - steps,
                          timeout_seconds=left, max_checkpoints=max_checkpoints, max_restores=max_restores, skill_state=skill_state)
        skill_state = clone_skill_state(result.get("skill_state", skill_state))
        state, registry = result['state'], result['recovery_state']
        observation = result.get('observation') or observation
        steps += result['steps']
        policy_steps += result.get('policy_steps', 0)
        bank_steps += result.get('bank_steps', 0)
        checks = max(checks, result['checker_calls'], state['checks'])
        success = bool(result['success'])
        turn_retrievals = []
        for record in result['skill_calls']:
            record = {**record, 'llm_call': calls, 'application_index': len(skill_calls) + 1}
            skill_calls.append(record)
            turn_retrievals.append(record)
        decision['execution'] = {k: v for k, v in result.items()
                                 if k not in ('state', 'recovery_state', 'observation', 'trace')}
        decision['execution']['skill_calls'] = turn_retrievals
        last_error = result.get('error')
        error_type = (last_error or {}).get('type')
        if error_type in ('WorkerError', 'WallTimeLimit'):
            termination = 'execution_worker_failure'
            break
        if error_type == 'InstructionLimit':
            termination = 'execution_step_budget_exhausted'
            break
    late = time.monotonic() - started >= timeout_seconds
    if late:
        success, termination = False, 'wall_time_budget_exhausted'
    elif success:
        termination = 'goal_reached'
    elif checks >= max_checks:
        termination = 'check_budget_exhausted'
    elif steps >= max_steps:
        termination = 'execution_step_budget_exhausted'
    backtracks = [{'from_state': e['state_key_before'], 'to_state': e['state_key_after'],
                   'checker_calls': e['checks_after'], 'api_event_index': e['event_index'],
                   'handle': e['handle'], 'reason': 'generated_policy_restore', 'budget_refunded': False}
                  for e in registry['events'][initial_event_count:]
                  if e.get('operation') == 'restore' and e.get('restored')]
    return {
        'case_id': sim.case['id'], 'case_path': str(Path(case_path).resolve()),
        'method': 'code_with_library' if bank is not None else 'code_no_library',
        'success': success, 'status': 'PASS' if success else 'UNKNOWN', 'termination': termination,
        'state': state, 'trace': state['trace'], 'actions': state['actions'],
        'recovery_state': registry, 'backtracks': backtracks, 'successful_restores': registry['restore_count'],
        'decisions': decisions, 'skill_calls': skill_calls, 'retrievals': copy.deepcopy(skill_calls),
        'initial_observation': initial, 'initial_observation_sha256': neutral_observation_hash(initial),
        'observation': observation, 'checker_calls': checks, 'completed_checker_calls': state['checks'],
        'llm_calls': calls, 'execution_steps': steps, 'controller_execution_steps': policy_steps,
        'generated_code_execution_steps': policy_steps, 'bank_execution_steps': bank_steps,
        'token_usage': usage, 'elapsed_seconds': time.monotonic() - started,
        'removed_count': len(state['actions']) if success else None,
        'accepted_removals': sum(bool(r.get('committed')) for r in state['trace']),
        'skill_state':skill_state, 'bank_version': guidance.get('bank_version'), 'bank_sha256': guidance.get('bank_sha256'),
        'library_sha256': guidance.get('bank_sha256'), 'limits': limits,
        'provider_error': provider_error, 'error': last_error,
        **sim.task_progress(state),
        'goal_reached_after_deadline': len(state['remaining']) <= 1 and late,
        'search': {'algorithm': 'LLM-generated code; optional explicitly called executable frontier/order/restore skills; no automatic host DFS',
                   'complete_under_finite_budget': False},
    }

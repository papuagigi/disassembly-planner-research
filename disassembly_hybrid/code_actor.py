"""New experiment adapter. The original actor/runtime/library are unmodified."""
from __future__ import annotations
import copy
import hashlib
import time
from pathlib import Path
from disassembly_mujoco.agent import build_prompt, validate_library, CODE_SCHEMA, ProviderError
from disassembly_mujoco.runtime import run_code
from disassembly_mujoco.simulator import DisassemblySim
from .common import public_evidence, neutral_observation_hash

def solve_code(case_path, provider, library=None, max_calls=4, max_checks=24,
               max_steps=1000000, timeout_seconds=480.0, initial_state=None,
               initial_observation=None):
    started = time.monotonic()
    sim = DisassemblySim(case_path, max_checks=max_checks, capture=False, state=initial_state)
    state = sim.export_state()
    observation = copy.deepcopy(initial_observation or sim.snapshot())
    initial_input = copy.deepcopy(observation)
    library_hash = validate_library(library) if library else None
    decisions, skill_calls, usage = [], [], {}
    calls = steps = 0
    counted_checks = state['checks']
    unfinished_operation = None
    goal_after_deadline = False
    provider_error = None
    termination = 'call_budget_exhausted'
    success = sim.success
    while not success and calls < max_calls and state['checks'] < max_checks and steps < max_steps:
        left = timeout_seconds - (time.monotonic() - started)
        if left <= 0:
            termination = 'wall_budget_exhausted'
            break
        observation['directed_blocking_graph'] = public_evidence(state)
        observation['common_probe_feedback'] = copy.deepcopy(initial_input.get('common_probe_feedback', []))
        prompt = build_prompt(observation, decisions, max_checks-state['checks'], max_steps-steps, library)
        prompt = prompt.replace('50000-opcode episode budget', str(max_steps)+'-opcode episode budget')
        prompt += ('\nCOMMON STUDY CONTEXT: The host already charged the target-direction probes shown in common_probe_feedback. '
                   'The directed_blocking_graph contains current-state directional evidence, not a solved order. '
                   'All earlier feedback remains available within this episode. Reuse it as appropriate. '
                   'All three arms have the same initial observations, 4 model calls and 24 total physics calls including probes. '
                   'Model weights and the supplied library are frozen across episodes.\n')
        calls += 1
        old_timeout = getattr(provider, 'timeout', None)
        if old_timeout is not None:
            provider.timeout = max(0.001, min(old_timeout, left))
        try:
            value, meta = provider.complete(prompt, CODE_SCHEMA, calls)
            if (not isinstance(value, dict) or set(value) != {'code', 'summary'}
                    or not all(isinstance(value[k], str) for k in value)):
                raise ProviderError('Expected code and summary string fields')
        except (ProviderError, OSError) as exc:
            provider_error = str(exc)
            decisions.append({'call': calls, 'provider_error': provider_error})
            termination = 'provider_error'
            break
        finally:
            if old_timeout is not None:
                provider.timeout = old_timeout
        left = timeout_seconds - (time.monotonic() - started)
        if left <= 0:
            decisions.append({'call': calls, 'response': value, 'metadata': meta,
                              'execution': {'error': {'type': 'WallTimeLimit'}}})
            termination = 'wall_budget_exhausted'
            break
        result = run_code(case_path, value['code'], state=state,
                          library_source=library['library_source'] if library else '',
                          exports=library['exports'] if library else [], max_checks=max_checks,
                          max_steps=max_steps-steps, timeout_seconds=min(120.0, left))
        state = result['state']
        counted_checks = max(counted_checks, result['checker_calls'], state['checks'])
        unfinished_operation = result.get('unfinished_operation')
        observation = result['observation'] or observation
        success = result['success']
        steps += result['steps']
        skill_calls.extend({**r, 'llm_call': calls} for r in result['skill_calls'])
        decisions.append({'call': calls, 'response': value, 'metadata': meta, 'execution': result,
                          'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()})
        for key, n in meta.get('usage', {}).items():
            if isinstance(n, (int, float)):
                usage[key] = usage.get(key, 0)+n
        if time.monotonic()-started >= timeout_seconds:
            goal_after_deadline = bool(success)
            success = False
            termination = 'wall_budget_exhausted'
            break
        if (result.get('error') or {}).get('type') in ('WorkerError', 'WallTimeLimit'):
            termination = ('execution_time_limit' if result['error']['type']=='WallTimeLimit'
                           else 'execution_worker_failure')
            break
    if success:
        termination = 'goal_reached'
    elif termination not in ('provider_error', 'wall_budget_exhausted', 'execution_worker_failure', 'execution_time_limit'):
        if state['checks'] >= max_checks:
            termination = 'check_budget_exhausted'
        elif steps >= max_steps:
            termination = 'execution_step_budget_exhausted'
    return {'case_id': sim.case['id'], 'case_path': str(Path(case_path).resolve()),
            'method': 'code_with_library' if library else 'code_no_library',
            'success': bool(success), 'status': 'PASS' if success else 'UNKNOWN',
            'termination': termination, 'initial_observation': initial_input,
            'initial_observation_sha256': neutral_observation_hash(initial_input),
            'observation': observation, 'state': state, 'trace': state['trace'],
            'actions': state['actions'], 'explored_actions': copy.deepcopy(state['actions']),
            'decisions': decisions, 'skill_calls': skill_calls, 'checker_calls': counted_checks,
            'completed_checker_calls': state['checks'], 'unfinished_operation': unfinished_operation,
            'goal_reached_after_deadline': goal_after_deadline,
            'execution_steps': steps, 'llm_calls': calls, 'token_usage': usage,
            'provider_error': provider_error, 'library_sha256': library_hash,
            'removed_count': len(state['actions']) if success else None,
            'accepted_removals': len(state['actions']), 'backtracks': 0,
            'elapsed_seconds': time.monotonic()-started}

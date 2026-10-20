"""v7.2 restricted executor: v7 runtime with the HardenedAPI facade and the API-level deadline.

Grammar, guards, opcode accounting and builtins are reused from disassembly_repair_v7.runtime
(unchanged file). Only the facade base class and the deadline wiring differ.
"""
from __future__ import annotations

import sys
import time

from disassembly_repair_v7 import runtime as v7
from .shared_api import HardenedAPI

guards = v7.guards
compile_restricted = v7.compile_restricted
simulation_result = v7.simulation_result


class PublicAPI(HardenedAPI):
    def __init__(self, sim, execution, callback, recovery_state=None, max_checkpoints=128, max_restores=256):
        self._execution, self._worker_callback = execution, callback

        def changed(event):
            if event['event'] == 'operation_started':
                self._worker_callback({**event, 'steps': execution['steps'],
                                       'recovery_state': self.export_recovery_state()})
            else:
                execution['checker_calls'] = sim.checks
                self._worker_callback({'event': 'progress', 'result': simulation_result(sim, execution, self)})
        super().__init__(sim, recovery_state=recovery_state, max_checks=execution['max_checks'],
                         max_checkpoints=max_checkpoints, max_restores=max_restores,
                         callback=changed, raise_goal=True,
                         goal_exception=guards.GoalReached, budget_exception=guards.BudgetLimit)


def execute_payload(payload, sim, callback):
    execution = {'steps': 0, 'policy_steps': 0, 'error': None, 'checker_calls': sim.checks,
                 'max_checks': payload['max_checks']}
    api = PublicAPI(sim, execution, callback, recovery_state=payload.get('recovery_state'),
                    max_checkpoints=payload.get('max_checkpoints', 128), max_restores=payload.get('max_restores', 256))
    api.deadline = payload.get('deadline_monotonic')
    api.deadline_exception = guards.WallTimeLimit   # same exception class as the policy wall guard
    safe = v7._safe_builtins()
    base = {'__builtins__': safe, '_binary': guards.safe_binary, '_attribute': guards.safe_attribute}
    started = time.monotonic()
    sys._getframe().f_trace_opcodes = True

    def trace(frame, event, arg):
        if frame.f_code.co_filename != '<policy>':
            return None
        if event == 'call':
            frame.f_trace_opcodes = True
            frame.f_trace_lines = False
        elif event == 'opcode':
            if execution['steps'] >= payload['max_steps']:
                raise guards.InstructionLimit('generated-code instruction budget exhausted')
            if time.monotonic() - started > payload['timeout_seconds']:
                raise guards.WallTimeLimit('code execution wall deadline exceeded')
            execution['policy_steps'] += 1
            execution['steps'] = execution['policy_steps']
            if execution['steps'] % 256 == 0:
                guards.memory_check()
        return trace

    try:
        policy = compile_restricted(payload['code'])
        scope = {**base, 'api': api}
        sys.settrace(trace)
        exec(policy, scope, scope)
    except guards.GoalReached:
        execution['halt_reason'] = 'goal_reached'
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        execution['error'] = {'type': type(exc).__name__, 'message': str(exc)[:1000]}
    finally:
        sys.settrace(None)
    result = simulation_result(sim, execution, api)
    result['execution_elapsed_seconds'] = time.monotonic() - started
    callback({'event': 'final', 'result': result})
    return result

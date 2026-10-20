"""v7 restricted in-process executor for A/B generated code.

Adapted copy of disassembly_real_v3.runtime.execute_payload (unchanged file).
Differences: the policy-facing facade derives from v7 LedgerAPI (search
ledger, dead-end re-entry guard, state checkpoints). The restricted grammar,
arithmetic guards, opcode accounting and goal/budget exceptions are the same
private copies of the 2D prototype modules. Executable skill banks are not
supported (v6 A/B never used them).
"""
from __future__ import annotations

import ast
import builtins
import importlib.util
import resource
import sys
import time

from .common import WORKSPACE
from .shared_api import LedgerAPI


if str(WORKSPACE / 'disassembly_planner_2d') not in sys.path:
    sys.path.insert(0, str(WORKSPACE / 'disassembly_planner_2d'))  # the grammar module imports planner2d.geometry


def _private_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, WORKSPACE / 'disassembly_planner_2d/planner2d' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grammar = _private_module('planner2d._v7_grammar', 'code_runtime.py')
guards = _private_module('planner2d._v7_guards', 'code_worker.py')
grammar.METHODS.update({'snapshot', 'checkpoint', 'restore', 'checkpoints'})
validate_source = grammar.validate_source


def compile_restricted(source):
    tree = validate_source(source, exports=[], library=False)
    tree = guards.GuardArithmetic().visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, '<policy>', 'exec')


def memory_check():  # replaced by the actor with the episode RSS guard
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    nbytes = value if sys.platform == 'darwin' else value * 1024
    if nbytes > 4 * 1024 ** 3:
        raise guards.MemoryLimit('resident memory exceeds 4 GiB')


guards.memory_check = memory_check


def _safe_builtins():
    safe = {name: getattr(builtins, name) for name in (
        'abs', 'min', 'max', 'len', 'enumerate', 'zip', 'all', 'any', 'bool', 'round', 'reversed')}
    safe.update({
        'range': guards.safe_range,
        'list': guards.safe_constructor(list), 'tuple': guards.safe_constructor(tuple),
        'set': guards.safe_constructor(set), 'frozenset': guards.safe_constructor(frozenset),
        'dict': guards.safe_constructor(dict),
        'sorted': lambda value, key=None, reverse=False: sorted(guards.iterable(value), key=key, reverse=reverse),
        'sum': lambda value, start=0: guards.bounded(sum(guards.iterable(value), start)),
        'int': lambda value=0: guards.bounded(int(value)),
        'float': lambda value=0: guards.bounded(float(value)),
        'str': lambda value='': guards.bounded(str(guards.plain(value))),
        'print': lambda *args, **kwargs: None,
    })
    return safe


class PublicAPI(LedgerAPI):
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


def simulation_result(sim, execution, api):
    return {'state': sim.export_state(), 'observation': api.snapshot(),
            'recovery_state': api.export_recovery_state(),
            'trace': sim.trace, 'actions': sim.actions, 'checker_calls': sim.checks,
            'steps': execution['steps'], 'policy_steps': execution.get('policy_steps', 0),
            'success': bool(sim.success), 'error': execution['error'],
            'halt_reason': execution.get('halt_reason'), **sim.task_progress()}


def execute_payload(payload, sim, callback):
    execution = {'steps': 0, 'policy_steps': 0, 'error': None, 'checker_calls': sim.checks,
                 'max_checks': payload['max_checks']}
    api = PublicAPI(sim, execution, callback, recovery_state=payload.get('recovery_state'),
                    max_checkpoints=payload.get('max_checkpoints', 128), max_restores=payload.get('max_restores', 256))
    safe = _safe_builtins()
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

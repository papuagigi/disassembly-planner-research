"""ABC-study restricted worker; no host search exists in A or B.

This reuses the audited restricted grammar and arithmetic guards from the 2D
prototype, not its geometry. Untrusted policy code runs in a subprocess with
no imports, file/network APIs, reflection, or private attribute access. This is
a restricted language, not a general Python or OS security sandbox.
"""
from __future__ import annotations

import ast
import builtins
import copy
import importlib.util
import json
import math
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

PROJECT = Path(__file__).resolve().parent
WORKSPACE = PROJECT.parent
sys.path.insert(0, str(WORKSPACE / "disassembly_planner_2d"))
# Read-only private module copies: old module objects and files stay unchanged.
def _private_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, WORKSPACE / "disassembly_planner_2d/planner2d" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

grammar = _private_module("planner2d._abc_grammar", "code_runtime.py")
guards = _private_module("planner2d._abc_guards", "code_worker.py")
grammar.METHODS.update({"snapshot", "checkpoint", "restore", "checkpoints"})
validate_source = grammar.validate_source
sys.path.insert(0, str(WORKSPACE))
from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_abc_v3.skill_adapter import SkillAdapter, load_bank
from disassembly_abc_v3.state_transport import clone_skill_state


def compile_restricted(source, exports, library):
    tree = validate_source(source, exports=exports, library=library)
    tree = guards.GuardArithmetic().visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, "<skills>" if library else "<policy>", "exec")


def emit(event):
    print(json.dumps(event, ensure_ascii=False, allow_nan=False), flush=True)


def memory_check():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    nbytes = value if sys.platform == "darwin" else value * 1024
    if nbytes > 1024 * 1024 * 1024:
        raise guards.MemoryLimit("resident memory exceeds 1 GiB")


guards.memory_check = memory_check


def _safe_builtins():
    safe = {name: getattr(builtins, name) for name in (
        "abs", "min", "max", "len", "enumerate", "zip", "all", "any", "bool", "round", "reversed")}
    safe.update({
        "range": guards.safe_range,
        "list": guards.safe_constructor(list), "tuple": guards.safe_constructor(tuple),
        "set": guards.safe_constructor(set), "frozenset": guards.safe_constructor(frozenset),
        "dict": guards.safe_constructor(dict),
        "sorted": lambda value, key=None, reverse=False: sorted(guards.iterable(value), key=key, reverse=reverse),
        "sum": lambda value, start=0: guards.bounded(sum(guards.iterable(value), start)),
        "int": lambda value=0: guards.bounded(int(value)),
        "float": lambda value=0: guards.bounded(float(value)),
        "str": lambda value="": guards.bounded(str(guards.plain(value))),
        "print": lambda *args, **kwargs: None,
    })
    return safe


class PublicAPI(SharedAPI):
    """Code-worker facade over the exact API used by the host DFS."""
    def __init__(self, sim, execution, callback, recovery_state=None,
                 max_checkpoints=128, max_restores=256):
        self._execution, self._worker_callback = execution, callback
        def changed(event):
            if event["event"] == "operation_started":
                self._worker_callback({**event, "steps": execution["steps"],
                    "recovery_state": self.export_recovery_state()})
            else:
                execution["checker_calls"] = sim.checks
                self._worker_callback({"event": "progress", "result": simulation_result(sim, execution, self)})
        super().__init__(sim, recovery_state=recovery_state, max_checks=execution["max_checks"],
                         max_checkpoints=max_checkpoints, max_restores=max_restores,
                         callback=changed, raise_goal=True,
                         goal_exception=guards.GoalReached, budget_exception=guards.BudgetLimit)

    def checkpoint(self):
        handle = super().checkpoint()
        # v3 adds public observed context after the inherited callback fires.
        self._worker_callback({"event": "progress", "result": simulation_result(
            self._sim, self._execution, self)})
        return handle

    def restore(self, handle=None):
        # Audit only: the policy, never this facade, decides to call restore.
        from disassembly_recovery.shared_api import physical_state_key
        before = physical_state_key(self._sim.export_state())
        result = super().restore(handle)
        event = self.export_recovery_state()['events'][-1]
        for record in reversed(self._execution['skill_calls']):
            if (not record.get('restore_applied') and record.get('returned_handle') == handle
                    and record.get('state_key') == before):
                record.update(restore_applied=True, restore_event_index=event['event_index'])
                break
        self._worker_callback({'event': 'progress', 'result': simulation_result(
            self._sim, self._execution, self)})
        return result


def simulation_result(sim, execution, api=None):
    return {"state": sim.export_state(), "observation": api.snapshot() if api else sim.snapshot(),
            "recovery_state": api.export_recovery_state() if api else execution.get("recovery_state"),
            "trace": sim.trace, "actions": sim.actions,
            "checker_calls": sim.checks, "steps": execution["steps"],
            "policy_steps": execution.get("policy_steps", 0),
            "bank_steps": execution.get("bank_steps", 0),
            "skill_calls": execution["skill_calls"], "skill_state": clone_skill_state(execution.get("skill_state")), "success": bool(sim.success),
            "error": execution["error"], "halt_reason": execution.get("halt_reason")}


def execute_payload(payload, sim, callback=emit):
    """Execute one turn; separate function supports small fake-physics tests."""
    execution = {"steps": 0, "policy_steps": 0, "bank_steps": 0, "skill_calls": [], "error": None,
                 "checker_calls": sim.checks, "max_checks": payload["max_checks"], "skill_state":clone_skill_state(payload.get("skill_state"))}
    api = PublicAPI(sim, execution, callback, recovery_state=payload.get("recovery_state"),
                    max_checkpoints=payload.get("max_checkpoints",128), max_restores=payload.get("max_restores",256))
    safe = _safe_builtins()
    base = {"__builtins__": safe, "_binary": guards.safe_binary, "_attribute": guards.safe_attribute}
    started = time.monotonic()
    # Python 3.12 only enables opcode monitoring if an existing frame already
    # requests it when settrace is installed. Without this, the same policy can
    # report zero steps and evade the instruction budget on that interpreter.
    # The trace callback still ignores every trusted frame by filename.
    sys._getframe().f_trace_opcodes = True

    def trace(frame, event, arg):
        if frame.f_code.co_filename != "<policy>":
            return None
        if event == "call":
            frame.f_trace_opcodes = True
            frame.f_trace_lines = False
        elif event == "opcode":
            if execution["steps"] >= payload["max_steps"]:
                raise guards.InstructionLimit("generated-code instruction budget exhausted")
            if time.monotonic() - started > payload["timeout_seconds"]:
                raise guards.WallTimeLimit("code execution wall deadline exceeded")
            execution["policy_steps"] += 1
            execution["steps"] = execution["policy_steps"] + execution["bank_steps"]
            if execution["steps"] % 256 == 0:
                memory_check()
        return trace

    try:
        policy = compile_restricted(payload["code"], payload["exports"], False)
        scope = {**base, "api": api}
        if payload.get('library_bank') is not None:
            adapter = SkillAdapter(payload['library_bank'], api, sim, execution,
                                   payload['max_steps'], callback, guards.InstructionLimit)
            scope['skills'] = SimpleNamespace(recommend=adapter.recommend,next_step=adapter.next_step)
        sys.settrace(trace)
        exec(policy, scope, scope)
    except guards.GoalReached:
        execution["halt_reason"] = "goal_reached"
    except BaseException as exc:
        execution["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
    finally:
        sys.settrace(None)
    result = simulation_result(sim, execution, api)
    result["execution_elapsed_seconds"] = time.monotonic() - started
    callback({"event": "final", "result": result})
    return result


def run_code(case_path, code, state=None, library_bank=None,
             max_checks=120, max_steps=1000000, timeout_seconds=120.0,
             recovery_state=None, max_checkpoints=128, max_restores=256, skill_state=None):
    """Spawn a worker. Whole-episode simulator state is restored on every turn.

    max_checks is the total episode allowance, while max_steps is the remaining
    policy-plus-bank allowance. Trusted MuJoCo native work does not count as Python
    opcodes, but counts toward the remaining global episode wall deadline.
    """
    if type(max_checks) is not int or max_checks < 0 or type(max_steps) is not int or max_steps < 0:
        raise ValueError("budgets must be nonnegative integers")
    if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 480:
        raise ValueError("execution timeout must be in (0, 480]")
    for label, value in (("max_checkpoints", max_checkpoints), ("max_restores", max_restores)):
        if type(value) is not int or value < 0:
            raise ValueError(label + " must be a nonnegative integer")
    bank = load_bank(library_bank) if library_bank is not None else None
    exports = ['recommend','next_step'] if bank is not None else []
    payload = {"case_path": str(Path(case_path).resolve()), "code": code, "state": state,
               "library_bank": bank, "exports": exports, "skill_state":clone_skill_state(skill_state), "max_checks": max_checks,
               "max_steps": max_steps, "timeout_seconds": float(timeout_seconds),
               "recovery_state": recovery_state, "max_checkpoints": max_checkpoints, "max_restores": max_restores}
    # Initialize via the worker even on admission errors so result shapes remain
    # consistent and no physics/environment object enters the policy process.
    worker = Path(__file__).resolve()
    proc = subprocess.Popen([sys.executable, "-I", "-B", str(worker), "--worker"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(json.dumps(payload), timeout=timeout_seconds + 20)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        stdout, stderr = proc.communicate()
    result = {"state": state, "recovery_state": copy.deepcopy(recovery_state), "observation": None, "trace": [], "actions": [],
              "checker_calls": state.get("checks", 0) if isinstance(state, dict) else 0,
              "steps": 0, "policy_steps": 0, "bank_steps": 0,
              "skill_calls": [], "skill_state":clone_skill_state(skill_state), "success": False, "error": None}
    complete, pending = False, None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("event") in ("initial", "progress", "final"):
            incoming=event["result"]
            if "skill_state" in incoming:
                incoming["skill_state"]=clone_skill_state(incoming["skill_state"])
            result.update(incoming)
            pending = None
            complete = event["event"] == "final"
        elif event.get("event") == "operation_started":
            pending = event
            if "recovery_state" in event:
                result["recovery_state"] = event["recovery_state"]
        elif event.get("event") == "skill_start":
            result["skill_calls"].append(event["call"])
        elif event.get("event") == "skill_end":
            index = event["index"]
            if index < len(result["skill_calls"]):
                result["skill_calls"][index].update(event["call"])
            if 'skill_state' in event:result['skill_state']=clone_skill_state(event['skill_state'])
            for key in ('steps', 'policy_steps', 'bank_steps'):
                result[key] = max(result.get(key, 0), event.get(key, 0))
    if not complete:
        result["error"] = {"type": "WallTimeLimit" if timed_out else "WorkerError",
                           "message": "worker deadline exceeded" if timed_out else "worker exited: " + stderr[-2000:]}
        if pending:
            result["unfinished_operation"] = pending
            result["checker_calls"] = max(result["checker_calls"], pending["checker_call"])
            result["steps"] = max(result["steps"], pending.get("steps", 0))
            if result.get("state") is not None:
                result["state"]["checks"] = max(result["state"]["checks"], pending["checker_call"])
    return result


def worker_main():
    sys.path.insert(0, str(WORKSPACE))
    from disassembly_mujoco.simulator import DisassemblySim
    payload = json.loads(sys.stdin.read())
    sim = DisassemblySim(payload["case_path"], max_checks=payload["max_checks"], capture=False,
                         state=payload["state"])
    initial_execution = {"steps": 0, "policy_steps": 0, "bank_steps": 0, "skill_calls": [], "error": None,
                         "max_checks": payload["max_checks"], "skill_state":clone_skill_state(payload.get("skill_state"))}
    initial_api = PublicAPI(sim, initial_execution, emit,
                           recovery_state=payload.get("recovery_state"),
                           max_checkpoints=payload.get("max_checkpoints",128),
                           max_restores=payload.get("max_restores",256))
    # Create one registry once, then pass it to the execution facade. Otherwise
    # initial and final events of a new turn could claim different episode IDs.
    payload["recovery_state"] = initial_api.export_recovery_state()
    emit({"event": "initial", "result": simulation_result(sim, initial_execution, initial_api)})
    try:
        validate_source(payload["code"], exports=payload["exports"])
        if payload.get("library_bank") is not None:
            from disassembly_abc_v3.memory import SkillBank
            SkillBank(payload['library_bank'])
        elif payload["exports"]:
            raise ValueError("exports require frozen skill bank")
    except ValueError as exc:
        initial_execution["error"] = {"type": "AdmissionError", "message": str(exc)}
        result = simulation_result(sim, initial_execution, initial_api)
        emit({"event": "final", "result": result})
        return
    # Import/load assets before restricting the worker's file descriptors.
    for name, amount in (("RLIMIT_CPU", math.ceil(payload["timeout_seconds"]) + 10),
                         ("RLIMIT_FSIZE", 0), ("RLIMIT_NOFILE", 64)):
        key = getattr(resource, name, None)
        if key is not None:
            try:
                _, hard = resource.getrlimit(key)
                limit = amount if hard == resource.RLIM_INFINITY else min(amount, hard)
                resource.setrlimit(key, (limit, limit))
            except (OSError, ValueError):
                pass
    def deadline(signum, frame):
        raise guards.WallTimeLimit("code execution wall deadline exceeded")
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, payload["timeout_seconds"])
    try:
        execute_payload(payload, sim)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__" and "--worker" in sys.argv:
    worker_main()

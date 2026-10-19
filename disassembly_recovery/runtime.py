"""Recovery-study restricted worker; physical state and checkpoint registry persist.

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

grammar = _private_module("planner2d._recovery_grammar", "code_runtime.py")
guards = _private_module("planner2d._recovery_guards", "code_worker.py")
grammar.METHODS.update({"snapshot", "checkpoint", "restore", "checkpoints"})
validate_source = grammar.validate_source
sys.path.insert(0, str(WORKSPACE))
from disassembly_recovery.shared_api import SharedAPI


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


def simulation_result(sim, execution, api=None):
    return {"state": sim.export_state(), "observation": api.snapshot() if api else sim.snapshot(),
            "recovery_state": api.export_recovery_state() if api else execution.get("recovery_state"),
            "trace": sim.trace, "actions": sim.actions,
            "checker_calls": sim.checks, "steps": execution["steps"],
            "skill_calls": execution["skill_calls"], "success": bool(sim.success),
            "error": execution["error"], "halt_reason": execution.get("halt_reason")}


def execute_payload(payload, sim, callback=emit):
    """Execute one turn; separate function supports small fake-physics tests."""
    execution = {"steps": 0, "skill_calls": [], "error": None,
                 "checker_calls": sim.checks, "max_checks": payload["max_checks"]}
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
        if frame.f_code.co_filename not in ("<policy>", "<skills>"):
            return None
        if event == "call":
            frame.f_trace_opcodes = True
            frame.f_trace_lines = False
        elif event == "opcode":
            if execution["steps"] >= payload["max_steps"]:
                raise guards.InstructionLimit("generated-code instruction budget exhausted")
            if time.monotonic() - started > payload["timeout_seconds"]:
                raise guards.WallTimeLimit("code execution wall deadline exceeded")
            execution["steps"] += 1
            if execution["steps"] % 256 == 0:
                memory_check()
        return trace

    def wrapped(name, function):
        def call(*args, **kwargs):
            if len(execution["skill_calls"]) >= 1000:
                raise guards.InstructionLimit("skill-call log limit exceeded")
            record = {"name": name, "args": guards.plain(args), "kwargs": guards.plain(kwargs),
                      "checks_before": sim.checks, "checks_after": None, "result": None, "error": None}
            index = len(execution["skill_calls"])
            execution["skill_calls"].append(record)
            callback({"event": "skill_start", "call": dict(record)})
            try:
                value = function(*args, **kwargs)
                record["result"] = guards.plain(value)
                return value
            except guards.GoalReached:
                record["control_flow"] = "goal_reached"
                raise
            except BaseException as exc:
                record["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
                raise
            finally:
                record["checks_after"] = sim.checks
                callback({"event": "skill_end", "index": index, "call": dict(record)})
        return call

    try:
        policy = compile_restricted(payload["code"], payload["exports"], False)
        library_scope = dict(base)
        if payload["library_source"]:
            library = compile_restricted(payload["library_source"], payload["exports"], True)
            sys.settrace(trace)
            exec(library, library_scope, library_scope)
            sys.settrace(None)
            for name in payload["exports"]:
                library_scope[name] = wrapped(name, library_scope[name])
        scope = {**base, "api": api,
                 "skills": SimpleNamespace(**{name: library_scope[name] for name in payload["exports"]})}
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


def run_code(case_path, code, state=None, library_source="", exports=None,
             max_checks=120, max_steps=1000000, timeout_seconds=120.0,
             recovery_state=None, max_checkpoints=128, max_restores=256):
    """Spawn a worker. Whole-episode simulator state is restored on every turn.

    max_checks is the total episode allowance, while max_steps is the remaining
    generated-code allowance. Trusted MuJoCo native work does not count as Python
    opcodes, but does count toward the identical 120-second wall limit per turn.
    """
    if type(max_checks) is not int or max_checks < 0 or type(max_steps) is not int or max_steps < 0:
        raise ValueError("budgets must be nonnegative integers")
    if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 300:
        raise ValueError("execution timeout must be in (0, 300]")
    for label, value in (("max_checkpoints", max_checkpoints), ("max_restores", max_restores)):
        if type(value) is not int or value < 0:
            raise ValueError(label + " must be a nonnegative integer")
    exports = list(exports or [])
    payload = {"case_path": str(Path(case_path).resolve()), "code": code, "state": state,
               "library_source": library_source, "exports": exports, "max_checks": max_checks,
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
              "steps": 0, "skill_calls": [], "success": False, "error": None}
    complete, pending = False, None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("event") in ("initial", "progress", "final"):
            result.update(event["result"])
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
    initial_execution = {"steps": 0, "skill_calls": [], "error": None,
                         "max_checks": payload["max_checks"]}
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
        if payload["library_source"]:
            validate_source(payload["library_source"], exports=payload["exports"], library=True)
        elif payload["exports"]:
            raise ValueError("exports require library source")
    except ValueError as exc:
        result = simulation_result(sim, {"steps": 0, "skill_calls": [],
                                        "error": {"type": "AdmissionError", "message": str(exc)}}, initial_api)
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

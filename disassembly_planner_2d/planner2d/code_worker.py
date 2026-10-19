"""Private isolated worker for code_runtime; no untrusted code enters its globals."""
from __future__ import annotations

import ast
import builtins
import json
import math
import resource
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

# Trusted bootstrap only. -I ignores cwd, PYTHONPATH and user site packages.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from planner2d.code_runtime import MAX_CONTAINER, MAX_NUMBER, validate_source
from planner2d.geometry import check_action


class GoalReached(BaseException):
    pass


class BudgetLimit(BaseException):
    pass


class InstructionLimit(BaseException):
    pass


class MemoryLimit(BaseException):
    pass


class WallTimeLimit(BaseException):
    pass


def emit(event):
    sys.stdout.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
    sys.stdout.flush()


def plain(value, depth=0, context=None):
    """Bounded JSON representation; cap total traversal and detect shared cycles."""
    if context is None:
        context = {"left": 300, "seen": set()}
    context["left"] -= 1
    if context["left"] < 0 or depth > 8:
        return "<log-limit>"
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, str):
            return value[:2000]
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, int) and abs(value) > MAX_NUMBER:
            return "<large-int>"
        return value
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        if id(value) in context["seen"]:
            return "<shared-reference>"
        context["seen"].add(id(value))
        if isinstance(value, dict):
            output = {}
            for index, (key, item) in enumerate(value.items()):
                if index >= 100 or context["left"] <= 0:
                    break
                safe_key = key if isinstance(key, (str, int, float, bool)) else "<key>"
                output[str(safe_key)[:100]] = plain(item, depth + 1, context)
            return output
        output = []
        for index, item in enumerate(value):
            if index >= 100 or context["left"] <= 0:
                break
            output.append(plain(item, depth + 1, context))
        return output
    return "<api>" if isinstance(value, Environment) else "<restricted-object>"


def bounded(value):
    if isinstance(value, (str, list, tuple, set, frozenset, dict)) and len(value) > MAX_CONTAINER:
        raise ValueError("container size exceeds limit")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if abs(value) > MAX_NUMBER or isinstance(value, float) and not math.isfinite(value):
            raise ValueError("number exceeds limit")
    return value


def iterable(value):
    # Materializing a generated iterable is traced; a bounded builtin range is finite.
    if hasattr(value, "__len__") and len(value) > MAX_CONTAINER:
        raise ValueError("iterable size exceeds limit")
    for index, item in enumerate(value):
        if index >= MAX_CONTAINER:
            raise ValueError("iterable size exceeds limit")
        yield item


def memory_check():
    maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    maximum_bytes = maximum if sys.platform == "darwin" else maximum * 1024
    if maximum_bytes > 512 * 1024 * 1024:
        raise MemoryLimit("resident memory exceeds 512 MiB")


def safe_attribute(obj, name):
    if not callable(getattr(obj, name)):
        raise AttributeError("only permitted callable methods are accessible")
    return lambda *args, **kwargs: safe_method(obj, name, *args, **kwargs)


def safe_method(obj, name, *args, **kwargs):
    """Guard mutable collection growth before allocating and check resident memory."""
    memory_check()
    if isinstance(obj, (list, set, dict)):
        if name in ("append", "insert", "add", "setdefault") and len(obj) >= MAX_CONTAINER:
            raise ValueError("container mutation exceeds limit")
        if name == "extend" and isinstance(obj, list):
            if len(args) != 1 or kwargs:
                raise ValueError("extend expects one iterable")
            incoming = list(iterable(args[0]))
            if len(obj) + len(incoming) > MAX_CONTAINER:
                raise ValueError("container extension exceeds limit")
            obj.extend(incoming)
            return None
        if name in ("update", "union", "intersection", "difference", "symmetric_difference",
                    "intersection_update", "difference_update"):
            converted = []
            for arg in args:
                converted.append(arg if isinstance(arg, dict) else list(iterable(arg)))
            if name in ("update", "union", "symmetric_difference"):
                if len(obj) + sum(len(arg) for arg in converted) + len(kwargs) > MAX_CONTAINER:
                    raise ValueError("container union exceeds limit")
            args = tuple(converted)
    value = getattr(obj, name)(*args, **kwargs)
    memory_check()
    return bounded(value)


def safe_range(*args):
    value = range(*args)
    if len(value) > MAX_CONTAINER:
        raise ValueError("range exceeds limit")
    return value


def safe_constructor(constructor):
    def construct(value=()):
        if constructor is dict:
            return bounded(dict(value) if isinstance(value, dict) else dict(iterable(value)))
        return bounded(constructor(iterable(value)))
    return construct


def safe_binary(left, right, operation):
    if operation == "mult":
        sequence, number = (left, right) if isinstance(right, int) else (right, left)
        if isinstance(sequence, (str, list, tuple)) and isinstance(number, int):
            if len(sequence) * max(0, number) > MAX_CONTAINER:
                raise ValueError("sequence multiplication exceeds limit")
        return bounded(left * right)
    if operation == "add":
        if isinstance(left, (str, list, tuple)) and isinstance(right, type(left)):
            if len(left) + len(right) > MAX_CONTAINER:
                raise ValueError("sequence addition exceeds limit")
        return bounded(left + right)
    if operation == "mod":
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            raise ValueError("string formatting is unavailable")
        return bounded(left % right)
    operations = {"sub": lambda: left - right, "div": lambda: left / right,
                  "floordiv": lambda: left // right, "bitor": lambda: left | right,
                  "bitand": lambda: left & right, "bitxor": lambda: left ^ right}
    return bounded(operations[operation]())


class GuardArithmetic(ast.NodeTransformer):
    operations = {ast.Mult: "mult", ast.Add: "add", ast.Mod: "mod", ast.Sub: "sub",
                  ast.Div: "div", ast.FloorDiv: "floordiv", ast.BitOr: "bitor",
                  ast.BitAnd: "bitand", ast.BitXor: "bitxor"}

    def visit_Attribute(self, node):
        self.generic_visit(node)
        return ast.copy_location(ast.Call(func=ast.Name(id="_attribute", ctx=ast.Load()),
            args=[node.value, ast.Constant(node.attr)], keywords=[]), node)

    def visit_BinOp(self, node):
        self.generic_visit(node)
        return ast.copy_location(ast.Call(func=ast.Name(id="_binary", ctx=ast.Load()),
            args=[node.left, node.right, ast.Constant(self.operations[type(node.op)])], keywords=[]), node)

    def visit_AugAssign(self, node):
        # Transform augmented arithmetic too; avoid duplicate evaluation of subscript targets.
        if not isinstance(node.target, ast.Name):
            raise ValueError("augmented assignment is supported only for names")
        replacement = ast.Assign(targets=[node.target], value=ast.BinOp(
            left=ast.Name(id=node.target.id, ctx=ast.Load()), op=node.op, right=node.value))
        return self.visit(ast.copy_location(replacement, node))


def compile_restricted(source, exports, library):
    tree = validate_source(source, exports=exports, library=library)
    tree = GuardArithmetic().visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, "<skills>" if library else "<policy>", "exec")


class Environment:
    def __init__(self, payload, state):
        self._scene = payload["scene"]
        self._remaining = set(payload["remaining"])
        self._fixed = {p["id"] for p in self._scene["parts"] if p["fixed"]}
        self._max_checks = payload["max_checks"]
        self._state = state

    def observe(self):
        return {"workspace": list(self._scene["workspace"]), "target_id": self._scene["target_id"],
                "remaining_parts": [{"id": part["id"], "rects": [list(r) for r in part["rects"]],
                    "allowed_directions": list(part["allowed_directions"]), "fixed": part["fixed"]}
                    for part in self._scene["parts"] if part["id"] in self._remaining]}

    def check(self, *args, **kwargs):
        return self._operation("check", args, kwargs)

    def remove(self, *args, **kwargs):
        return self._operation("remove", args, kwargs)

    def _operation(self, kind, args, kwargs):
        if len(self._state["trace"]) >= self._max_checks:
            raise BudgetLimit("checker budget exhausted")
        before = sorted(self._remaining)
        fields = ("part_id", "direction", "remaining") if kind == "check" else ("part_id", "direction")
        supplied = dict(kwargs)
        invalid = len(args) > len(fields) or any(k not in fields for k in kwargs)
        for key, value in zip(fields, args):
            if key in supplied:
                invalid = True
            supplied[key] = value
        pid, direction = supplied.get("part_id"), supplied.get("direction")
        hypothesis = supplied.get("remaining")
        state = self._remaining
        if hypothesis is not None:
            if not isinstance(hypothesis, (list, tuple, set, frozenset)):
                invalid = True
            else:
                try:
                    state = set(hypothesis)
                    invalid = invalid or not state <= self._remaining or not self._fixed <= state
                except (TypeError, ValueError):
                    invalid = True
        action = {"part_id": pid, "direction": direction}
        if invalid:
            check = {"valid": False, "reason": "invalid_api_arguments", "blockers": [],
                     "distance": 0.0, "swept_rects": []}
        else:
            check = check_action(self._scene, state, action)
        if kind == "remove" and check["valid"]:
            self._remaining.remove(pid)
            self._state["actions"].append(dict(action))
        trace = {"kind": kind, "checker_call": len(self._state["trace"]) + 1,
                 "remaining_before": before, "remaining_after": sorted(self._remaining),
                 "hypothetical_remaining": sorted(state) if hypothesis is not None and not invalid else None,
                 "action": plain(action), "check": check}
        self._state["trace"].append(trace)
        self._state["remaining"] = sorted(self._remaining)
        self._state["checker_calls"] = len(self._state["trace"])
        emit({"event": "trace", "trace": trace, "steps": self._state["steps"]})
        if kind == "remove" and check["valid"] and pid == self._scene["target_id"]:
            raise GoalReached("target recovered; execution stops at the goal prefix")
        return json.loads(json.dumps(check))


def wrap_skill(name, function, state):
    def wrapped(*args, **kwargs):
        if len(state["skill_calls"]) >= 1000:
            raise InstructionLimit("skill call log limit exceeded")
        call = {"index": len(state["skill_calls"]), "name": name,
                "args": plain(args), "kwargs": plain(kwargs),
                "checks_before": state["checker_calls"], "checks_after": None,
                "result": None, "error": None}
        state["skill_calls"].append(call)
        emit({"event": "skill_start", "call": dict(call)})
        try:
            value = function(*args, **kwargs)
            call["result"] = plain(value)
            return value
        except GoalReached:
            call["control_flow"] = "goal_reached"
            raise
        except BaseException as exc:
            call["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
            raise
        finally:
            call["checks_after"] = state["checker_calls"]
            emit({"event": "skill_end", "call": dict(call)})
    return wrapped


def configure_limits(timeout):
    limits = {}
    for name, amount in (("RLIMIT_DATA", 512 * 1024 * 1024),
                         ("RLIMIT_CPU", max(1, math.ceil(timeout) + 1)),
                         ("RLIMIT_FSIZE", 0), ("RLIMIT_NOFILE", 32)):
        resource_id = getattr(resource, name, None)
        if resource_id is None:
            continue
        try:
            soft, hard = resource.getrlimit(resource_id)
            value = amount if hard == resource.RLIM_INFINITY else min(amount, hard)
            resource.setrlimit(resource_id, (value, value))
            limits[name] = value
        except (OSError, ValueError) as exc:
            limits[name] = "unavailable:" + type(exc).__name__
    # macOS maps shared libraries into a large virtual address space before startup.
    # DATA caps heap there; AS is also useful on Linux.
    if sys.platform != "darwin" and hasattr(resource, "RLIMIT_AS"):
        try:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
            limits["RLIMIT_AS"] = 512 * 1024 * 1024
        except (OSError, ValueError) as exc:
            limits["RLIMIT_AS"] = "unavailable:" + type(exc).__name__
    return limits


def main():
    payload = json.loads(sys.stdin.read())
    state = {"remaining": payload["remaining"], "actions": [], "trace": [], "skill_calls": [],
             "checker_calls": 0, "steps": 0, "error": None}
    state["resource_limits"] = configure_limits(payload["timeout_seconds"])
    state["resource_limits"]["rss_guard_bytes"] = 512 * 1024 * 1024
    state["resource_limits"]["max_container_items"] = MAX_CONTAINER
    emit({"event": "limits", "limits": state["resource_limits"]})
    api = Environment(payload, state)
    safe = {name: getattr(builtins, name) for name in
            ("abs", "min", "max", "len", "enumerate", "zip", "all", "any", "bool", "round", "reversed")}
    safe.update({"range": safe_range, "list": safe_constructor(list),
                 "tuple": safe_constructor(tuple), "set": safe_constructor(set),
                 "frozenset": safe_constructor(frozenset), "dict": safe_constructor(dict),
                 "sorted": lambda value, key=None, reverse=False: sorted(iterable(value), key=key, reverse=reverse),
                 "sum": lambda value, start=0: bounded(sum(iterable(value), start)),
                 "int": lambda value=0: bounded(int(value)),
                 "float": lambda value=0: bounded(float(value)),
                 "str": lambda value="": bounded(str(plain(value))),
                 "print": lambda *args, **kwargs: None})
    scope = {"__builtins__": safe, "_binary": safe_binary, "_attribute": safe_attribute}
    def trace(frame, event, arg):
        if frame.f_code.co_filename not in ("<policy>", "<skills>"):
            return None
        if event == "call":
            frame.f_trace_opcodes = True
            frame.f_trace_lines = False
        elif event == "opcode":
            if state["steps"] >= payload["max_steps"]:
                raise InstructionLimit("instruction budget exhausted")
            state["steps"] += 1
            if state["steps"] % 256 == 0:
                memory_check()
        return trace
    def deadline(signum, frame):
        raise WallTimeLimit("execution wall time exceeded")
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, payload["timeout_seconds"])
    try:
        policy = compile_restricted(payload["code"], payload["exports"], False)
        if payload["library_source"]:
            library = compile_restricted(payload["library_source"], payload["exports"], True)
            sys.settrace(trace)
            exec(library, scope, scope)
            sys.settrace(None)
            for name in payload["exports"]:
                scope[name] = wrap_skill(name, scope[name], state)
        skills = SimpleNamespace(**{name: scope[name] for name in payload["exports"]})
        # Separate policy names protect the registered library from policy reassignment.
        policy_scope = {"__builtins__": safe, "_binary": safe_binary, "_attribute": safe_attribute, "api": api, "skills": skills}
        sys.settrace(trace)
        exec(policy, policy_scope, policy_scope)
    except GoalReached:
        state["halt_reason"] = "goal_reached"
    except BaseException as exc:
        state["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
    finally:
        sys.settrace(None)
        signal.setitimer(signal.ITIMER_REAL, 0)
    state["success"] = payload["scene"]["target_id"] not in state["remaining"]
    emit({"event": "final", "result": state})


if __name__ == "__main__":
    main()

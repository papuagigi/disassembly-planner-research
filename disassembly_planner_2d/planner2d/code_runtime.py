"""Restricted code-as-policy runner. Generated Python is never run in this process.

CONTRACT: ``run_code`` accepts a validated scene and an optional current remaining
set. The returned prefix is authoritative even if execution raises or times out.
Only ``api.observe()``, ``api.check(part_id, direction, remaining=None)`` and
``api.remove(part_id, direction)`` expose the trusted environment. check and
remove each consume ONE checker call; remove checks and commits atomically.
A successful target removal stops execution immediately at that goal prefix,
with error=None and halt_reason="goal_reached". Skill logs mark this control flow.
Hypothetical remaining must be a subset of current remaining and retain all
fixed parts. It changes no physical state. No checker caching or solver fallback
exists. observe returns copies of public geometry only. Code may define Python
functions, loops and recursion. Optional validated library functions are exposed
as ``skills.<export>(api, ...)``. Library code uses exactly the same API.

This is a deliberately restricted language in an isolated, resource-limited
worker, not a general-purpose Python or operating-system security sandbox.
"""
from __future__ import annotations

import ast
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from .geometry import initial_state, validate_scene

MAX_SOURCE_CHARS = 60000
MAX_AST_NODES = 8000
MAX_CONTAINER = 50000
MAX_NUMBER = 10 ** 12
PUBLIC_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")
METHODS = {
    "observe", "check", "remove", "get", "keys", "values", "items", "copy",
    "append", "extend", "insert", "pop", "clear", "count", "index", "reverse",
    "sort", "add", "discard", "update", "union", "intersection", "difference",
    "issubset", "issuperset", "isdisjoint", "intersection_update",
    "difference_update", "symmetric_difference", "setdefault", "popitem",
}
BUILTIN_NAMES = {
    "abs", "min", "max", "sum", "len", "range", "enumerate", "zip", "list",
    "tuple", "set", "frozenset", "dict", "sorted", "all", "any", "bool", "int",
    "float", "str", "round", "reversed", "print",
}
FORBIDDEN_NAMES = {
    "open", "eval", "exec", "compile", "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr", "hasattr", "type", "object", "super",
    "input", "help", "breakpoint", "memoryview", "bytes", "bytearray",
    "classmethod", "staticmethod", "property", "__builtins__",
}
ALLOWED_NODES = {
    ast.Module, ast.Expr, ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Name,
    ast.Load, ast.Store, ast.Del, ast.Constant, ast.List, ast.Tuple, ast.Set,
    ast.Dict, ast.Subscript, ast.Slice, ast.Attribute, ast.Call, ast.keyword,
    ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.If, ast.IfExp,
    ast.For, ast.While, ast.Break, ast.Continue, ast.Pass, ast.Delete,
    ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
    ast.comprehension, ast.Compare, ast.BoolOp, ast.UnaryOp, ast.BinOp,
    ast.And, ast.Or, ast.Not, ast.UAdd, ast.USub, ast.Add, ast.Sub, ast.Mult,
    ast.Div, ast.FloorDiv, ast.Mod, ast.BitOr, ast.BitAnd, ast.BitXor,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.Is, ast.IsNot,
}
if hasattr(ast, "Index"):
    ALLOWED_NODES.add(ast.Index)


def validate_source(source, exports=None, library=False):
    """Validate the restricted grammar; return its AST or raise ValueError.

    Library modules contain only plain function definitions and a docstring.
    Exports are unique public snake_case function names. Imports, exceptions,
    classes, decorators, annotations, private names/attributes, arbitrary object
    attributes, power/shift operators, and formatting are intentionally absent.
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a nonempty string")
    if len(source) > MAX_SOURCE_CHARS:
        raise ValueError("source exceeds character limit")
    if exports is not None and not isinstance(exports, (list, tuple)):
        raise ValueError("exports must be a list of names")
    exports = [] if exports is None else list(exports)
    if (any(not isinstance(n, str) or not PUBLIC_NAME.fullmatch(n) for n in exports)
            or len(exports) != len(set(exports))):
        raise ValueError("exports must be unique public snake_case names")
    try:
        tree = ast.parse(source, filename="<skills>" if library else "<policy>")
    except (SyntaxError, RecursionError, ValueError) as exc:
        raise ValueError("invalid Python syntax: " + str(exc)) from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise ValueError("source exceeds AST node limit")
    for node in nodes:
        if type(node) not in ALLOWED_NODES:
            raise ValueError("unsupported Python syntax: " + type(node).__name__)
        if isinstance(node, ast.Name) and (node.id.startswith("_") or node.id in FORBIDDEN_NAMES):
            raise ValueError("forbidden name: " + node.id)
        if isinstance(node, ast.arg) and (node.arg.startswith("_") or node.arg in FORBIDDEN_NAMES or node.annotation):
            raise ValueError("forbidden parameter or annotation: " + node.arg)
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith("_") or node.name in FORBIDDEN_NAMES:
                raise ValueError("forbidden function name: " + node.name)
            if node.decorator_list or node.returns or node.type_comment:
                raise ValueError("decorators and function annotations are unavailable")
            # Defaults execute during definition; avoiding them keeps admission inert.
            if any(not isinstance(default, ast.Constant) for default in node.args.defaults):
                raise ValueError("function defaults must be literal constants")
            if any(default is not None and not isinstance(default, ast.Constant)
                   for default in node.args.kw_defaults):
                raise ValueError("function defaults must be literal constants")
        if isinstance(node, ast.AnnAssign):
            raise ValueError("annotations are unavailable")
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store) and isinstance(node.slice, ast.Slice):
            raise ValueError("slice assignment is unavailable")
        if isinstance(node, ast.Attribute):
            if (node.attr.startswith("_") or node.attr not in METHODS | set(exports)
                    or not isinstance(node.ctx, ast.Load)):
                raise ValueError("unavailable attribute: " + node.attr)
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, (bytes, complex)):
                raise ValueError("bytes and complex literals are unavailable")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if abs(value) > MAX_NUMBER or isinstance(value, float) and not math.isfinite(value):
                    raise ValueError("numeric literal exceeds limit")
            if isinstance(value, str) and len(value) > 10000:
                raise ValueError("string literal exceeds limit")
        if isinstance(node, ast.comprehension) and node.is_async:
            raise ValueError("async comprehensions are unavailable")
        if isinstance(node, ast.Call) and not isinstance(node.func, (ast.Name, ast.Attribute, ast.Lambda)):
            raise ValueError("only named functions, permitted methods, and lambdas may be called")
        if isinstance(node, ast.keyword) and node.arg is None:
            raise ValueError("expanded keyword arguments are unavailable")
    if library:
        defs = set()
        for item in tree.body:
            if isinstance(item, ast.FunctionDef):
                if item.name in defs:
                    raise ValueError("duplicate library function: " + item.name)
                defs.add(item.name)
            elif not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant)
                      and isinstance(item.value.value, str)):
                raise ValueError("library top level may contain only function definitions")
        if not exports or not set(exports).issubset(defs):
            raise ValueError("each library export must name a defined function")
    return tree


def _initial_result(scene, remaining):
    return {"remaining": sorted(remaining), "actions": [], "trace": [], "skill_calls": [],
            "checker_calls": 0, "steps": 0, "error": None,
            "success": scene["target_id"] not in remaining, "resource_limits": {}}


def run_code(scene, code, remaining=None, library_source="", exports=None,
             max_checks=24, max_steps=50000, timeout_seconds=5.0):
    """Run one policy turn with the supplied remaining global budgets.

    Code/worker failures are returned in ``error={type,message}``; malformed
    caller scene/budget arguments raise ValueError. Trace prefixes are retained
    after deadline, checker-budget, instruction-budget, or ordinary code errors.
    """
    validate_scene(scene)
    if type(max_checks) is not int or max_checks < 0:
        raise ValueError("max_checks must be a nonnegative integer")
    if type(max_steps) is not int or max_steps < 0:
        raise ValueError("max_steps must be a nonnegative integer")
    if not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds <= 30:
        raise ValueError("timeout_seconds must be in (0, 30]")
    original = initial_state(scene)
    remaining = original if remaining is None else frozenset(remaining)
    fixed = {part["id"] for part in scene["parts"] if part["fixed"]}
    if not remaining <= original or not fixed <= remaining:
        raise ValueError("remaining must contain known parts and retain fixed parts")
    result = _initial_result(scene, remaining)
    exports = [] if exports is None else list(exports)
    try:
        validate_source(code, exports=exports)
        if library_source:
            validate_source(library_source, exports=exports, library=True)
        elif exports:
            raise ValueError("exports require library_source")
    except ValueError as exc:
        result["error"] = {"type": "AdmissionError", "message": str(exc)}
        return result
    payload = {"scene": scene, "code": code, "remaining": sorted(remaining),
               "library_source": library_source, "exports": exports,
               "max_checks": max_checks, "max_steps": max_steps,
               "timeout_seconds": float(timeout_seconds)}
    worker = Path(__file__).with_name("code_worker.py")
    proc = subprocess.Popen([sys.executable, "-I", str(worker)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    parent_timeout = False
    try:
        stdout, stderr = proc.communicate(json.dumps(payload), timeout=timeout_seconds + 1.0)
    except subprocess.TimeoutExpired:
        parent_timeout = True
        proc.kill()
        stdout, stderr = proc.communicate()
    saw_final = False
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        kind = event.get("event")
        if kind == "trace":
            trace = event["trace"]
            result["trace"].append(trace)
            result["checker_calls"] = len(result["trace"])
            result["remaining"] = trace["remaining_after"]
            result["steps"] = max(result["steps"], event.get("steps", 0))
            if trace["kind"] == "remove" and trace["check"]["valid"]:
                result["actions"].append(trace["action"])
        elif kind == "skill_start":
            result["skill_calls"].append(event["call"])
        elif kind == "skill_end":
            index = event["call"]["index"]
            if 0 <= index < len(result["skill_calls"]):
                result["skill_calls"][index].update(event["call"])
        elif kind == "limits":
            result["resource_limits"] = event["limits"]
        elif kind == "final":
            result.update(event["result"])
            saw_final = True
    result["success"] = scene["target_id"] not in result["remaining"]
    if not saw_final:
        result["error"] = {"type": "WallTimeLimit" if parent_timeout else "WorkerError",
                           "message": "worker deadline exceeded" if parent_timeout
                           else "worker exited without final result (exit %s): %s" %
                           (proc.returncode, stderr[-1000:])}
    return result

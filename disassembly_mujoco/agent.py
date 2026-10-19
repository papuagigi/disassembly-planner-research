"""Code-as-policy actor for the MuJoCo selective-disassembly prototype."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "disassembly_planner_2d"))
from planner2d.llm import CodexCLIProvider, ProviderError
from .runtime import run_code, validate_source

MODEL = "gpt-6-luna"
EFFORT = "low"
LIMITS = {"max_calls": 4, "max_checks": 24, "max_steps": 50000, "execution_timeout": 120.0}
CODE_SCHEMA = {"type": "object", "properties": {
    "code": {"type": "string"}, "summary": {"type": "string"}},
    "required": ["code", "summary"], "additionalProperties": False}

API_SPEC = '''Return executable Python for a 3D OBJ selective-disassembly environment.
The host runs your code; do NOT call tools, open files, browse, or execute code yourself.
The host executes the returned code as a script. It does not automatically call functions you define.
Include a top-level invocation such as run(api) after defining your entry function, or call the public API directly at top level.
The goal is verified removal of the target while every accepted step leaves the remaining assembly stable.
Public API, identical in both conditions:
  api.snapshot() -> {target_id, remaining_parts:[{id,bounds,center,mass,fixed,allowed_directions,...}], remaining_checks,...}
  api.observe() -> alias for snapshot()
  api.check(part_id, direction) -> {valid,reason,blockers,stability,...}; tests without changing accepted state.
  api.remove(part_id, direction) -> same validation, commits ONLY when valid and stable.
Directions are +x,-x,+y,-y,+z,-z. Coordinates and masses use SI units; gravity is downward (-z).
The trusted checker tests a straight translation without rotation and simulates the remainder under gravity/contact/friction after removal.
This is a supported extraction abstraction: it is not a robot arm, force-limited pull, or joint/fastener simulator.
Every check or remove consumes ONE of the shared 24 checker calls, including rejected/repeated/library-internal queries.
check then remove costs TWO; remove alone checks and commits in ONE. There is no planner-side cache or free hypothetical checker.
snapshot is free and returns current accepted state. Fixed parts cannot be removed. Observe allowed_directions.
A collision rejection reports blockers when available. A stability rejection may require removing a supported part first.
A rejection does not change accepted physical state. Do not equate unsupported motion or timeout with universal impossibility.
The host stops code immediately upon verified target removal. Aim for success first, then fewer removed parts and calls.
You may use functions, loops, recursion, ordinary arithmetic, lists/dicts/sets and safe Python builtins.
No imports, file/network access, reflection, private attributes, classes, exceptions, annotations, f-strings or slice assignment.
Function defaults must be literals; subscript augmented assignment is unavailable: use x[i]=x[i]+1.
Available builtins: abs,min,max,sum,len,range,enumerate,zip,list,tuple,set,frozenset,dict,sorted,all,any,bool,int,float,str,round,reversed,print.
Only those builtins are available: isinstance and type are unavailable. All part IDs are already strings.
All numeric literals and computed numbers must be finite with absolute value <= 1000000000000 (1e12). Do not use 1e30, infinity, or other larger sentinel values.
Basic public list/dict/set methods are available. print is ignored. Generated policy AND skill opcodes share a 50000-opcode episode budget.
Trusted physics internals do not count as generated-code opcodes. Each code turn has a 120-second wall limit including physics calls.
Names reset each model turn; accepted physical state and previous feedback persist. Return plain code without markdown fences.
'''


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_library(library):
    if not isinstance(library, dict):
        raise ValueError("library must be a JSON object")
    for key in ("library_source", "exports", "skills"):
        if key not in library:
            raise ValueError("library missing " + key)
    validate_source(library["library_source"], exports=library["exports"], library=True)
    if not isinstance(library["skills"], list):
        raise ValueError("skill metadata must be a list")
    return canonical_hash(library)


def build_prompt(observation, decisions, checks_left, steps_left, library=None):
    guidance = {"available": False, "exports": []}
    if library is not None:
        guidance = {"available": True, "exports": library["exports"], "skills": library["skills"],
                    "source": library["library_source"],
                    "usage": "Call skills.EXPORTED_NAME(api, ...). You choose whether to call the real Python helpers. Their internal check/remove calls use your same budget."}
    data = {"observation": observation, "remaining_checker_calls": checks_left,
            "remaining_generated_opcodes": steps_left,
            "history": [{"code": d["response"]["code"], "execution": {
                k: d["execution"].get(k) for k in ("trace", "actions", "error", "skill_calls", "observation", "steps")}}
                for d in decisions if "response" in d]}
    return (API_SPEC + "\nTASK AND EXECUTION FEEDBACK:\n" + json.dumps(data, ensure_ascii=False)
            + "\nREUSABLE LIBRARY:\n" + json.dumps(guidance, ensure_ascii=False))


def solve_code(case_path, provider, library=None, max_calls=4, max_checks=24,
               max_steps=50000, execution_timeout=120.0, expected_observation_hash=None):
    from .simulator import DisassemblySim
    case_path = Path(case_path).resolve()
    for name, n in (("max_calls", max_calls), ("max_checks", max_checks), ("max_steps", max_steps)):
        if type(n) is not int or n < 1:
            raise ValueError(name + " must be a positive integer")
    library_hash = validate_library(library) if library is not None else None
    started = time.monotonic()
    sim = DisassemblySim(case_path, max_checks=max_checks, capture=False)
    observation, state = sim.snapshot(), sim.export_state()
    initial_observation = observation
    initial_hash = canonical_hash(initial_observation)
    if expected_observation_hash is not None and initial_hash != expected_observation_hash:
        raise ValueError("initial actor input differs from the frozen shared observation")
    trace, actions, decisions, skill_calls, usage = [], [], [], [], {}
    calls = checks = steps = 0
    success = bool(sim.success)
    provider_error = None
    termination = "call_budget_exhausted"
    while not success and calls < max_calls and checks < max_checks and steps < max_steps:
        prompt = build_prompt(observation, decisions, max_checks - checks, max_steps - steps, library)
        calls += 1
        try:
            value, meta = provider.complete(prompt, CODE_SCHEMA, calls)
            if (not isinstance(value, dict) or set(value) != {"code", "summary"}
                    or not all(isinstance(value[k], str) for k in value)):
                raise ProviderError("Expected exactly code and summary string fields")
        except (ProviderError, OSError) as exc:
            provider_error = str(exc)
            decisions.append({"call": calls, "provider_error": provider_error,
                              "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
            termination = "provider_error"
            break
        result = run_code(case_path, value["code"], state=state,
                          library_source=library["library_source"] if library else "",
                          exports=library["exports"] if library else [], max_checks=max_checks,
                          max_steps=max_steps - steps, timeout_seconds=execution_timeout)
        state = result["state"]
        observation = result["observation"] or observation
        trace, actions = result["trace"], result["actions"]
        checks, success = result["checker_calls"], result["success"]
        steps += result["steps"]
        skill_calls.extend({**record, "llm_call": calls} for record in result["skill_calls"])
        decisions.append({"call": calls, "response": value, "metadata": meta, "execution": result,
                          "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
        for key, n in meta.get("usage", {}).items():
            if isinstance(n, (int, float)):
                usage[key] = usage.get(key, 0) + n
        if (result.get("error") or {}).get("type") in ("WorkerError", "WallTimeLimit"):
            termination = "execution_worker_failure"
            break
    if success:
        termination = "goal_reached"
    elif provider_error is None and termination != "execution_worker_failure":
        if checks >= max_checks:
            termination = "check_budget_exhausted"
        elif steps >= max_steps:
            termination = "execution_step_budget_exhausted"
    return {"case_id": sim.case.get("id", case_path.stem), "case_path": str(case_path),
            "method": "with_library" if library is not None else "no_library",
            "success": success, "termination": termination,
            "initial_observation": initial_observation, "observation": observation, "state": state,
            "initial_observation_sha256": initial_hash,
            "actions": actions, "trace": trace, "decisions": decisions, "skill_calls": skill_calls,
            "checker_calls": checks, "execution_steps": steps, "llm_calls": calls,
            "token_usage": usage, "provider_error": provider_error,
            "removed_count": len(actions) if success else None, "accepted_removals": len(actions),
            "elapsed_seconds": time.monotonic() - started, "library_sha256": library_hash,
            "limits": {"max_calls": max_calls, "max_checks": max_checks, "max_steps": max_steps,
                       "execution_timeout": execution_timeout},
            "scope": "3D mesh removal path and MuJoCo post-removal stability under assumed physical parameters; no robot or force-controlled extraction."}

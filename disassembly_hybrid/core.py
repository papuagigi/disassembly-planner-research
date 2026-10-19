"""Graph-filtered, LLM-ranked DFS with executable local repair skills.

The original code-as-policy implementation is imported only for its trusted
simulator. This module does not modify it and does not expose arbitrary code
execution to the ranking model.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time

from .graph import (ConditionalBlockingGraph, DIRECTIONS, action_key,
                    canonical_candidates, physical_state_key)
from .skills import SKILL_CATALOG, SKILL_NAMES, apply_selected_skills

RANK_SCHEMA = {"type": "object", "properties": {
    "ordered_actions": {"type": "array", "items": {"type": "object", "properties": {
        "part_id": {"type": "string"},
        "direction": {"type": "string", "enum": list(DIRECTIONS)}},
        "required": ["part_id", "direction"], "additionalProperties": False}},
    "skills": {"type": "array", "items": {"type": "string", "enum": list(SKILL_NAMES)}},
    "summary": {"type": "string"}},
    "required": ["ordered_actions", "skills", "summary"], "additionalProperties": False}

RANK_INSTRUCTIONS = """Rank allowed actions for selective disassembly of a real 3D OBJ assembly.
Return only the required JSON object; do not use tools, write code, or inspect files.
Goal: remove the target through a verified sequence while every accepted step leaves the remainder stable.
The host owns depth-first search, branch restoration, query budgets, and physics validation.
Directions are world-axis straight translations; rotation and robot/grasp planning are out of scope.
The directed graph contains only observed blockers for specific directions in exact physical states.
It is not a global precedence DAG. Untested actions are uncertain, not infeasible.
Rank the supplied candidate part/direction pairs in ordered_actions. Omitted candidates are appended
in canonical order; duplicates are ignored. Never invent an action outside the candidates.
Select zero or more skill names in skills. Selected local skills reorder your frontier using current
feedback after each rejection. They only recommend; they cannot check/remove parts or bypass filters.
Skills persist for this node until you rank it again; a child inherits them if the LLM budget is exhausted.
The same shared checker budget pays for initial probes and all later remove attempts. A remove both
checks and commits in one call. Failed attempts leave state unchanged. Backtracking is hypothetical,
restores physical state, and never refunds checks. Search stops on the first verified target recovery.
Each model turn gives one ordering, not one action. The host may attempt many actions without calling
you again. Once the model-call cap is reached, it follows its existing ordering plus deterministic
canonical completion and selected skills. It does not call an extra model or use unseen test answers.
Prioritize success, then fewer removals and checks. Include a short factual summary.
"""


class PlannerInstructionLimit(RuntimeError):
    pass


def parse_ranking(value, candidates):
    if not isinstance(value, dict) or set(value) != {"ordered_actions", "skills", "summary"}:
        raise ValueError("ranking requires exactly ordered_actions, skills, summary")
    if not isinstance(value["summary"], str) or not isinstance(value["ordered_actions"], list):
        raise ValueError("invalid ranking or summary type")
    if not isinstance(value["skills"], list) or any(name not in SKILL_NAMES for name in value["skills"]):
        raise ValueError("invalid selected skill")
    allowed = {action_key(action): action for action in candidates}
    ordered, seen = [], set()
    for action in value["ordered_actions"]:
        if (not isinstance(action, dict) or set(action) != {"part_id", "direction"}
                or not all(isinstance(v, str) for v in action.values())):
            raise ValueError("malformed candidate action")
        key = action_key(action)
        if key not in allowed:
            raise ValueError("ranked action is not in the filtered candidates")
        if key not in seen:
            ordered.append(dict(allowed[key]))
            seen.add(key)
    omitted = [dict(action) for action in candidates if action_key(action) not in seen]
    skills = list(dict.fromkeys(value["skills"]))
    return ordered + omitted, skills, {"omitted_candidates": len(omitted),
                                      "duplicate_candidates": len(value["ordered_actions"]) - len(seen)}


def restore_branch(sim, saved_state):
    """Restore a branch's poses/actions while keeping all global expenditure."""
    checks, trace = sim.checks, copy.deepcopy(sim.trace)
    restored = copy.deepcopy(saved_state)
    restored.update(checks=checks, trace=trace)
    sim.restore_state(restored)
    assert sim.checks == checks and len(sim.trace) == len(trace)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _prompt(sim, context, frame, candidates):
    observation = sim.snapshot()
    initial = context["initial_observation"]
    extras = {key: value for key, value in initial.items() if key not in observation}
    current_graph = context["graph"].describe(frame["key"])
    extras["directed_blocking_graph"] = current_graph
    extras["common_probe_feedback_scope"] = "Frozen initial-state observations only; current hard exclusions are in directed_blocking_graph."
    payload = {"observation": {**observation, **extras},
               "directed_blocking_graph": current_graph,
               "current_state_feedback": context["graph"].evidence(frame["key"]),
               "candidate_actions": candidates,
               "current_path": sim.actions,
               "depth": len(context["stack"]) - 1,
               "shared_limits": context["limits"],
               "llm_calls_remaining_after_this_call": context["limits"]["max_calls"] - context["calls"] - 1,
               "backtracks_so_far": len(context["backtracks"]),
               "previous_model_decisions": [{"call": d["call"], "response": d.get("response"),
                                               "ranking_error": d.get("ranking_error")}
                                              for d in context["decisions"]],
               "available_skills": SKILL_CATALOG}
    return RANK_INSTRUCTIONS + "\nTASK AND FEEDBACK:\n" + json.dumps(payload, ensure_ascii=False)


def _rank(sim, context, frame, candidates, trigger):
    if context["calls"] >= context["limits"]["max_calls"]:
        return True
    prompt = _prompt(sim, context, frame, candidates)
    context["calls"] += 1
    decision = {"call": context["calls"], "trigger": trigger,
                "state_key": frame["key"], "depth": len(context["stack"]) - 1,
                "checks_before": sim.checks, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    context["decisions"].append(decision)
    provider = context["provider"]
    remaining = context["deadline"] - time.monotonic()
    if remaining <= 0:
        context["termination"] = "wall_time_budget_exhausted"
        return False
    old_timeout = getattr(provider, "timeout", None)
    if isinstance(old_timeout, (int, float)):
        provider.timeout = min(old_timeout, remaining)
    try:
        value, metadata = provider.complete(prompt, RANK_SCHEMA, context["calls"])
    except PlannerInstructionLimit:
        raise
    except Exception as exc:
        context["provider_error"] = str(exc)
        decision["provider_error"] = str(exc)
        context["termination"] = "provider_error"
        return False
    finally:
        if isinstance(old_timeout, (int, float)):
            provider.timeout = old_timeout
    decision.update(response=value, metadata=metadata)
    for key, value_ in metadata.get("usage", {}).items():
        if isinstance(value_, (int, float)):
            context["usage"][key] = context["usage"].get(key, 0) + value_
    if time.monotonic() >= context["deadline"]:
        context["termination"] = "wall_time_budget_exhausted"
        return False
    try:
        frame["ordered"], frame["skills"], normalization = parse_ranking(value, candidates)
        decision["normalization"] = normalization
    except ValueError as exc:
        # Malformed model output cannot introduce executable actions. Preserve
        # an earlier valid ordering or the canonical complete frontier.
        decision["ranking_error"] = str(exc)
        decision["fallback"] = "previous legal ordering with canonical completion"
    frame["failures_since_rank"] = 0
    return True


def _frame(sim, inherited_skills=()):
    state = sim.export_state()
    return {"state": state, "key": physical_state_key(state),
            "ordered": canonical_candidates(sim.snapshot()), "skills": list(inherited_skills),
            "explored": set(), "initialized": False, "failures_since_rank": 0}


def _search(sim, context):
    graph, stack = context["graph"], context["stack"]
    while stack and not sim.success:
        if time.monotonic() >= context["deadline"]:
            context["termination"] = "wall_time_budget_exhausted"
            break
        if sim.checks >= context["limits"]["max_checks"]:
            context["termination"] = "check_budget_exhausted"
            break
        frame = stack[-1]
        candidates = [action for action in graph.filter(frame["key"], frame["ordered"])
                      if action_key(action) not in frame["explored"]]
        if not candidates:
            finished = stack.pop()
            if not stack:
                context["termination"] = "search_frontier_exhausted"
                break
            before_checks = sim.checks
            restore_branch(sim, stack[-1]["state"])
            context["backtracks"].append({"from_state": finished["key"],
                                         "to_state": stack[-1]["key"],
                                         "checker_calls": sim.checks,
                                         "remaining": list(sim.remaining)})
            assert before_checks == sim.checks
            continue
        needs_feedback_rank = frame["failures_since_rank"] >= 6
        if not frame["initialized"] or needs_feedback_rank:
            trigger = "new_search_state" if not frame["initialized"] else "six_new_rejections"
            if not _rank(sim, context, frame, candidates, trigger):
                break
            frame["initialized"] = True
            candidates = [action for action in graph.filter(frame["key"], frame["ordered"])
                          if action_key(action) not in frame["explored"]]
        ordered, skill_records = apply_selected_skills(
            frame["skills"], candidates, sim.snapshot(), graph.evidence(frame["key"]))
        for record in skill_records:
            context["skill_calls"].append({**record, "state_key": frame["key"],
                                            "checks_before": sim.checks, "checks_after": sim.checks,
                                            "llm_call": context["calls"]})
        if not ordered:
            raise RuntimeError("skill frontier cannot remove all legal candidates")
        action = ordered[0]
        frame["explored"].add(action_key(action))
        before = sim.checks
        result = sim.remove(action["part_id"], action["direction"])
        if sim.checks != before + 1:
            raise RuntimeError("trusted simulator did not charge exactly one checker call")
        sim.trace[-1].update(search_state_key=frame["key"], search_depth=len(stack) - 1,
                             search_branch=len(context["explored_actions"]))
        graph.add(frame["key"], result)
        if result.get("valid"):
            context["explored_actions"].append({**copy.deepcopy(sim.actions[-1]),
                                                "checker_call": sim.checks,
                                                "from_state": frame["key"],
                                                "to_state": physical_state_key(sim.export_state())})
        if time.monotonic() >= context["deadline"]:
            context["termination"] = "wall_time_budget_exhausted"
            context["goal_after_deadline"] = bool(sim.success)
            break
        if result.get("valid"):
            if sim.success:
                context["termination"] = "goal_reached"
                break
            stack.append(_frame(sim, frame["skills"]))
        else:
            frame["failures_since_rank"] += 1


def solve_hybrid(case_path, provider, max_calls=4, max_checks=24,
                 timeout_seconds=480, initial_state=None, initial_observation=None,
                 simulator_factory=None, max_steps=1000000, **kwargs):
    """Return a bounded system-comparison result without altering old files.

    The wall deadline includes provider time. A single native physics operation
    is checked immediately after completion, so OS-level preemption requires a
    parent worker timeout. Opcode counts cover only new planner/graph/skill
    frames; trusted physics and inference internals are excluded.
    """
    for name, value in (("max_calls", max_calls), ("max_checks", max_checks)):
        if type(value) is not int or value < 0:
            raise ValueError(name + " must be a nonnegative integer")
    if max_steps is not None and (type(max_steps) is not int or max_steps < 0):
        raise ValueError("max_steps must be None or a nonnegative integer")
    if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive and finite")
    started = time.monotonic()
    if simulator_factory is None:
        from disassembly_mujoco.simulator import DisassemblySim
        simulator_factory = DisassemblySim
    sim = simulator_factory(case_path, max_checks=max_checks, capture=False, state=initial_state)
    observation = copy.deepcopy(initial_observation if initial_observation is not None else sim.snapshot())
    if sim.checks > max_checks:
        raise ValueError("initial probes exceed the checker budget")
    if kwargs.get("expected_observation_hash") not in (None, _hash(observation)):
        raise ValueError("initial actor input differs from frozen shared observation")
    graph = ConditionalBlockingGraph()
    initial_key = physical_state_key(sim.export_state())
    for record in sim.trace:
        # The common initial probes are noncommitting checks in the frozen
        # initial state. Never attach an earlier-state removal to this state.
        if (record.get("operation") == "check" and not record.get("committed")
                and set(record.get("remaining_before", sim.remaining)) == set(sim.remaining)):
            graph.add(initial_key, record)
    limits = {"max_calls": max_calls, "max_checks": max_checks,
              "max_steps": max_steps, "total_wall_seconds": timeout_seconds}
    context = {"provider": provider, "initial_observation": observation,
               "graph": graph, "limits": limits, "deadline": started + timeout_seconds,
               "stack": [_frame(sim)], "calls": 0, "decisions": [], "skill_calls": [],
               "explored_actions": [], "backtracks": [], "usage": {},
               "provider_error": None, "termination": "unknown", "steps": 0}
    allowed_files = {str(Path(__file__).resolve()),
                     str(Path(__file__).with_name("graph.py").resolve()),
                     str(Path(__file__).with_name("skills.py").resolve())}
    previous_trace = sys.gettrace()

    def instruction_trace(frame, event, arg):
        if frame.f_code.co_filename not in allowed_files:
            return None
        if event == "call":
            frame.f_trace_opcodes = True
            frame.f_trace_lines = False
        elif event == "opcode":
            if max_steps is not None and context["steps"] >= max_steps:
                raise PlannerInstructionLimit("planner instruction budget exhausted")
            context["steps"] += 1
        return instruction_trace

    error = None
    try:
        sys._getframe().f_trace_opcodes = True
        sys.settrace(instruction_trace)
        _search(sim, context)
    except PlannerInstructionLimit as exc:
        context["termination"] = "execution_step_budget_exhausted"
        error = {"type": type(exc).__name__, "message": str(exc)}
    except Exception as exc:
        context["termination"] = "planner_error"
        error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        sys.settrace(previous_trace)
    # A planner-opcode interruption may occur after a trusted, atomic simulator
    # operation but before planner-side bookkeeping. Reconcile from the trusted
    # global trace so performed removals and charged checks are never hidden.
    recorded_checks = {action["checker_call"] for action in context["explored_actions"]}
    for record in sim.trace:
        if record.get("committed") and record["checker_call"] not in recorded_checks:
            context["explored_actions"].append({
                "part_id": record["part_id"], "direction": record["direction"],
                "stability": record.get("stability"), "checker_call": record["checker_call"],
                "from_state": record.get("search_state_key"),
                "to_state": None, "interrupted_bookkeeping": True})
    context["explored_actions"].sort(key=lambda action: action["checker_call"])
    if sim.success and time.monotonic() >= context["deadline"] and context["termination"] != "goal_reached":
        context["goal_after_deadline"] = True
    within_wall_budget = not context.get("goal_after_deadline", False)
    success = bool(sim.success) and within_wall_budget
    if success:
        context["termination"] = "goal_reached"
    elif time.monotonic() >= context["deadline"] and context["termination"] != "provider_error":
        context["termination"] = "wall_time_budget_exhausted"
    status = "PASS" if success else "UNKNOWN"
    return {"case_id": sim.case.get("id", Path(case_path).stem),
            "case_path": str(Path(case_path).resolve()), "method": "graph_llm_dfs_library",
            "success": success, "status": status, "termination": context["termination"],
            "goal_reached_after_deadline": context.get("goal_after_deadline", False),
            "initial_observation": observation, "initial_observation_sha256": _hash(observation),
            "observation": sim.snapshot(), "state": sim.export_state(),
            "actions": copy.deepcopy(sim.actions), "trace": copy.deepcopy(sim.trace),
            "explored_actions": context["explored_actions"], "backtracks": context["backtracks"],
            "decisions": context["decisions"], "skill_calls": context["skill_calls"],
            "checker_calls": sim.checks, "execution_steps": context["steps"],
            "llm_calls": context["calls"], "token_usage": context["usage"],
            "provider_error": context["provider_error"], "error": error,
            "removed_count": len(sim.actions) if success else None,
            "accepted_removals": len(sim.actions),
            "explored_accepted_removals": len(context["explored_actions"]),
            "elapsed_seconds": time.monotonic() - started, "limits": limits,
            "library_sha256": hashlib.sha256(Path(__file__).with_name("skills.py").read_bytes()).hexdigest(),
            "initial_graph": graph.describe(initial_key),
            "search": {"algorithm": "depth_first_first_feasible", "minimum_guarantee": False,
                       "graph_scope": "exact physical state and extraction direction",
                       "post_llm_budget": "existing ordering, canonical completion, selected local skills",
                       "backtracking": "hypothetical full physical state restoration; no budget refund"},
            "scope": "Sampled 6-axis straight mesh extraction followed by MuJoCo remainder stability under assumed gravity/friction. "
                     "No robot, force-controlled extraction, rotation search, or real-world validation."}

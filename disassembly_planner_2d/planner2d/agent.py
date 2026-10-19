"""LLM proposal -> independent check -> feedback. No heuristic fallback."""
from __future__ import annotations

import json
import time

from .geometry import apply_action, initial_state, is_goal, validate_scene
from .llm import ProviderError, parse_plan


def build_prompt(scene: dict, remaining: frozenset, trace: list[dict], library=None) -> str:
    from .skills import prompt_guidance
    guidance = prompt_guidance(library) if library is not None else "[]"
    observation = {"workspace": scene["workspace"], "target_id": scene["target_id"],
                   "remaining_parts": [{key: part[key] for key in
                       ("id", "rects", "allowed_directions", "fixed")}
                       for part in scene["parts"] if part["id"] in remaining]}
    feedback = [{"remaining_before": t["remaining_before"], "action": t["action"],
                 "valid": t["check"]["valid"], "reason": t["check"]["reason"],
                 "blockers": t["check"]["blockers"]} for t in trace]
    return (
        "You are a 2D disassembly sequence planner. Use ONLY the supplied observation, feedback, and optional experience guidance below. "
        "Do not invoke tools, read files, run code, browse, or modify anything. "
        "Your objective is to recover target_id with as few removed parts as possible. "
        "Coordinates use +x right and +y up. A rectangle is [x_min,y_min,width,height]. "
        "Each part is the UNION of its rectangles. An action translates a whole part straight "
        "in the specified direction until all of it is outside workspace. Interior intersection "
        "anywhere along the full path is a collision; boundary touching is allowed. "
        "Fixed parts cannot move. Only allowed_directions may be used. Removed parts disappear. "
        "This is geometric reasoning only, with no gravity, friction, rotation, or robot arm. "
        "Propose a short sequence of actions from the CURRENT state that recovers the target. "
        "A separate trusted checker will execute actions in order, stopping at the first rejected "
        "action. You will receive the actual feedback in a later call. Rejected actions do NOT "
        "change the state. Do not repeat a rejected state/action; remove blockers or choose another "
        "direction. Do not invent part IDs. Do not remove fixed walls. "
        "Return the required JSON actions array and a brief Korean summary of the strategy. "
        "The summary is a proposal, NOT evidence that the plan is valid.\nOBSERVATION:\n"
        + json.dumps(observation, ensure_ascii=False, separators=(",", ":"))
        + "\nACTUAL CHECKER FEEDBACK:\n" + json.dumps(feedback, ensure_ascii=False, separators=(",", ":"))
        + "\nOPTIONAL EXPERIENCE GUIDANCE:\n"
        + guidance
        + "\nThese are generalized hints from development demonstrations, if present. "
        "Their source paths passed a checker; this does not prove they apply to this state. "
        "Use only hints consistent with the observation. Every action must still pass the same checker.")


def solve_llm(scene: dict, provider, max_calls: int = 4, max_checks: int = 24,
              initial_actions: list[dict] | None = None, library=None) -> dict:
    """A pure provider is injectable for unit tests; provenance remains explicit.

    initial_actions is an explicitly labelled recovery exercise, not normal LLM
    performance. It can demonstrate that real rejection feedback is handled.
    """
    validate_scene(scene)
    if type(max_calls) is not int or type(max_checks) is not int or min(max_calls, max_checks) < 1:
        raise ValueError("max_calls and max_checks must be positive integers")
    started = time.monotonic()
    remaining = initial_state(scene)
    trace, actions, decisions = [], [], []
    attempted, usage = set(), {}
    llm_calls = 0
    termination = "call_budget_exhausted"
    provider_error = None
    pending_seed = initial_actions is not None
    while not is_goal(scene, remaining) and len(trace) < max_checks:
        if pending_seed:
            proposed = parse_plan({"actions": initial_actions, "summary": "Explicit recovery exercise"})
            source = "scripted_recovery_seed"
            pending_seed = False
        else:
            if llm_calls >= max_calls:
                break
            llm_calls += 1
            prompt = build_prompt(scene, remaining, trace, library=library)
            try:
                proposed, meta = provider.propose(prompt, llm_calls)
                proposed = parse_plan(proposed)
            except (ProviderError, OSError) as exc:
                termination, provider_error = "provider_error", str(exc)
                break
            decisions.append({"call": llm_calls, "response": proposed, "metadata": meta})
            for key, value in meta.get("usage", {}).items():
                if isinstance(value, (int, float)):
                    usage[key] = usage.get(key, 0) + value
            source = provider.name
        no_new_check = True
        for action in proposed["actions"]:
            if len(trace) >= max_checks or is_goal(scene, remaining):
                break
            signature = (remaining, action["part_id"], action["direction"])
            if signature in attempted:
                break
            attempted.add(signature)
            no_new_check = False
            before = remaining
            remaining, check = apply_action(scene, remaining, action)
            trace.append({"step": len(trace) + 1, "remaining_before": sorted(before),
                          "action": action, "check": check, "remaining_after": sorted(remaining),
                          "proposal_source": source, "llm_call": llm_calls})
            if check["valid"]:
                actions.append(action)
            else:
                break
        if no_new_check:
            termination = "repeated_proposal"
            break
    success = is_goal(scene, remaining)
    if success:
        termination = "goal_reached"
    elif len(trace) >= max_checks:
        termination = "check_budget_exhausted"
    return {"scene_id": scene["id"], "method": "llm_feedback", "success": success,
            "termination": termination, "actions": actions, "trace": trace,
            "checker_calls": len(trace), "failed_candidates": sum(not t["check"]["valid"] for t in trace),
            "elapsed_seconds": time.monotonic() - started,
            "removed_count": len(actions) if success else None, "llm_calls": llm_calls,
            "token_usage": usage, "provider": provider.name, "decisions": decisions,
            "provider_error": provider_error, "remaining": sorted(remaining),
            "provenance": ((provider.name + "_with_scripted_recovery_seed") if decisions else "scripted_seed_only")
                if initial_actions is not None else provider.name,
            "evaluation_kind": "recovery_exercise" if initial_actions is not None else "prototype_smoke_test",
            "limits": {"max_calls": max_calls, "max_checks": max_checks},
            "library_sha256": library.get("sha256") if library is not None else None,
            "library_entries_supplied": len(library.get("skills", [])) if library is not None else 0,
            "scope": "2D axis translation and geometry only; not physical robot feasibility"}

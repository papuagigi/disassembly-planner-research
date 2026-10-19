"""Executable LOCAL recommendations distilled from the frozen recover_target.

These helpers only return candidate orderings.  They cannot inspect the
simulator, run a check, remove a part, restore a state, or consume a hidden
physics budget. Their output is intersected with the graph-filtered frontier.

Provenance: manually factored from the previously developed recover_target's
blocker-chain, upward/outward direction and unstable-part heuristics. This is
an ASPIRE-inspired reuse mechanism, not automatic skill discovery or training.
No held-out evaluation assembly was used to write these functions.
"""
from __future__ import annotations

from .graph import action_key

SKILL_CATALOG = [
    {"name": "dependency_priority", "description":
     "Prioritize the deepest known movable blockers of the target in this exact-state directed graph. "
     "Unknown alternative directions remain candidates; this recommendation is not a hard precedence."},
    {"name": "direction_preference", "description":
     "Keep the chosen part order, but use the frozen recover_target upward/outward direction score relative to the target."},
    {"name": "stability_priority", "description":
     "Prefer candidate parts reported as moving in a rejected remainder-stability check. "
     "This is a repair heuristic, not a stability guarantee."},
]
SKILL_NAMES = tuple(skill["name"] for skill in SKILL_CATALOG)


def dependency_priority(candidates, observation, evidence):
    target = observation["target_id"]
    movable = {p["id"] for p in observation["remaining_parts"] if not p.get("fixed", False)}
    blockers = {}
    for result in evidence:
        if result.get("reason") == "path_collision":
            blockers.setdefault(result["part_id"], set()).update(
                p for p in result.get("blockers", []) if p in movable)
    depth = {target: 0}

    def visit(part, path):
        # Cycles can occur because edges concern different directions. Never
        # interpret them as infeasibility or recurse through a cycle forever.
        for blocker in sorted(blockers.get(part, ())):
            if blocker in path:
                continue
            depth[blocker] = max(depth.get(blocker, 0), len(path))
            visit(blocker, path + (blocker,))

    visit(target, (target,))
    return sorted(candidates, key=lambda action: -depth.get(action["part_id"], -1))


def direction_preference(candidates, observation, evidence):
    del evidence
    parts = {p["id"]: p for p in observation["remaining_parts"]}
    if not parts:
        return list(candidates)
    target = parts.get(observation["target_id"])
    if target is None:
        return list(candidates)
    def center(part):
        return part.get("center", [(part["bounds"][0][axis] + part["bounds"][1][axis]) / 2
                                   for axis in range(3)])
    target_center = center(target)
    part_order = {}
    for action in candidates:
        part_order.setdefault(action["part_id"], len(part_order))
    ranks = {}
    for pid, part in parts.items():
        ranked = []
        for direction, axis, sign in (("+z", 2, 1), ("+x", 0, 1), ("-x", 0, -1),
                                      ("+y", 1, 1), ("-y", 1, -1), ("-z", 2, -1)):
            width = max(part["bounds"][1][axis] - part["bounds"][0][axis], 0.000001)
            outward = sign * (center(part)[axis] - target_center[axis]) / width
            score = (0 if direction == "+z" else 2 if direction == "-z" else 1) - min(1, max(-1, outward))
            ranked.append((score, direction))
        preferred = [direction for _, direction in sorted(ranked)]
        ranks[pid] = {direction: i for i, direction in enumerate(preferred)}
    return sorted(candidates, key=lambda action: (part_order[action["part_id"]],
                                                  ranks[action["part_id"]][action["direction"]]))


def stability_priority(candidates, observation, evidence):
    del observation
    unstable = set()
    for result in evidence:
        if result.get("reason") == "unstable_remainder":
            unstable.update((result.get("stability") or {}).get("unstable_parts", []))
    return sorted(candidates, key=lambda action: action["part_id"] not in unstable)


_FUNCTIONS = {"dependency_priority": dependency_priority,
              "direction_preference": direction_preference,
              "stability_priority": stability_priority}


def apply_selected_skills(names, candidates, observation, evidence):
    """Apply only explicitly selected skills; never extend the legal frontier."""
    allowed = {action_key(action): action for action in candidates}
    ordered = list(candidates)
    records = []
    for name in names:
        if name not in _FUNCTIONS:
            raise ValueError("unknown local skill: " + str(name))
        proposed = _FUNCTIONS[name](ordered, observation, evidence)
        seen = set()
        filtered = []
        for action in proposed + ordered:
            key = action_key(action)
            if key in allowed and key not in seen:
                seen.add(key)
                filtered.append(dict(allowed[key]))
        records.append({"name": name, "input_candidates": len(ordered),
                        "ordered_actions": filtered, "physics_calls": 0,
                        "role": "recommendation only; DFS owns execution"})
        ordered = filtered
    return ordered, records

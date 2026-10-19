"""Deterministic search baselines for the finite 2D removal model.

The exact baseline minimizes the number of removals, including the target.
The heuristic uses observed target failures to prioritize direct blockers, then
prefers short exterior translations. It backtracks rather than declaring a
scene impossible after one failed action. Neither method invokes an LLM.

Trace entries are chronological *search trials*, not one physical trajectory.
Each entry therefore carries the complete branch state before and after its
checker call. ``actions`` contains only the final solution path, if one exists.
"""

from collections import deque
from time import perf_counter

from .geometry import candidate_actions, check_action, initial_state, is_goal, validate_scene


_DIRECTION_ORDER = {"up": 0, "down": 1, "left": 2, "right": 3}


def _start(scene, max_checks):
    if isinstance(max_checks, bool) or not isinstance(max_checks, int) or max_checks < 0:
        raise ValueError("max_checks must be a non-negative integer")
    validate_scene(scene)
    return initial_state(scene)


def _ordered_actions(scene, remaining):
    return sorted(
        candidate_actions(scene, remaining),
        key=lambda action: (
            action["part_id"] != scene["target_id"],
            action["part_id"],
            _DIRECTION_ORDER[action["direction"]],
        ),
    )


def _record_check(scene, remaining, action, trace):
    check = check_action(scene, remaining, action)
    after = remaining - {action["part_id"]} if check["valid"] else remaining
    trace.append(
        {
            "step": len(trace) + 1,
            "remaining_before": sorted(remaining),
            "action": dict(action),
            "check": check,
            "remaining_after": sorted(after),
        }
    )
    return after, check


def _result(scene, method, termination, actions, trace, started):
    success = termination == "goal_reached"
    result = {
        "scene_id": scene["id"],
        "method": method,
        "success": success,
        "termination": termination,
        "actions": [dict(action) for action in actions] if success else [],
        "trace": trace,
        "checker_calls": len(trace),
        "elapsed_seconds": perf_counter() - started,
        "removed_count": len(actions) if success else None,
    }
    if method == "exact_bfs":
        if success:
            note = (
                "BFS proves minimum removals, including the target, within this "
                "2D axis-aligned translation model."
            )
        elif termination == "search_exhausted":
            note = "No solution exists within this finite 2D removal model."
        else:
            note = "Budget exhausted; feasibility and optimality remain unknown."
        result["optimality"] = note
    else:
        result["optimality"] = "Heuristic search does not certify minimum removals."
    return result


def solve_exact(scene, max_checks=100000):
    """Return a shortest valid removal path by breadth-first search.

    A state is the set of remaining part IDs. Every successful action removes
    one part at unit cost. Alternative directions reaching an already visited
    state need no further checker calls. Budget exhaustion is not infeasibility.
    """
    started = perf_counter()
    initial = _start(scene, max_checks)
    trace = []
    queue = deque([(initial, [])])
    visited = {initial}
    attempted = set()

    while queue:
        remaining, path = queue.popleft()
        if is_goal(scene, remaining):
            return _result(scene, "exact_bfs", "goal_reached", path, trace, started)
        for action in _ordered_actions(scene, remaining):
            successor = remaining - {action["part_id"]}
            key = (remaining, action["part_id"], action["direction"])
            if successor in visited or key in attempted:
                continue
            if len(trace) >= max_checks:
                return _result(scene, "exact_bfs", "budget_exhausted", [], trace, started)
            attempted.add(key)
            after, check = _record_check(scene, remaining, action, trace)
            if not check["valid"]:
                continue
            next_path = path + [dict(action)]
            if is_goal(scene, after):
                return _result(scene, "exact_bfs", "goal_reached", next_path, trace, started)
            visited.add(after)
            queue.append((after, next_path))

    return _result(scene, "exact_bfs", "search_exhausted", [], trace, started)


def _exterior_distance(scene, part, direction):
    """Geometry-only ranking estimate; this does not check collision clearance."""
    xmin, ymin, xmax, ymax = scene["workspace"]
    rects = part["rects"]
    bounds = (
        min(rect[0] for rect in rects),
        min(rect[1] for rect in rects),
        max(rect[0] + rect[2] for rect in rects),
        max(rect[1] + rect[3] for rect in rects),
    )
    distances = {
        "up": ymax - bounds[1],
        "down": bounds[3] - ymin,
        "left": bounds[2] - xmin,
        "right": xmax - bounds[0],
    }
    return max(0.0, distances[direction])


def _rank_non_target_actions(scene, actions, target_failures, parts):
    # Favor blockers of target exits that contain no permanently fixed part.
    # The set sizes are a ranking signal, not an admissible cost estimate.
    relevance = {}
    for failure in target_failures:
        blockers = failure.get("blockers", [])
        if not blockers or any(parts[part_id].get("fixed", False) for part_id in blockers):
            continue
        for part_id in blockers:
            relevance[part_id] = min(relevance.get(part_id, float("inf")), len(blockers))
    return sorted(
        actions,
        key=lambda action: (
            relevance.get(action["part_id"], float("inf")),
            _exterior_distance(scene, parts[action["part_id"]], action["direction"]),
            action["part_id"],
            _DIRECTION_ORDER[action["direction"]],
        ),
    )


def solve_heuristic(scene, max_checks=80):
    """Try target exits, then blockers and exterior parts, with DFS backtracking.

    Every actual geometry query, including failed target attempts, consumes one
    budget unit. Cached state-action attempts and already explored states do not
    consume additional units. No random choices or hidden checker calls occur.
    """
    started = perf_counter()
    initial = _start(scene, max_checks)
    trace = []
    visited = {initial}
    attempted = set()
    parts = {part["id"]: part for part in scene["parts"]}

    def make_frame(remaining, path):
        actions = _ordered_actions(scene, remaining)
        return {
            "remaining": remaining,
            "path": path,
            "targets": deque(a for a in actions if a["part_id"] == scene["target_id"]),
            "others": [a for a in actions if a["part_id"] != scene["target_id"]],
            "failures": [],
            "ranked": None,
        }

    stack = [make_frame(initial, [])]
    while stack:
        frame = stack[-1]
        remaining = frame["remaining"]
        if is_goal(scene, remaining):
            return _result(scene, "heuristic_dfs", "goal_reached", frame["path"], trace, started)
        if frame["targets"]:
            action = frame["targets"].popleft()
        else:
            if frame["ranked"] is None:
                frame["ranked"] = deque(
                    _rank_non_target_actions(scene, frame["others"], frame["failures"], parts)
                )
            if not frame["ranked"]:
                stack.pop()
                continue
            action = frame["ranked"].popleft()

        successor = remaining - {action["part_id"]}
        key = (remaining, action["part_id"], action["direction"])
        if successor in visited or key in attempted:
            continue
        if len(trace) >= max_checks:
            return _result(scene, "heuristic_dfs", "budget_exhausted", [], trace, started)
        attempted.add(key)
        after, check = _record_check(scene, remaining, action, trace)
        if not check["valid"]:
            if action["part_id"] == scene["target_id"]:
                frame["failures"].append(check)
            continue
        next_path = frame["path"] + [dict(action)]
        if is_goal(scene, after):
            return _result(scene, "heuristic_dfs", "goal_reached", next_path, trace, started)
        visited.add(after)
        stack.append(make_frame(after, next_path))

    return _result(scene, "heuristic_dfs", "search_exhausted", [], trace, started)

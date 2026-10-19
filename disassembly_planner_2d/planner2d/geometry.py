"""Exact axis-aligned, straight-line geometry for a deliberately limited model.

Coordinates are Cartesian: ``up`` increases y. Each part is a union of
rectangles [x, y, width, height]. Boundary contact is allowed. No gravity,
friction, rotation, deformation, grasping or robot kinematics is simulated.
"""

import math
import re
from collections.abc import Mapping


DIRECTIONS = ("up", "down", "left", "right")


def _number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _overlap(a, b):
    """True only for positive-area intersection; touching edges are free."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (max(ax, bx) < min(ax + aw, bx + bw)
            and max(ay, by) < min(ay + ah, by + bh))


def validate_scene(scene):
    """Validate schema, dimensions and initial inter-part nonpenetration."""
    if not isinstance(scene, Mapping):
        raise ValueError("scene must be a mapping")
    for field in ("id", "name", "description", "target_id"):
        if not isinstance(scene.get(field), str) or not scene[field].strip():
            raise ValueError("scene requires a nonempty " + field)
    if scene.get("split") not in ("development", "evaluation"):
        raise ValueError("split must be development or evaluation")
    workspace = scene.get("workspace")
    if not isinstance(workspace, (list, tuple)) or len(workspace) != 4 or not all(map(_number, workspace)):
        raise ValueError("workspace must contain four finite numbers")
    xmin, ymin, xmax, ymax = workspace
    if not (xmin < xmax and ymin < ymax):
        raise ValueError("workspace must have positive dimensions")
    parts = scene.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("parts must be a nonempty list")
    seen = set()
    for part in parts:
        if not isinstance(part, Mapping):
            raise ValueError("part must be a mapping")
        pid = part.get("id")
        if not isinstance(pid, str) or not pid or pid in seen:
            raise ValueError("part ids must be unique nonempty strings")
        seen.add(pid)
        if not isinstance(part.get("label"), str) or not part["label"]:
            raise ValueError("part requires a label: " + pid)
        if not isinstance(part.get("fixed"), bool):
            raise ValueError("fixed must be a boolean: " + pid)
        if not isinstance(part.get("color"), str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", part["color"]):
            raise ValueError("color must be #RRGGBB: " + pid)
        directions = part.get("allowed_directions")
        if (not isinstance(directions, list)
                or any(not isinstance(d, str) or d not in DIRECTIONS for d in directions)
                or len(set(directions)) != len(directions)):
            raise ValueError("invalid allowed_directions: " + pid)
        if not part["fixed"] and not directions:
            raise ValueError("movable part needs an allowed direction: " + pid)
        rects = part.get("rects")
        if not isinstance(rects, list) or not rects:
            raise ValueError("part requires rectangles: " + pid)
        for rect in rects:
            if not isinstance(rect, (list, tuple)) or len(rect) != 4 or not all(map(_number, rect)):
                raise ValueError("rectangle needs four finite numbers: " + pid)
            x, y, w, h = rect
            if w <= 0 or h <= 0:
                raise ValueError("rectangle dimensions must be positive: " + pid)
            if x < xmin or y < ymin or x + w > xmax or y + h > ymax:
                raise ValueError("rectangle lies outside workspace: " + pid)
    for i, first in enumerate(parts):
        for second in parts[i + 1:]:
            if any(_overlap(a, b) for a in first["rects"] for b in second["rects"]):
                raise ValueError("initial interior overlap: %s and %s" % (first["id"], second["id"]))
    target = next((p for p in parts if p["id"] == scene["target_id"]), None)
    if target is None or target["fixed"]:
        raise ValueError("target must identify a movable part")


def initial_state(scene):
    return frozenset(part["id"] for part in scene["parts"])


def candidate_actions(scene, remaining):
    return [{"part_id": part["id"], "direction": direction}
            for part in scene["parts"]
            if part["id"] in remaining and not part["fixed"]
            for direction in part["allowed_directions"]]


def _result(valid, reason, blockers=None, distance=0.0, swept_rects=None):
    return {"valid": valid, "reason": reason, "blockers": blockers or [],
            "distance": float(distance), "swept_rects": swept_rects or []}


def check_action(scene, remaining, action):
    """Check the entire continuous path, not sampled animation frames.

    All component rectangles translate by the same distance. Their swept
    rectangles form exactly the swept union for one axis-aligned translation.
    The terminal part has no interior inside the workspace (touch is allowed).
    ``scene`` must already have passed ``validate_scene``.
    """
    if not isinstance(action, Mapping):
        return _result(False, "invalid_action")
    pid, direction = action.get("part_id"), action.get("direction")
    if not isinstance(pid, str) or not isinstance(direction, str):
        return _result(False, "invalid_action")
    part = next((p for p in scene["parts"] if p["id"] == pid), None)
    if part is None:
        return _result(False, "unknown_part")
    if pid not in remaining:
        return _result(False, "already_removed")
    if part["fixed"]:
        return _result(False, "fixed_part")
    if direction not in part["allowed_directions"]:
        return _result(False, "direction_not_allowed")
    xmin, ymin, xmax, ymax = scene["workspace"]
    rects = part["rects"]
    if direction == "right":
        distance = xmax - min(r[0] for r in rects)
        swept = [[x, y, w + distance, h] for x, y, w, h in rects]
    elif direction == "left":
        distance = max(r[0] + r[2] for r in rects) - xmin
        swept = [[x - distance, y, w + distance, h] for x, y, w, h in rects]
    elif direction == "up":
        distance = ymax - min(r[1] for r in rects)
        swept = [[x, y, w, h + distance] for x, y, w, h in rects]
    else:  # down
        distance = max(r[1] + r[3] for r in rects) - ymin
        swept = [[x, y - distance, w, h + distance] for x, y, w, h in rects]
    blockers = sorted(other["id"] for other in scene["parts"]
                      if other["id"] != pid and other["id"] in remaining
                      and any(_overlap(a, b) for a in swept for b in other["rects"]))
    return _result(not blockers, "collision" if blockers else "clear", blockers, distance, swept)


def apply_action(scene, remaining, action):
    check = check_action(scene, remaining, action)
    state = frozenset(remaining)
    if check["valid"]:
        state = state - {action["part_id"]}
    return state, check


def is_goal(scene, remaining):
    return scene["target_id"] not in remaining


def observation(scene, remaining):
    """Public geometry only: no feasible-action labels or solution sequence."""
    return {"scene_id": scene["id"], "workspace": list(scene["workspace"]),
            "target_id": scene["target_id"],
            "parts": [{"id": p["id"], "label": p["label"],
                       "rects": [list(r) for r in p["rects"]],
                       "allowed_directions": list(p["allowed_directions"]),
                       "fixed": p["fixed"]}
                      for p in scene["parts"] if p["id"] in remaining]}

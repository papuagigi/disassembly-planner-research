"""Frozen synthetic stress cases for the second, explicitly harder evaluation.

These designs are fixed before running either LLM condition. They increase
geometric dependency depth and alternative-route costs; no model output was
used to choose the layouts. IDs and part order are deterministically shuffled.
Descriptions are administrative metadata and must not enter model prompts.
The world model is unchanged: independent rectangle unions, straight complete
extraction, boundary contact allowed, no gravity or rotation.
"""

from copy import deepcopy
import random

from .geometry import candidate_actions, check_action, initial_state


def _part(name, rects, directions, fixed=False):
    return {"id": name, "label": name, "rects": rects,
            "allowed_directions": list(directions), "fixed": fixed,
            "color": "#687586" if fixed else "#66b9ae"}


def _opaque_scene(sid, parts, workspace, seed):
    rng = random.Random(seed)
    non_target = [part["id"] for part in parts if part["id"] != "target"]
    opaque = ["p%02d" % number for number in range(1, len(non_target) + 1)]
    rng.shuffle(opaque)
    names = dict(zip(non_target, opaque))
    for part in parts:
        part["id"] = names.get(part["id"], "target")
        part["label"] = "Target" if part["id"] == "target" else "Part " + part["id"]
        if part["id"] == "target":
            part["color"] = "#ec7272"
    rng.shuffle(parts)
    return {"id": sid, "name": sid.replace("_", " ").title(),
            "description": "A preregistered synthetic stress-test assembly.",
            "split": "evaluation", "workspace": workspace,
            "target_id": "target", "parts": parts}


def _grid(sid, rows, target, seed, compound_cells=()):
    """Rows are listed bottom to top; X denotes a fixed component."""
    parts = []
    for row, values in enumerate(rows):
        for col, value in enumerate(values):
            x, y = 2 + 5 * col, 2 + 5 * row
            rects = [[x, y, 2, 2]]
            if (col, row) in compound_cells:
                # A connected L, not its full bounding box.
                rects = [[x, y, 2, 0.75], [x, y + 0.75, 0.75, 1.25]]
            name = "target" if (col, row) == target else "cell_%d_%d" % (col, row)
            parts.append(_part(name, rects, [] if value == "X" else value.split("/"), value == "X"))
    return _opaque_scene(sid, parts, [0, 0, 5 * len(rows[0]) + 3, 5 * len(rows) + 3], seed)


def _window():
    parts = [
        _part("target", [[8, 14, 2, 1]], ["right"]),
        _part("window", [[20, 4, 1, 10], [20, 15, 1, 11]], [], True),
        _part("shutter", [[22, 12, 1, 5]], ["up", "down"]),
        _part("upper_a", [[21, 20, 3, 1], [23, 21, 1, 2]], ["left", "right"]),
        _part("upper_b", [[27, 19, 1, 3]], ["up"]),
        _part("upper_c", [[26, 27, 3, 1], [28, 26, 1, 1]], ["left"]),
        _part("upper_d", [[13, 27, 2, 1]], ["left"]),
        _part("lower_e", [[22, 8, 1, 1]], ["left", "down"]),
        _part("lower_f", [[21, 4, 3, 1], [21, 5, 1, 1]], ["right"]),
        _part("lower_g", [[28, 3, 1, 4]], ["down"]),
        _part("lower_h", [[28, 1, 1, 1]], ["right"]),
        _part("extra_a", [[2, 4, 2, 2]], ["left", "up"]),
        _part("extra_b", [[6, 4, 2, 2]], ["left"]),
        _part("extra_c", [[10, 4, 2, 2]], ["down"]),
        _part("extra_d", [[3, 20, 2, 2]], ["up", "right"]),
        _part("extra_e", [[12, 18, 2, 2]], ["down"]),
    ]
    return _opaque_scene("challenge_03", parts, [0, 0, 32, 32], 4303)


_CHALLENGES = [
    _grid("challenge_01", [
        ["X", "down", "down", "down"],
        ["left", "up/right", "up", "up"],
        ["up", "left", "up", "right"],
        ["left", "left", "left", "right"],
    ], (1, 1), 4301, {(0, 2), (2, 2), (3, 1)}),
    _grid("challenge_02", [
        ["X", "down", "down", "down"],
        ["X", "right", "up/down", "up"],
        ["left", "left", "up/down", "up"],
        ["left", "left", "left", "left"],
    ], (1, 1), 4302, {(2, 1), (3, 2), (1, 3)}),
    _window(),
    _grid("challenge_04", [
        ["left", "left", "left", "left", "left"],
        ["down", "left", "up/right", "down", "down"],
        ["down", "up", "left", "right", "X"],
        ["left", "left", "left", "right", "X"],
    ], (2, 1), 4304, {(0, 2), (2, 2), (3, 0), (4, 1)}),
]

_MECHANISMS = {
    "challenge_01": "Unequal target routes with shared upper-route prerequisites",
    "challenge_02": "Shared prerequisites and multi-level release dependencies",
    "challenge_03": "Boundary-contact aperture, rectangle unions and alternative shutter releases",
    "challenge_04": "Long turning chains and competing extraction routes",
}


def list_challenges():
    """Return all four frozen evaluation scenes, without sharing mutable data."""
    return deepcopy(_CHALLENGES)


def get_challenge(scene_id):
    for scene in _CHALLENGES:
        if scene["id"] == scene_id:
            return deepcopy(scene)
    raise KeyError("unknown challenge: " + str(scene_id))


def challenge_metadata(scene):
    """Report structural diagnostics only; these are never LLM input."""
    state = initial_state(scene)
    actions = candidate_actions(scene, state)
    checks = [check_action(scene, state, action) for action in actions]
    return {
        "scene_id": scene["id"],
        "design_mechanism": _MECHANISMS.get(scene["id"], "custom"),
        "part_count": len(scene["parts"]),
        "movable_part_count": sum(not part["fixed"] for part in scene["parts"]),
        "fixed_part_count": sum(part["fixed"] for part in scene["parts"]),
        "compound_part_count": sum(len(part["rects"]) > 1 for part in scene["parts"]),
        "rectangle_count": sum(len(part["rects"]) for part in scene["parts"]),
        "allowable_action_count": len(actions),
        "initial_feasible_action_count": sum(check["valid"] for check in checks),
        "initial_blocked_action_count": sum(not check["valid"] for check in checks),
    }

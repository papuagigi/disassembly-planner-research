"""Frozen, newly composed assemblies for executable-skill transfer.

These cases were authored without inspecting executable-skill candidates or
running an LLM. Author checks use geometry and an exact oracle only to establish
validity, budget feasibility, and structural distinction from every old case.
The mechanism family remains the same limited 2D translation world. This is a
new finite benchmark, not a claim of unseen physics or real-product transfer.
"""
from copy import deepcopy
import random

from .geometry import candidate_actions, check_action, initial_state
from .transfer_cases import dependency_fingerprint


def _p(name, rects, directions=(), fixed=False):
    return {"id": name, "label": name, "rects": rects,
            "allowed_directions": list(directions), "fixed": fixed,
            "color": "#687586" if fixed else "#66b9ae"}


def _scene(sid, parts, seed):
    # Peripheral pieces are genuine removable geometry in both conditions.
    # Their placement can still block a full extraction sweep across the world.
    pads = [
        _p("accessory_a", [[52, 3, 3, 1], [52, 4, 1, 1]], ["right"]),
        _p("accessory_b", [[52, 13, 1, 3], [53, 13, 2, 1]], ["right"]),
        _p("accessory_c", [[52, 32, 3, 1], [54, 33, 1, 1]], ["right"]),
        _p("accessory_d", [[51, 43, 2, 2]], ["right"]),
        _p("accessory_e", [[45, 48, 2, 1]], ["up"]),
        _p("accessory_f", [[35, 48, 2, 1]], ["up"]),
    ]
    for part in pads:
        if len(parts) >= 13:
            break
        parts.append(part)
    rng = random.Random(seed)
    names = [p["id"] for p in parts if p["id"] != "target"]
    ids = ["p%02d" % i for i in range(1, len(names) + 1)]
    rng.shuffle(ids)
    mapping = dict(zip(names, ids))
    for p in parts:
        p["id"] = mapping.get(p["id"], "target")
        p["label"] = "Target" if p["id"] == "target" else "Part " + p["id"]
        if p["id"] == "target":
            p["color"] = "#ec7272"
    rng.shuffle(parts)
    return {"id": sid, "name": sid.replace("_", " ").title(),
            "description": "A frozen synthetic assembly for executable-skill transfer.",
            "split": "development" if "_dev_" in sid else "evaluation",
            "workspace": [0, 0, 60, 52], "target_id": "target", "parts": parts}


def _dev_one():
    return _scene("code_dev_01", [
        _p("target", [[9, 8, 2, 2]], ["up", "right"]),
        _p("baffle", [[8, 16, 4, 1]], fixed=True),
        _p("gate_a", [[19, 7, 1, 4]], ["up"]),
        _p("gate_b", [[30, 7, 1, 4]], ["down"]),
        _p("cap", [[18, 24, 15, 1], [18, 25, 1, 1]], ["left"]),
        _p("pin", [[5, 23, 1, 4]], ["down"]),
        _p("lower", [[28, 3, 5, 1]], ["right"]),
        _p("post", [[45, 2, 1, 5]], ["up"]),
        _p("fixture", [[0, 40, 5, 1], [0, 41, 1, 3]], fixed=True),
    ], 8101)


def _dev_two():
    return _scene("code_dev_02", [
        _p("target", [[18, 4, 1, 2], [19, 4, 5, 1]], ["up"]),
        _p("gate_a", [[17, 12, 3, 1]], ["left"]),
        _p("gate_b", [[22, 15, 3, 1]], ["right"]),
        _p("left", [[7, 11, 1, 4]], ["up"]),
        _p("right", [[38, 14, 1, 4]], ["down", "up"]),
        _p("cap", [[6, 27, 35, 1], [6, 28, 1, 1]], ["right"]),
        _p("cap_pin", [[46, 26, 1, 4]], ["up"]),
        _p("floor", [[37, 2, 3, 1]], fixed=True),
        _p("fixture", [[0, 38, 1, 5], [1, 42, 4, 1]], fixed=True),
    ], 8102)


def _eval_one():
    return _scene("code_eval_01", [
        _p("target", [[21, 5, 2, 3]], ["up"]),
        _p("gate_a", [[19, 13, 6, 1]], ["left", "right"]),
        _p("gate_b", [[20, 23, 5, 1], [24, 24, 1, 1]], ["right"]),
        _p("left_pin", [[8, 12, 1, 4]], ["down"]),
        _p("left_base", [[7, 2, 3, 1]], ["left"]),
        _p("right_pin", [[36, 12, 1, 14]], ["up"]),
        _p("roof", [[35, 36, 5, 1], [39, 37, 1, 1]], ["left"]),
        _p("roof_key", [[12, 35, 1, 4]], ["up"]),
        _p("fixture", [[3, 20, 1, 5], [3, 25, 4, 1]], fixed=True),
    ], 8201)


def _eval_two():
    return _scene("code_eval_02", [
        _p("target", [[28, 19, 2, 2]], ["left", "down"]),
        _p("wall", [[21, 16, 1, 8]], fixed=True),
        _p("gate", [[26, 12, 7, 1]], ["left", "right"]),
        _p("left_fixed", [[14, 10, 1, 5]], fixed=True),
        _p("key_a", [[38, 11, 1, 4]], ["up"]),
        _p("key_b", [[44, 10, 1, 6]], ["down"]),
        _p("cap_a", [[37, 29, 3, 1], [37, 30, 1, 1]], ["right"]),
        _p("cap_key", [[48, 28, 1, 4]], ["up"]),
        _p("base_b", [[43, 2, 4, 1], [46, 3, 1, 1]], ["left"]),
    ], 8202)


def _eval_three():
    return _scene("code_eval_03", [
        _p("target", [[4, 16, 2, 1], [4, 17, 1, 6]], ["right"]),
        _p("window", [[17, 0, 1, 16], [17, 23, 1, 22]], fixed=True),
        _p("gate_low", [[26, 15, 1, 3]], ["down"]),
        _p("gate_high", [[26, 21, 1, 4]], ["up"]),
        _p("gate_far", [[37, 15, 1, 10]], ["up"]),
        _p("low_stop", [[25, 5, 3, 1]], ["right"]),
        _p("bottom_pin", [[43, 4, 1, 3]], ["down"]),
        _p("top_bridge", [[25, 33, 15, 1], [39, 34, 1, 1]], ["right"]),
        _p("bridge_key", [[46, 32, 1, 3]], ["up"]),
    ], 8203)


def _eval_four():
    return _scene("code_eval_04", [
        _p("target", [[16, 15, 6, 1], [16, 16, 1, 5]], ["down", "right", "up"]),
        _p("peg", [[19, 18, 1, 1]], fixed=True),
        _p("top_fixed", [[15, 26, 9, 1]], fixed=True),
        _p("lower", [[18, 9, 3, 1]], ["left", "right"]),
        _p("left_pin", [[8, 8, 1, 5]], ["up"]),
        _p("left_cap", [[7, 30, 3, 1], [7, 31, 1, 2]], ["right"]),
        _p("cap_pin", [[34, 29, 1, 5]], ["up"]),
        _p("right_pin", [[30, 8, 1, 5]], ["down"]),
        _p("base", [[29, 3, 3, 1]], ["left"]),
        _p("base_pin", [[13, 2, 1, 3]], ["down"]),
    ], 8204)


def _eval_five():
    return _scene("code_eval_05", [
        _p("target", [[22, 20, 2, 2]], ["up", "down"]),
        _p("upper", [[21, 28, 5, 1], [21, 29, 1, 1]], ["left"]),
        _p("lower", [[20, 13, 6, 1]], ["left"]),
        _p("shared_pin", [[9, 11, 1, 21]], ["up", "down"]),
        _p("top_cap", [[8, 39, 4, 1]], ["right"]),
        _p("cap_pin", [[37, 38, 1, 5]], ["down"]),
        _p("middle", [[36, 24, 3, 1], [38, 25, 1, 1]], ["right"]),
        _p("lower_cap", [[8, 4, 4, 1]], ["left"]),
        _p("left_fixed", [[2, 2, 1, 5]], fixed=True),
        _p("extra_fixed", [[43, 17, 3, 1], [45, 18, 1, 3]], fixed=True),
    ], 8205)


def _eval_six():
    return _scene("code_eval_06", [
        _p("target", [[8, 14, 2, 2]], ["right", "up"]),
        _p("side_a", [[18, 13, 1, 4]], ["down"]),
        _p("side_b", [[32, 13, 1, 4]], ["up", "down"]),
        _p("top_a", [[7, 25, 4, 1]], ["right"]),
        _p("side_cap", [[31, 24, 5, 1], [35, 25, 1, 1]], ["up"]),
        _p("cap_stop", [[30, 37, 7, 1]], ["left"]),
        _p("stop_key", [[4, 36, 1, 4]], ["up"]),
        _p("side_base", [[16, 4, 19, 1], [16, 5, 1, 1]], ["left"]),
        _p("base_key", [[3, 3, 1, 4]], ["down"]),
        _p("fixed", [[42, 19, 1, 5], [43, 23, 3, 1]], fixed=True),
    ], 8206)


_DEVELOPMENT = [_dev_one(), _dev_two()]
_EVALUATION = [_eval_one(), _eval_two(), _eval_three(), _eval_four(), _eval_five(), _eval_six()]


def development_validation_cases():
    return deepcopy(_DEVELOPMENT)


def heldout_evaluation_cases():
    return deepcopy(_EVALUATION)


def metadata(scene):
    state = initial_state(scene)
    actions = candidate_actions(scene, state)
    checks = [check_action(scene, state, action) for action in actions]
    return {"scene_id": scene["id"], "split": scene["split"],
            "construction": "new manually composed layout; no transform or identifier substitution of an old assembly",
            "author_model_access": False,
            "part_count": len(scene["parts"]),
            "movable_part_count": sum(not p["fixed"] for p in scene["parts"]),
            "fixed_part_count": sum(p["fixed"] for p in scene["parts"]),
            "compound_part_count": sum(len(p["rects"]) > 1 for p in scene["parts"]),
            "rectangle_count": sum(len(p["rects"]) for p in scene["parts"]),
            "allowable_action_count": len(actions),
            "initial_feasible_action_count": sum(c["valid"] for c in checks),
            "initial_blocked_action_count": sum(not c["valid"] for c in checks),
            **dependency_fingerprint(scene)}

"""Fresh, deterministic cases for failure-derived procedural-skill transfer.

All layouts are manually composed before any new model execution. The two
development-validation layouts and six evaluation layouts are separate designs,
not ID permutations or affine transforms of previous cases. Their mechanism
families intentionally overlap: this tests transfer within the same limited 2D
world, not transfer to unseen physics. Administrative provenance and structural
diagnostics are never supplied through geometry.observation().
"""

from copy import deepcopy
import hashlib
import json
import random

from .geometry import candidate_actions, check_action, initial_state


def _p(name, rects, directions=(), fixed=False):
    return {"id": name, "label": name, "rects": rects,
            "allowed_directions": list(directions), "fixed": fixed,
            "color": "#687586" if fixed else "#66b9ae"}


def _scene(sid, split, parts, bounds, seed):
    rng = random.Random(seed)
    names = [p["id"] for p in parts if p["id"] != "target"]
    opaque = ["p%02d" % i for i in range(1, len(names) + 1)]
    rng.shuffle(opaque)
    mapping = dict(zip(names, opaque))
    for part in parts:
        part["id"] = mapping.get(part["id"], "target")
        part["label"] = "Target" if part["id"] == "target" else "Part " + part["id"]
        if part["id"] == "target":
            part["color"] = "#ec7272"
    rng.shuffle(parts)
    return {"id": sid, "name": sid.replace("_", " ").title(),
            "description": "A preregistered synthetic transfer assembly.",
            "split": split, "workspace": bounds, "target_id": "target", "parts": parts}


def _development_one():
    return _scene("transfer_dev_01", "development", [
        _p("target", [[8, 8, 2, 2]], ["right", "up"]),
        _p("right_gate", [[15, 7, 2, 5]], ["up"]),
        _p("cap", [[14, 18, 6, 1], [19, 19, 1, 1]], ["left"]),
        _p("key", [[5, 17, 1, 3]], ["up"]),
        _p("release", [[4, 25, 3, 1]], ["right"]),
        _p("upper", [[7, 14, 4, 1], [7, 15, 1, 1]], ["left"]),
        _p("left_bar", [[3, 12, 1, 5]], ["down"]),
        _p("lower", [[2, 3, 3, 1]], ["right"]),
        _p("bottom_gate", [[12, 2, 1, 3]], ["down"]),
        _p("extra_a", [[27, 2, 2, 1], [28, 3, 1, 1]], ["right"]),
        _p("extra_b", [[26, 11, 2, 2]], ["up", "right"]),
        _p("extra_c", [[24, 29, 3, 1]], ["left"]),
        _p("fixture", [[0, 0, 1, 8], [0, 0, 8, 1]], fixed=True),
    ], [0, 0, 32, 32], 7101)


def _development_two():
    return _scene("transfer_dev_02", "development", [
        _p("target", [[22, 12, 3, 2]], ["left"]),
        _p("window_a", [[16, 0, 1, 12], [16, 14, 1, 16]], fixed=True),
        _p("window_b", [[6, 0, 1, 12], [6, 14, 1, 16]], fixed=True),
        _p("shutter_a", [[11, 10, 1, 6]], ["up", "down"]),
        _p("shutter_b", [[3, 11, 1, 5]], ["up"]),
        _p("lower", [[10, 5, 3, 1]], ["down"]),
        _p("bottom", [[9, 1, 5, 1]], ["down"]),
        _p("upper", [[10, 21, 3, 1], [12, 22, 1, 1]], ["up"]),
        _p("top", [[9, 27, 5, 1]], ["up"]),
        _p("left_upper", [[2, 21, 3, 1]], ["left"]),
        _p("extra_a", [[24, 3, 3, 1], [26, 4, 1, 1]], ["right"]),
        _p("extra_b", [[25, 21, 2, 2]], ["up"]),
        _p("extra_c", [[20, 27, 2, 1]], ["right"]),
    ], [0, 0, 32, 32], 7102)


def _evaluation_one():
    return _scene("transfer_eval_01", "evaluation", [
        _p("target", [[9, 6, 6, 1], [9, 7, 1, 1]], ["up"]),
        _p("gate_a", [[9, 13, 1, 2]], ["left"]),
        _p("gate_b", [[14, 11, 1, 5]], ["right"]),
        _p("key_a", [[3, 12, 1, 4]], ["up"]),
        _p("key_b", [[24, 10, 1, 7]], ["up"]),
        _p("cap", [[2, 22, 26, 1], [27, 23, 1, 1]], ["left"]),
        _p("post", [[0.5, 21, 1, 4]], ["down"]),
        _p("bottom", [[0.5, 1, 1, 2]], ["right"]),
        _p("extra_a", [[31, 5, 2, 1], [32, 6, 1, 1]], ["right"]),
        _p("extra_b", [[6, 29, 2, 1]], ["up"]),
        _p("extra_c", [[20, 30, 2, 2]], ["right"]),
        _p("fixture", [[34, 17, 1, 3]], fixed=True),
    ], [0, 0, 36, 34], 7201)


def _evaluation_two():
    return _scene("transfer_eval_02", "evaluation", [
        _p("target", [[8, 10, 2, 4]], ["right", "up"]),
        _p("baffle", [[4, 18, 10, 1]], fixed=True),
        _p("window", [[18, 1, 1, 9], [18, 14, 1, 16]], fixed=True),
        _p("shutter", [[23, 8, 1, 8]], ["up", "down"]),
        _p("upper", [[22, 22, 5, 1], [22, 23, 1, 3]], ["right"]),
        _p("stopper", [[31, 21, 1, 5]], ["down"]),
        _p("low", [[31, 2, 1, 3], [30, 2, 1, 1]], ["down"]),
        _p("lower", [[22, 3, 4, 1]], ["left", "right"]),
        _p("extra_a", [[3, 3, 3, 1], [3, 4, 1, 2]], ["left"]),
        _p("extra_b", [[9, 25, 2, 2]], ["up"]),
        _p("extra_c", [[24, 30, 3, 1]], ["right"]),
        _p("extra_d", [[2, 12, 2, 1]], ["down", "left"]),
    ], [0, 0, 36, 34], 7202)


def _evaluation_three():
    return _scene("transfer_eval_03", "evaluation", [
        _p("target", [[4, 8, 2, 2]], ["right"]),
        _p("gate_a", [[12, 7, 1, 5]], ["up"]),
        _p("gate_b", [[23, 6, 1, 6]], ["down"]),
        _p("cap", [[11, 20, 4, 1], [11, 21, 1, 1]], ["right"]),
        _p("pin", [[29, 18, 1, 6]], ["up"]),
        _p("roof", [[28, 29, 4, 1], [31, 30, 1, 1]], ["left"]),
        _p("roof_key", [[2, 28, 1, 3]], ["down"]),
        _p("lower", [[22, 2, 4, 1]], ["left"]),
        _p("bottom_key", [[9, 1, 1, 4]], ["down"]),
        _p("fixture_a", [[0, 0, 1, 1]], fixed=True),
        _p("fixture_b", [[34, 14, 1, 5]], fixed=True),
        _p("extra_a", [[6, 15, 2, 1], [7, 16, 1, 2]], ["up"]),
        _p("extra_b", [[17, 27, 2, 1]], ["up"]),
        _p("extra_c", [[31, 4, 2, 2]], ["right"]),
    ], [0, 0, 36, 34], 7203)


def _evaluation_four():
    return _scene("transfer_eval_04", "evaluation", [
        _p("target", [[8, 7, 5, 1], [8, 8, 1, 5]], ["down", "right"]),
        _p("peg", [[11, 10, 1, 2]], fixed=True),
        _p("blocker", [[9, 4, 3, 1]], ["left"]),
        _p("left_key", [[2, 3, 1, 4]], ["up"]),
        _p("cap", [[1, 19, 5, 1], [1, 20, 1, 1]], ["right"]),
        _p("right_key", [[20, 18, 1, 4]], ["down"]),
        _p("stop", [[19, 2, 3, 1]], ["left"]),
        _p("bottom", [[8, 1, 1, 1]], ["right"]),
        _p("fixture", [[27, 11, 1, 5]], fixed=True),
        _p("extra_a", [[14, 25, 2, 1], [15, 26, 1, 1]], ["up"]),
        _p("extra_b", [[3, 27, 2, 2]], ["left"]),
        _p("extra_c", [[25, 4, 2, 2]], ["right"]),
    ], [0, 0, 30, 32], 7204)


def _evaluation_five():
    return _scene("transfer_eval_05", "evaluation", [
        _p("target", [[20, 10, 2, 2]], ["left", "up"]),
        _p("left_gate", [[13, 9, 1, 5]], ["up"]),
        _p("left_extra", [[8, 10, 1, 1]], ["down"]),
        _p("bridge", [[12, 23, 12, 1], [12, 24, 1, 1]], ["left"]),
        _p("pin", [[5, 22, 1, 3]], ["down"]),
        _p("rail", [[4, 5, 3, 1], [4, 6, 1, 1]], ["right"]),
        _p("stop", [[27, 4, 1, 3]], ["up"]),
        _p("middle", [[19, 17, 3, 1], [19, 18, 1, 1]], ["right"]),
        _p("post", [[30, 14, 1, 5]], ["down"]),
        _p("bottom_stop", [[29, 1, 3, 1]], ["left"]),
        _p("fixture_a", [[0, 13, 1, 4]], fixed=True),
        _p("fixture_b", [[34, 22, 1, 5]], fixed=True),
        _p("extra_a", [[2, 29, 3, 1]], ["left"]),
        _p("extra_b", [[23, 29, 2, 1]], ["up"]),
    ], [0, 0, 36, 34], 7205)


def _evaluation_six():
    return _scene("transfer_eval_06", "evaluation", [
        _p("target", [[16, 3, 2, 2]], ["up"]),
        _p("window_a", [[0, 10, 16, 1], [18, 10, 18, 1]], fixed=True),
        _p("window_b", [[0, 22, 16, 1], [18, 22, 18, 1]], fixed=True),
        _p("shutter_a", [[14, 14, 6, 1]], ["right", "left"]),
        _p("trapped_post", [[26, 13, 1, 3]], ["up"]),
        _p("left_pin", [[7, 13, 1, 3], [8, 13, 1, 1]], ["left"]),
        _p("left_key", [[2, 13, 1, 3]], ["left"]),
        _p("shutter_b", [[14, 27, 6, 1]], ["left"]),
        _p("upper_pin", [[8, 26, 1, 3]], ["up"]),
        _p("cap", [[7, 33, 3, 1], [7, 34, 1, 1]], ["right"]),
        _p("upper_stop", [[29, 32, 1, 3]], ["right"]),
        _p("extra_a", [[3, 3, 2, 2]], ["down"]),
        _p("extra_b", [[25, 5, 3, 1]], ["right"]),
        _p("extra_c", [[33, 27, 2, 1]], ["up"]),
    ], [0, 0, 36, 38], 7206)


_DEVELOPMENT = [_development_one(), _development_two()]
_EVALUATION = [_evaluation_one(), _evaluation_two(), _evaluation_three(),
               _evaluation_four(), _evaluation_five(), _evaluation_six()]

_PROVENANCE = {
    "transfer_dev_01": {"source_parents": ["challenge_01", "challenge_04"],
                        "design_change": "Irregular competing turning chains with distinct release branches"},
    "transfer_dev_02": {"source_parents": ["challenge_03"],
                        "design_change": "Two serial apertures and two independently released shutters"},
    "transfer_eval_01": {"source_parents": ["challenge_02"],
                         "design_change": "Wide target, two parallel gates and a shared cap-release chain"},
    "transfer_eval_02": {"source_parents": ["challenge_03", "challenge_01"],
                         "design_change": "Permanent target-route baffle and unequal shutter-release dependencies"},
    "transfer_eval_03": {"source_parents": ["challenge_02", "challenge_04"],
                         "design_change": "Serial gates with separate unequal turning dependency chains"},
    "transfer_eval_04": {"source_parents": ["challenge_03", "challenge_04"],
                         "design_change": "Connected target notch, fixed interior peg, and opposite-direction release chain"},
    "transfer_eval_05": {"source_parents": ["challenge_01", "challenge_02"],
                         "design_change": "Two target routes share a bridge while retaining different side dependencies"},
    "transfer_eval_06": {"source_parents": ["challenge_03", "challenge_02"],
                         "design_change": "Stacked apertures with serial shutters and a permanently trapped movable decoy"},
}


def development_validation_cases():
    return deepcopy(_DEVELOPMENT)


def heldout_evaluation_cases():
    return deepcopy(_EVALUATION)


def dependency_fingerprint(scene):
    """ID-free graph refinement signature for novelty checks, not an oracle.

The target dependency closure includes all blockers of all permitted actions,
recursively. Disconnected decorative parts do not affect this signature. A
different signature certifies a different labelled dependency graph; equal
signatures do not certify graph isomorphism. Direction labels are omitted so
rotated direction names alone cannot make a layout appear structurally new.
"""
    state = initial_state(scene)
    parts = {p["id"]: p for p in scene["parts"]}
    blockers = {pid: [] for pid in parts}
    for action in candidate_actions(scene, state):
        blockers[action["part_id"]].append(tuple(check_action(scene, state, action)["blockers"]))
    closure, pending = set(), [scene["target_id"]]
    while pending:
        pid = pending.pop()
        if pid in closure:
            continue
        closure.add(pid)
        for group in blockers[pid]:
            pending.extend(group)
    labels = {pid: ("target" if pid == scene["target_id"] else
                    "fixed" if parts[pid]["fixed"] else "movable") for pid in closure}
    for _ in range(len(closure)):
        labels = {pid: hashlib.sha256(json.dumps([
            labels[pid], sorted([sorted(labels[b] for b in group) for group in blockers[pid]])
        ], sort_keys=True).encode()).hexdigest() for pid in closure}
    signature = hashlib.sha256(json.dumps(sorted(labels.values())).encode()).hexdigest()
    return {"target_dependency_part_count": len(closure), "dependency_signature": signature}


def metadata(scene):
    state = initial_state(scene)
    actions = candidate_actions(scene, state)
    checks = [check_action(scene, state, a) for a in actions]
    return {
        "scene_id": scene["id"], "split": scene["split"],
        "provenance": deepcopy(_PROVENANCE.get(scene["id"], {})),
        "construction": "new manually composed geometry; no affine transform of a source scene",
        "part_count": len(scene["parts"]),
        "movable_part_count": sum(not p["fixed"] for p in scene["parts"]),
        "fixed_part_count": sum(p["fixed"] for p in scene["parts"]),
        "compound_part_count": sum(len(p["rects"]) > 1 for p in scene["parts"]),
        "rectangle_count": sum(len(p["rects"]) for p in scene["parts"]),
        "allowable_action_count": len(actions),
        "initial_feasible_action_count": sum(c["valid"] for c in checks),
        "initial_blocked_action_count": sum(not c["valid"] for c in checks),
        **dependency_fingerprint(scene),
    }

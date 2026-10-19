"""Eight hand-designed synthetic 2D scenarios; no real product/CAD claim.

The development/evaluation split is fixed. Evaluation structures differ in
branching, exits and rectangle-union geometry; they are not statistical
evidence of generalization to real products. Descriptions contain no answers.
"""

from copy import deepcopy


def _part(pid, label, rects, directions, fixed=False, color="#66b9ae"):
    return {"id": pid, "label": label, "rects": rects,
            "allowed_directions": directions, "fixed": fixed, "color": color}


def _scene(sid, name, description, parts, split="development"):
    return {"id": sid, "name": name, "description": description, "split": split,
            "workspace": [0, 0, 12, 12], "target_id": "target", "parts": parts}


_SCENES = [
    _scene("housing_demo", "Housing module", "A target module, housing components and external accessories.", [
        _part("housing", "Housing", [[2, 2, 1, 7], [9, 2, 1, 7], [2, 1, 8, 1]], [], True, "#687586"),
        _part("cover", "Cover", [[2, 9, 8, 1]], ["up"], color="#eeab63"),
        _part("retainer", "Retainer", [[4, 7, 4, 1]], ["up"], color="#b69bdf"),
        _part("target", "Target module", [[5, 3, 2, 3]], ["up"], color="#ec7272"),
        _part("spacer", "Spacer", [[3.25, 3, 1, 2]], ["up"]),
        _part("tab", "Accessory tab", [[0.25, 5, 1, 1]], ["left"]),
        _part("badge", "Badge", [[10.5, 3, 1, 1]], ["down"]),
    ]),
    _scene("side_drawer", "Side-access cartridge", "A cartridge within a three-sided housing with several accessories.", [
        _part("housing", "Housing", [[2, 2, 8, 1], [2, 9, 8, 1], [2, 3, 1, 6]], [], True, "#687586"),
        _part("target", "Target cartridge", [[4, 5, 3, 2]], ["right"], color="#ec7272"),
        _part("gate", "End plate", [[9, 3, 1, 6]], ["right"], color="#b69bdf"),
        _part("strip", "External strip", [[10, 3, 1, 6]], ["up"], color="#eeab63"),
        _part("handle", "Handle", [[4, 3.5, 1, 1]], ["right"]),
        _part("tag", "Label plate", [[0.5, 10.5, 1, 0.5]], ["left"]),
        _part("sensor", "Sensor", [[7.5, 7.5, 0.75, 0.75]], ["right"]),
    ]),
    _scene("sandwich_escape", "Opposed shields", "A module between upper and lower supports and lateral components.", [
        _part("fixture", "Support fixture", [[1, 1, 10, 1], [2, 9, 8, 1]], [], True, "#687586"),
        _part("target", "Target module", [[5, 4, 2, 2]], ["left", "right"], color="#ec7272"),
        _part("left_shield", "Left shield", [[3, 3, 1, 4]], ["up", "down"], color="#b69bdf"),
        _part("right_shield", "Right shield", [[8, 3, 1, 5]], ["right"], color="#eeab63"),
        _part("bridge", "Crosspiece", [[2, 7, 6, 1]], ["left"]),
        _part("key", "Accessory key", [[10, 10.5, 1, 1]], ["up"]),
        _part("washer", "Loose spacer", [[0.25, 3, 1, 1]], ["left"]),
    ]),
    _scene("offset_corridor", "Offset module", "An asymmetric module with offset surrounding components.", [
        _part("bracket", "Bracket", [[2, 2, 1, 7], [2, 2, 4, 1]], [], True, "#687586"),
        _part("target", "Target module", [[4, 4, 2, 1], [4, 5, 1, 2]], ["right"], color="#ec7272"),
        _part("upper_block", "Upper block", [[6, 6, 2, 1]], ["up"], color="#b69bdf"),
        _part("lower_block", "Lower block", [[7, 3, 1, 2]], ["down"], color="#eeab63"),
        _part("lid", "Top plate", [[5, 9, 4, 1]], ["up"]),
        _part("plug", "Accessory plug", [[9.5, 2, 1, 1]], ["down"]),
        _part("tab", "Side tab", [[0.5, 8, 1, 1]], ["left"]),
    ]),
    _scene("nested_gate", "Branching enclosure", "An asymmetric target and multiple peripheral components in a fixture.", [
        _part("fixture", "Fixture", [[2, 1, 8, 1], [2, 2, 1, 7]], [], True, "#687586"),
        _part("target", "Target module", [[4, 4, 1, 4], [5, 4, 2, 1]], ["right"], color="#ec7272"),
        _part("upper_gate", "Upper plate", [[7, 6, 1, 3]], ["up"], color="#b69bdf"),
        _part("roof", "Top panel", [[6, 10, 3, 1]], ["left"], color="#eeab63"),
        _part("lower_gate", "Lower plate", [[8, 3, 1, 3]], ["right"]),
        _part("outer_guard", "External guard", [[10, 3, 1, 7]], ["up"], color="#7b9ed4"),
        _part("spacer", "Upper spacer", [[4, 8, 1, 1]], ["up"]),
        _part("tab", "Side tab", [[0, 3, 1, 1]], ["down"]),
    ], "evaluation"),
    _scene("split_route", "Multiple access routes", "A target with two permitted extraction directions and a surrounding fixture.", [
        _part("fixture", "Fixture", [[3, 2, 7, 1], [10, 8, 1, 3]], [], True, "#687586"),
        _part("target", "Target module", [[5, 4, 2, 2]], ["up", "left"], color="#ec7272"),
        _part("bridge", "Crosspiece", [[4, 7, 4, 1]], ["up"], color="#b69bdf"),
        _part("lid", "Top panel", [[3, 9, 6, 1]], ["left", "right"], color="#eeab63"),
        _part("side_plug", "Side plug", [[3, 4, 1, 2]], ["left"]),
        _part("side_stop", "Side plate", [[1, 3, 1, 5]], ["up"], color="#7b9ed4"),
        _part("shelf", "Peripheral shelf", [[0, 9, 2, 1]], ["up"]),
        _part("accessory", "Accessory", [[8.5, 4, 0.5, 1]], ["down", "right"]),
    ], "evaluation"),
    _scene("key_bridge", "Stepped cover", "A target beneath a stepped component within a constrained housing.", [
        _part("housing", "Housing", [[1, 2, 1, 7], [1, 1, 10, 1]], [], True, "#687586"),
        _part("target", "Target module", [[5, 4, 2, 2]], ["up"], color="#ec7272"),
        _part("gate", "Stepped component", [[4, 7, 4, 1], [4, 5, 1, 2]], ["left", "up"], color="#b69bdf"),
        _part("cap", "Upper panel", [[3, 10, 6, 1]], ["right"], color="#eeab63"),
        _part("stopper", "Outer component", [[10, 9, 1, 2]], ["up"]),
        _part("spacer", "Side spacer", [[8, 4, 1, 2]], ["right"]),
        _part("tag", "Accessory tag", [[0, 10, 1, 1]], ["left"]),
    ], "evaluation"),
    _scene("concave_window", "Segmented window", "A narrow target, a segmented fixture and surrounding panels.", [
        _part("frame", "Frame", [[2, 2, 1, 6], [2, 2, 7, 1], [2, 8, 7, 1]], [], True, "#687586"),
        _part("window", "Segmented fixture", [[8, 3, 1, 2], [8, 6, 1, 2]], [], True, "#687586"),
        _part("target", "Target module", [[5, 5, 2, 1]], ["right"], color="#ec7272"),
        _part("shutter", "Side panel", [[9, 4, 1, 3]], ["up"], color="#b69bdf"),
        _part("knob", "Upper component", [[9, 9, 1, 1]], ["right"], color="#eeab63"),
        _part("spacer", "Internal spacer", [[3.5, 4, 1, 1]], ["down"]),
        _part("tag", "Accessory tag", [[0, 4, 1, 1]], ["up"]),
    ], "evaluation"),
]


def list_scenes():
    """Return independent copies so callers cannot alter the scene registry."""
    return deepcopy(_SCENES)


def get_scene(scene_id):
    for scene in _SCENES:
        if scene["id"] == scene_id:
            return deepcopy(scene)
    raise KeyError("unknown scene: " + str(scene_id))

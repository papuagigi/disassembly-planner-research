"""State-conditional directed blocking evidence, without oracle precedences.

An edge ``blocker -> blocked part`` is evidence for one extraction direction
in one exact physical state.  It is never a global assembly precedence.
"""
from __future__ import annotations

import copy
import hashlib
import json

DIRECTIONS = ("+x", "-x", "+y", "-y", "+z", "-z")


def physical_state_key(state):
    """Hash full surviving poses, including velocities, without rounding.

    Checks, trace, path actions and insertion order do not describe physics.
    Removed-part poses also cannot affect a future simulator build.
    """
    remaining = sorted(state["remaining"])
    physical = {"remaining": remaining,
                "poses": {pid: state["poses"][pid] for pid in remaining}}
    encoded = json.dumps(physical, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def action_key(action):
    return action["part_id"], action["direction"]


def canonical_candidates(observation):
    """Unknown actions stay candidates; a missing edge is not proof of safety."""
    return [{"part_id": part["id"], "direction": direction}
            for part in sorted(observation["remaining_parts"], key=lambda p: p["id"])
            if not part.get("fixed", False)
            for direction in DIRECTIONS
            if direction in part.get("allowed_directions", DIRECTIONS)]


class ConditionalBlockingGraph:
    def __init__(self):
        self._evidence = {}
        # Incoming adjacency is indexed by (moving part, extraction direction)
        # inside an exact physical state: blocker -> moving part. It is the
        # active hard filter for observed collision edges, not merely a diagram.
        self._incoming = {}
        # Other rejections (e.g. unstable remainder) are independent of the
        # blocking graph and use a separate same-state failure cache.
        self._rejected = {}

    def add(self, state_key, result):
        evidence = copy.deepcopy(result)
        evidence["state_key"] = state_key
        self._evidence.setdefault(state_key, []).append(evidence)
        # Invalid arguments are not physical proof, but the identical malformed
        # action need not be generated again. Canonical candidates exclude them.
        if not result.get("valid", False):
            blockers = result.get("blockers") or []
            if result.get("reason") == "path_collision" and blockers:
                incoming = self._incoming.setdefault(state_key, {})
                incoming.setdefault(action_key(result), set()).update(blockers)
            else:
                self._rejected.setdefault(state_key, set()).add(action_key(result))

    def evidence(self, state_key):
        return copy.deepcopy(self._evidence.get(state_key, []))

    def rejected(self, state_key):
        return (set(self._rejected.get(state_key, set()))
                | set(self._incoming.get(state_key, {})))

    def incoming_blockers(self, state_key, part_id, direction):
        """Read graph predecessors for this exact state and direction only."""
        return set(self._incoming.get(state_key, {}).get((part_id, direction), set()))

    def filter(self, state_key, candidates):
        incoming = self._incoming.get(state_key, {})
        cached_rejections = self._rejected.get(state_key, set())
        return [copy.deepcopy(action) for action in candidates
                if not incoming.get(action_key(action))
                and action_key(action) not in cached_rejections]

    def describe(self, state_key):
        edges = []
        for (part_id, direction), blockers in self._incoming.get(state_key, {}).items():
            for blocker in sorted(blockers):
                edge = {"from": blocker, "to": part_id,
                        "direction": direction, "state_key": state_key,
                        "semantics": "blocks this sampled straight extraction in this state"}
                if edge not in edges:
                    edges.append(edge)
        return {"state_key": state_key, "edges": edges,
                "rejected_actions": [dict(part_id=p, direction=d)
                                     for p, d in sorted(self.rejected(state_key))],
                "filter_rule": "Exclude a candidate when it has an incoming blocking edge for this exact state and direction. "
                               "Separately exclude cached same-state stability/other rejections.",
                "non_graph_cached_rejections": [dict(part_id=p, direction=d)
                                                for p, d in sorted(self._rejected.get(state_key, set()))],
                "scope": "Exact-state, direction-conditional evidence; not a global precedence DAG. "
                         "Only tested rejected actions are filtered; untested actions remain uncertain."}

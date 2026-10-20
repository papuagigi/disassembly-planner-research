"""DIAGNOSTIC-ONLY collision-rule variants. Never used by evaluated planners.

P1_persisting_interference: in the evaluated rule a material sample whose
operation-initial depth exceeds penetration_tolerance (0.2 mm) is permitted
only tolerance, so any pre-existing CAD interference above 0.2 mm rejects the
very first path sample (a direction-independent lock). P1 instead permits each
sample its own initial depth + resting slack (the rule the evaluated checker
already uses for initial depths <= tolerance). Penetration may persist but may
not grow by more than 0.02 mm. Containment, unresolved-intersection, floor and
MuJoCo stability rules are unchanged. Purpose: test whether the initial-
interference rule is the binding constraint on full disassembly.

P2_persist_up_to_stable_penetration (candidate evaluation physics, see
analysis/PHYSICS_DECISION.md): like P1, but only for operation-initial depths
<= stable_penetration_m (1 mm, the model's own threshold already used by the
initial screen, the MuJoCo-convex path checker and the stability criterion).
Deeper initial samples keep the evaluated cap (tolerance), exactly mirroring
disassembly_mujoco.simulator: `if initial_depth > stable_penetration_m:
permitted = penetration_tolerance_m`.
"""
from __future__ import annotations

import numpy as np

VARIANTS = ('P1_persisting_interference', 'P2_persist_up_to_stable_penetration')
DESCRIPTIONS = {
    'P1_persisting_interference': 'DIAGNOSTIC P1: any initial interference may persist, growth <= resting_contact_slack_m',
    'P2_persist_up_to_stable_penetration': 'P2: initial interference <= stable_penetration_m may persist with growth <= resting_contact_slack_m; deeper initial interference capped at penetration_tolerance_m',
}


def apply(variant):
    if variant is None:
        return
    assert variant in VARIANTS, variant
    from disassembly_real_v3 import source_collision as sc

    def _material_check(self, owner, outside, triangle_ids):
        ids, blocks = self._triangle_samples(owner, triangle_ids)
        sizes = [len(block) for block in blocks]
        if not sum(sizes):
            return [], False
        points = np.concatenate(blocks)
        values = sc.signed_material_distance(self.meshes[outside], self._other_local(points, owner, outside, self.poses))
        keys = [(owner, outside, tid) for tid in ids]
        missing = [i for i, key in enumerate(keys) if key not in self.initial_depth_samples]
        if missing:
            new_points = np.concatenate([blocks[i] for i in missing])
            depths = sc.signed_material_distance(self.meshes[outside], self._other_local(new_points, owner, outside, self.initial_poses))
            cursor = 0
            for i in missing:
                n = sizes[i]
                self.initial_depth_samples[keys[i]] = depths[cursor:cursor + n].copy()
                cursor += n
        initial = np.concatenate([self.initial_depth_samples[key] for key in keys])
        # P1: no reset to tolerance for deep initial samples. P2: reset only above stable_penetration_m.
        permitted = np.maximum(self.physics['penetration_tolerance_m'], np.maximum(initial, 0.) + self.physics['resting_contact_slack_m'])
        if variant == 'P2_persist_up_to_stable_penetration':
            permitted[initial > self.physics['stable_penetration_m'] + sc.SURFACE_EPSILON_M] = self.physics['penetration_tolerance_m']
        bad = np.flatnonzero(values > permitted + sc.SURFACE_EPSILON_M)
        failures = []
        if len(bad):
            index = int(bad[np.argmax(values[bad] - permitted[bad])])
            failures.append(dict(kind='source_material_sample', sample_owner=owner, other_part=outside,
                                 signed_depth_m=float(values[index]), initial_signed_depth_m=float(initial[index]),
                                 permitted_depth_m=float(permitted[index]), owner_local_point_m=points[index].tolist(),
                                 diagnostic_variant=variant))
        return failures, bool(np.any(values > sc.SURFACE_EPSILON_M))

    sc.SourceMeshCollisionChecker._material_check = _material_check

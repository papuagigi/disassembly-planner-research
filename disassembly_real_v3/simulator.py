"""Full-disassembly physics adapter with explicit extraction coordinate frames.

The six public action labels are unchanged. ``straight_world_axes`` reproduces
the old kinematic checker. ``straight_source_axes`` maps each labelled source
axis through the case's whole-assembly setup rotation. Neither mode generates
rotating or force-driven trajectories. Residual gravity/friction, state export,
checkpoint restoration and full n-1 task semantics remain inherited.
"""
from __future__ import annotations

import copy
import math
import time

import mujoco
import numpy as np

from disassembly_mujoco.simulator import DIRECTIONS
from disassembly_real_v2.simulator import FullDisassemblySim as PreviousFullDisassemblySim


PATH_MODES = ('straight_world_axes', 'straight_source_axes')
COLLISION_MODES = ('mujoco_convex', 'source_mesh_bvh')


class FullDisassemblySim(PreviousFullDisassemblySim):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path_mode = self.physics.get('path_mode', 'straight_world_axes')
        if self.path_mode not in PATH_MODES:
            raise ValueError('Unsupported path_mode: ' + str(self.path_mode))
        self.physics['path_mode'] = self.path_mode
        self.extraction_collision = self.physics.get('extraction_collision', 'mujoco_convex')
        if self.extraction_collision not in COLLISION_MODES:
            raise ValueError('Unsupported extraction_collision: ' + str(self.extraction_collision))
        self.physics['extraction_collision'] = self.extraction_collision
        self._source_collision = None
        transform = np.asarray(self.case.get('whole_assembly_rigid_transform', np.eye(4)), dtype=float)
        if (transform.shape != (4, 4) or not np.isfinite(transform).all()
                or not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-10, rtol=0)):
            raise ValueError('whole_assembly_rigid_transform must be a finite rigid 4x4 matrix')
        self.setup_rotation = transform[:3, :3].copy()
        if (not np.allclose(self.setup_rotation.T @ self.setup_rotation, np.eye(3), atol=1e-8, rtol=0)
                or not np.isclose(np.linalg.det(self.setup_rotation), 1.0, atol=1e-8, rtol=0)):
            raise ValueError('whole_assembly_rigid_transform rotation must be proper and orthonormal')

    def extraction_vector(self, direction):
        """Resolve an existing action label to a unit world-space vector."""
        vector = np.asarray(DIRECTIONS[direction], dtype=float)
        if self.path_mode == 'straight_source_axes':
            vector = self.setup_rotation @ vector
            vector = vector / np.linalg.norm(vector)
        return vector

    def extraction_distance(self, pid, vector):
        """Clear all surviving AABBs along the actual path, plus 15 mm."""
        allbounds = np.asarray([self.bounds(p) for p in self.remaining])
        pb = self.bounds(pid)
        if self.path_mode == 'straight_world_axes':
            # Preserve the exact old arithmetic for backwards comparison.
            axis = int(np.argmax(abs(vector)))
            sign = int(vector[axis])
            return float((allbounds[:, 1, axis].max() - pb[0, axis] if sign > 0
                          else pb[1, axis] - allbounds[:, 0, axis].min()) + .015)
        # Projection support functions for every AABB. AABB overlap itself is
        # never used to reject an extraction; MuJoCo contacts do that below.
        other_max = np.sum(np.where(vector >= 0, allbounds[:, 1], allbounds[:, 0]) * vector, axis=1)
        moving_min = np.sum(np.where(vector >= 0, pb[0], pb[1]) * vector)
        return float(other_max.max() - moving_min + .015)

    def snapshot(self):
        value = super().snapshot()
        value['path_mode'] = self.path_mode
        value['extraction_collision'] = self.extraction_collision
        value['action_frame'] = 'source_assembly' if self.path_mode == 'straight_source_axes' else 'world'
        value['direction_vectors_world'] = {name: self.extraction_vector(name).tolist() for name in DIRECTIONS}
        value['scope'] = ('Sampled fixed-quaternion straight extraction in the declared action frame '
                          'with the declared collision representation, '
                          'then MuJoCo residual gravity/contact/friction stability. '
                          'No force-driven extraction or arbitrary rotation planner.')
        return value

    observe = snapshot

    def _operation(self, pid, direction, commit):
        """Old transaction/trace contract with frame-aware path coordinates."""
        if self.checks >= self.max_checks:
            raise RuntimeError('checker budget exhausted')
        self.checks += 1
        started = time.perf_counter()
        before = list(self.remaining)
        result = dict(valid=False, reason='', blockers=[], stability=None,
                      part_id=pid, direction=direction, checker_call=self.checks,
                      path_samples=0, physics_steps=0, path_mode=self.path_mode,
                      extraction_collision=self.extraction_collision)
        if not isinstance(pid, str) or not isinstance(direction, str):
            result['reason'] = 'invalid_arguments'
        elif pid not in self.remaining:
            result['reason'] = 'unknown_or_removed_part'
        elif self.parts[pid].get('fixed', False):
            result['reason'] = 'fixed_part'
        elif direction not in self.parts[pid].get('allowed_directions', list(DIRECTIONS)) or direction not in DIRECTIONS:
            result['reason'] = 'invalid_direction'
        else:
            vector = self.extraction_vector(direction)
            result['resolved_direction_world'] = vector.tolist()
            distance = self.extraction_distance(pid, vector)
            samples = max(1, int(math.ceil(distance / self.physics['path_step_m'])))
            initial = np.asarray(self.poses[pid]['position'])
            frames = []
            initial_penetrations = {}
            if self.extraction_collision == 'source_mesh_bvh':
                if self._source_collision is None:
                    from disassembly_real_v3.source_collision import SourceMeshCollisionChecker
                    self._source_collision = SourceMeshCollisionChecker(self)
                result['collision_policy'] = self._source_collision.begin_path(pid, self.remaining, self.poses)
            else:
                model, data, ids, geomids = self._build()
                bid = ids[pid]
                joint = model.body_jntadr[bid]
                q = model.jnt_qposadr[joint]
                for contact in data.contact:
                    pair = tuple(sorted((int(contact.geom1), int(contact.geom2))))
                    initial_penetrations[pair] = max(initial_penetrations.get(pair, 0.), -float(contact.dist))
            for index in range(samples + 1):
                position = initial + vector * distance * index / samples
                result['path_samples'] += 1
                blockers = set()
                if self.extraction_collision == 'source_mesh_bvh':
                    pose = {**self.poses[pid], 'position': position.tolist()}
                    source_check = self._source_collision.check_pose(pose)
                    blockers.update(source_check['blockers'])
                    if blockers:
                        result['collision_details'] = source_check['details']
                else:
                    data.qpos[q:q+3] = position
                    mujoco.mj_forward(model, data)
                    for contact in data.contact:
                        a, b = geomids.get(int(contact.geom1)), geomids.get(int(contact.geom2))
                        pair = tuple(sorted((int(contact.geom1), int(contact.geom2))))
                        initial_depth = initial_penetrations.get(pair, 0.)
                        permitted = max(self.physics['penetration_tolerance_m'],
                                        initial_depth + self.physics['resting_contact_slack_m'])
                        if initial_depth > self.physics['stable_penetration_m']:
                            permitted = self.physics['penetration_tolerance_m']
                        if pid in (a, b) and contact.dist < -permitted:
                            other = b if a == pid else a
                            if other is not None and other != pid:
                                blockers.add(other)
                if blockers:
                    result.update(reason='path_collision', blockers=sorted(blockers),
                                  collision_distance_m=float(distance * index / samples))
                    break
                if self.capture and index % max(1, samples // 24) == 0:
                    poses = copy.deepcopy(self.poses)
                    poses[pid]['position'] = position.tolist()
                    frames.append(poses)
            result['extraction_distance_m'] = distance
            if not result['reason']:
                after = [p for p in self.remaining if p != pid]
                stability, final = self.settle(after, self.poses)
                result.update(stability=stability, physics_steps=stability['physics_steps'],
                              valid=stability['stable'], reason='ok' if stability['stable'] else 'unstable_remainder')
                if result['valid'] and commit:
                    if self.capture:
                        for pose in frames:
                            self._record_frame('기하학 경로 재생: ' + pid, pose, before, advance=.03)
                        self.settle(after, self.poses, capture=True)
                    self.remaining = after
                    self.poses = final
                    self.actions.append(dict(part_id=pid, direction=direction, stability=stability))
                    self._record_frame('제거 승인: ' + pid)
        result['elapsed_seconds'] = time.perf_counter() - started
        result['committed'] = bool(commit and result['valid'])
        self.trace.append({**copy.deepcopy(result), 'operation': 'remove' if commit else 'check',
                           'remaining_before': before, 'remaining_after': list(self.remaining)})
        self.events.append(dict(frame=max(0, len(self.frames)-1), time=self.clock,
                                type=result['reason'], part_id=pid,
                                message=f'{pid} {direction}: {result["reason"]}'))
        return copy.deepcopy(result)


DisassemblySim = FullDisassemblySim

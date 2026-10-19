"""Original-triangle BVH extraction checks; no reference paths or dynamics.

FCL supplies surface-intersection neighborhoods only. It never supplies the
penetration threshold. Deterministic material samples query original-mesh
signed distances and keep their own operation-initial signed-depth baseline.
Unresolved intersections fail closed, except proven separating/touching planes
or motion bounded by the existing numerical slack. This is a finite sampled
material test, not exact continuous solid collision or penetration depth.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import sys

DEPENDENCY_ROOT = Path(__file__).resolve().parent / '.collision_deps'
if str(DEPENDENCY_ROOT) not in sys.path:
    sys.path.insert(0, str(DEPENDENCY_ROOT))

import fcl
import numpy as np
from scipy.spatial.transform import Rotation
import trimesh


MAX_CONTACTS = 20000
SURFACE_EPSILON_M = 1e-8
INWARD_OFFSETS_M = (0., .0002, .001)


def _winding_inside(mesh, points):
    triangles = np.asarray(mesh.triangles)
    answer = []
    for point in np.asarray(points):
        t = triangles-point
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        la, lb, lc = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1), np.linalg.norm(c, axis=1)
        numerator = np.einsum('ij,ij->i', a, np.cross(b, c))
        denominator = (la*lb*lc + np.einsum('ij,ij->i', a, b)*lc
                       + np.einsum('ij,ij->i', b, c)*la + np.einsum('ij,ij->i', c, a)*lb)
        winding = float(np.sum(2*np.arctan2(numerator, denominator))/(4*np.pi))
        answer.append(abs(winding) > .5)
    return np.asarray(answer, dtype=bool)


def signed_material_distance(mesh, points):
    """Inside positive, outside negative, explicit surface band zero; no RNG."""
    points = np.asarray(points, dtype=float)
    if len(points) == 0:
        return np.empty(0)
    closest, distance, triangles = trimesh.proximity.closest_point(mesh, points)
    signed = -distance.copy()
    nonzero = distance > SURFACE_EPSILON_M
    if not nonzero.any():
        return np.zeros(len(points))
    indices = np.flatnonzero(nonzero)
    normals = mesh.face_normals[triangles[indices]]
    normal_offset = np.einsum('ij,ij->i', points[indices]-closest[indices], normals)
    projection = points[indices]-normals*normal_offset[:, None]
    bary = trimesh.triangles.points_to_barycentric(mesh.triangles[triangles[indices]], projection)
    interior_projection = np.all((bary >= -1e-10) & (bary <= 1+1e-10), axis=1)
    normal_points = indices[interior_projection]
    signed[normal_points] = -np.sign(normal_offset[interior_projection])*distance[normal_points]
    ambiguous = indices[~interior_projection]
    if len(ambiguous):
        inside = _winding_inside(mesh, points[ambiguous])
        signed[ambiguous] = np.where(inside, distance[ambiguous], -distance[ambiguous])
    signed[~nonzero] = 0.
    return signed


def rotation(pose):
    q = pose['quaternion']
    return Rotation.from_quat([*q[1:], q[0]]).as_matrix()


@lru_cache(maxsize=256)
def _load_geometry(path, size, modified_ns):
    """Cache geometry only; poses and collision outcomes never enter the cache."""
    mesh = trimesh.load(path, force='mesh', process=False)
    if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume <= 0:
        raise ValueError('Source collision requires a closed consistently oriented solid: ' + path)
    # Topology export can duplicate coordinate indices. Exact-coordinate welding
    # is only for component validation; it moves no triangle.
    vertices, inverse = np.unique(np.asarray(mesh.vertices), axis=0, return_inverse=True)
    connected = trimesh.Trimesh(vertices=vertices, faces=inverse[np.asarray(mesh.faces)], process=False)
    if len(connected.split(only_watertight=False)) != 1:
        raise ValueError('Source containment guard requires one connected component: ' + path)
    bvh = fcl.BVHModel()
    bvh.beginModel()
    bvh.addSubModel(np.asarray(mesh.vertices), np.asarray(mesh.faces))
    bvh.endModel()
    return mesh, bvh


class SourceMeshCollisionChecker:
    def __init__(self, sim):
        self.physics = sim.physics
        self.meshes = {}
        self.objects = {}
        for pid, part in sim.parts.items():
            path = sim._path(part['visual_mesh'])
            stat = path.stat()
            mesh, bvh = _load_geometry(str(path), stat.st_size, stat.st_mtime_ns)
            self.meshes[pid] = mesh
            self.objects[pid] = fcl.CollisionObject(bvh, fcl.Transform())
        self.poses = {}
        self.initial_contacts = {}
        self.initial_pair_envelopes = {}
        self.material_samples = {pid: {} for pid in self.meshes}
        self.initial_depth_samples = {}
        self.initial_floor_depth = 0.
        self.moving = None
        self.remaining = []
        self.initial_pair_certificates = {}

    def set_pose(self, pid, pose):
        self.poses[pid] = pose
        self.objects[pid].setTransform(fcl.Transform(rotation(pose), np.asarray(pose['position'])))

    def _contacts(self, other):
        result = fcl.CollisionResult()
        count = fcl.collide(self.objects[self.moving], self.objects[other],
                            fcl.CollisionRequest(num_max_contacts=MAX_CONTACTS, enable_contact=True), result)
        if count >= MAX_CONTACTS:
            raise RuntimeError('Original-mesh contact capacity reached; no truncated pass is allowed')
        return result.contacts

    def begin_path(self, moving, remaining, poses):
        self.moving = moving
        self.remaining = [pid for pid in remaining if pid != moving]
        for pid in remaining:
            self.set_pose(pid, poses[pid])
        self.initial_contacts = {}
        self.initial_pair_envelopes = {}
        self.initial_depth_samples = {}
        self.initial_poses = {pid: {'position': list(poses[pid]['position']),
                                   'quaternion': list(poses[pid]['quaternion'])} for pid in remaining}
        summaries = []
        self.initial_pair_certificates = {}
        for other in self.remaining:
            contacts = self._contacts(other)
            for c in contacts:
                key = (other, int(c.b1), int(c.b2))
                self.initial_contacts[key] = max(self.initial_contacts.get(key, 0.), float(c.penetration_depth))
            self.initial_pair_envelopes[other] = max([float(c.penetration_depth) for c in contacts] + [0.])
            if contacts:
                left, has_left = self._material_check(self.moving, other, [c.b1 for c in contacts])
                right, has_right = self._material_check(other, self.moving, [c.b2 for c in contacts])
                certified = not (left or right) and (has_left or has_right or self._separating_touch(other, contacts))
            else:
                certified = not (self._contained(self.moving, other) or self._contained(other, self.moving))
            self.initial_pair_certificates[other] = bool(certified)
            summaries.append(dict(other_part=other, initial_triangle_contacts=len(contacts),
                                  maximum_initial_FCL_contact_depth_m=max([float(c.penetration_depth) for c in contacts] + [0.]),
                                  initial_material_certificate=bool(certified)))
        self.initial_floor_depth = max(0., -self._minimum_height(moving))
        return dict(method='original_triangle_BVH_plus_per_material_sample_signed_depth',
                    initial_part_pairs=summaries, initial_floor_depth_m=self.initial_floor_depth,
                    new_contact_tolerance_m=self.physics['penetration_tolerance_m'],
                    initial_contact_slack_m=self.physics['resting_contact_slack_m'],
                    envelope_scope='Each indexed source-material point is compared to that same point at operation-initial poses, symmetrically in both part directions. FCL contact depths never admit a collision.',
                    material_initial_depth_cap_m=self.physics['penetration_tolerance_m'],
                    surface_band_m=SURFACE_EPSILON_M,
                    surface_samples='Triangle vertices, three edge midpoints, centroid; inward normal offsets; outside-own-material points discarded.',
                    inward_offsets_m=list(INWARD_OFFSETS_M),
                    uncertainty_policy='Unresolved BVH intersection fails closed unless a separating/touching plane proves disjoint or global point displacement is bounded by initial contact slack.',
                    contact_capacity=MAX_CONTACTS,
                    exactness='Original triangles and deterministic finite material samples; discrete trajectory poses; not exact continuous collision or maximum solid penetration.')

    def _minimum_height(self, pid):
        pose = self.poses[pid]
        return float((self.meshes[pid].vertices @ rotation(pose).T + pose['position'])[:, 2].min())

    def _contained(self, inside, outside):
        """No surface intersections: test representative vertices in the solid."""
        inner_mesh = self.meshes[inside]
        pose_in, pose_out = self.poses[inside], self.poses[outside]
        indices = np.unique([0, len(inner_mesh.vertices)//2, len(inner_mesh.vertices)-1])
        world = inner_mesh.vertices[indices] @ rotation(pose_in).T + pose_in['position']
        local = (world - pose_out['position']) @ rotation(pose_out)
        out_mesh = self.meshes[outside]
        depth = float(signed_material_distance(out_mesh, local).max())
        # Strictly nested, disjoint connected surfaces are a solid collision
        # even if the sampled clearance happens to be below contact tolerance.
        if depth <= SURFACE_EPSILON_M:
            return None
        return dict(kind='solid_containment', contained_part=inside, containing_part=outside,
                    sampled_interior_depth_m=depth)

    def _triangle_samples(self, pid, triangle_ids):
        ids = sorted(set(map(int, triangle_ids)))
        cache = self.material_samples[pid]
        new_ids = [tid for tid in ids if tid not in cache]
        if new_ids:
            mesh = self.meshes[pid]
            triangles = mesh.triangles[new_ids]
            base = np.stack([triangles[:, 0], triangles[:, 1], triangles[:, 2],
                             (triangles[:, 0]+triangles[:, 1])/2,
                             (triangles[:, 1]+triangles[:, 2])/2,
                             (triangles[:, 2]+triangles[:, 0])/2,
                             triangles.mean(axis=1)], axis=1)
            normals = mesh.face_normals[new_ids]
            blocks = np.concatenate([base-normals[:, None, :]*offset for offset in INWARD_OFFSETS_M], axis=1)
            flat = blocks.reshape(-1, 3)
            own_depth = signed_material_distance(mesh, flat).reshape(len(new_ids), -1)
            for i, tid in enumerate(new_ids):
                cache[tid] = blocks[i][own_depth[i] >= -SURFACE_EPSILON_M]
        return ids, [cache[tid] for tid in ids]

    def _other_local(self, points, owner, outside, poses):
        a, b = poses[owner], poses[outside]
        world = points @ rotation(a).T + a['position']
        return (world-b['position']) @ rotation(b)

    def _material_check(self, owner, outside, triangle_ids):
        ids, blocks = self._triangle_samples(owner, triangle_ids)
        sizes = [len(block) for block in blocks]
        if not sum(sizes):
            return [], False
        points = np.concatenate(blocks)
        values = signed_material_distance(self.meshes[outside], self._other_local(points, owner, outside, self.poses))
        keys = [(owner, outside, tid) for tid in ids]
        missing = [i for i, key in enumerate(keys) if key not in self.initial_depth_samples]
        if missing:
            new_points = np.concatenate([blocks[i] for i in missing])
            depths = signed_material_distance(self.meshes[outside], self._other_local(new_points, owner, outside, self.initial_poses))
            cursor = 0
            for i in missing:
                n = sizes[i]
                self.initial_depth_samples[keys[i]] = depths[cursor:cursor+n].copy()
                cursor += n
        initial = np.concatenate([self.initial_depth_samples[key] for key in keys])
        permitted = np.maximum(self.physics['penetration_tolerance_m'], np.maximum(initial, 0.)+self.physics['resting_contact_slack_m'])
        permitted[initial > self.physics['penetration_tolerance_m']+SURFACE_EPSILON_M] = self.physics['penetration_tolerance_m']
        bad = np.flatnonzero(values > permitted+SURFACE_EPSILON_M)
        failures = []
        if len(bad):
            index = int(bad[np.argmax(values[bad]-permitted[bad])])
            failures.append(dict(kind='source_material_sample', sample_owner=owner, other_part=outside,
                                 signed_depth_m=float(values[index]), initial_signed_depth_m=float(initial[index]),
                                 permitted_depth_m=float(permitted[index]), owner_local_point_m=points[index].tolist()))
        return failures, bool(np.any(values > SURFACE_EPSILON_M))

    def _small_initial_motion(self):
        a, b = self.poses[self.moving], self.initial_poses[self.moving]
        vertices = self.meshes[self.moving].vertices
        delta = vertices @ (rotation(a)-rotation(b)).T + np.asarray(a['position'])-b['position']
        return float(np.linalg.norm(delta, axis=1).max()) <= self.physics['resting_contact_slack_m']

    def _separating_touch(self, other, contacts):
        """A separating support plane proves no material overlap globally."""
        a, b = self.poses[self.moving], self.poses[other]
        ra, rb = rotation(a), rotation(b)
        av = self.meshes[self.moving].vertices @ ra.T + a['position']
        bv = self.meshes[other].vertices @ rb.T + b['position']
        axes = [np.eye(3)]
        if contacts:
            axes.append(self.meshes[self.moving].face_normals[[int(c.b1) for c in contacts]] @ ra.T)
            axes.append(self.meshes[other].face_normals[[int(c.b2) for c in contacts]] @ rb.T)
        normals = np.unique(np.round(np.concatenate(axes), 10), axis=0)
        normals = normals[np.isfinite(normals).all(axis=1) & (np.linalg.norm(normals, axis=1) > .5)]
        for normal in normals:
            pa, pb = av @ normal, bv @ normal
            if pa.min() >= pb.max()-SURFACE_EPSILON_M or pb.min() >= pa.max()-SURFACE_EPSILON_M:
                return True
        return False

    def check_pose(self, pose):
        self.set_pose(self.moving, pose)
        blockers = []
        failures = []
        for other in self.remaining:
            contacts = self._contacts(other)
            bad = []
            if contacts:
                left, has_left = self._material_check(self.moving, other, [c.b1 for c in contacts])
                right, has_right = self._material_check(other, self.moving, [c.b2 for c in contacts])
                bad.extend(left+right)
                bounded_initial = self.initial_pair_certificates.get(other, False) and self._small_initial_motion()
                if (not bad and not has_left and not has_right and not bounded_initial
                        and not self._separating_touch(other, contacts)):
                    bad.append(dict(kind='unresolved_surface_intersection', other_part=other,
                                    note='BVH intersected; finite samples found no material witness and no separating plane or bounded-slack proof. Rejected conservatively.'))
            # A pair with surface intersections is already checked above.
            # A pair with disjoint surfaces might still be nested.
            if not contacts:
                contained = self._contained(self.moving, other) or self._contained(other, self.moving)
                if contained:
                    bad.append(contained)
            if bad:
                blockers.append(other)
                failures.extend(sorted(bad, key=lambda c: c.get('depth_m', c.get('sampled_interior_depth_m', 0.)), reverse=True)[:4])
        depth = max(0., -self._minimum_height(self.moving))
        floor_permitted = max(self.physics['penetration_tolerance_m'],
                              self.initial_floor_depth + self.physics['resting_contact_slack_m'])
        if self.initial_floor_depth > self.physics['stable_penetration_m']:
            floor_permitted = self.physics['penetration_tolerance_m']
        if depth > floor_permitted:
            blockers.append('__floor__')
            failures.append(dict(kind='source_vertex_floor', depth_m=depth,
                                 permitted_depth_m=floor_permitted))
        return dict(blockers=sorted(set(blockers)), details=failures[:8])

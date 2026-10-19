"""Adversarial original-mesh collision diagnostics; no held-out CAD/model."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scipy.spatial.transform import Rotation
import trimesh

from disassembly_real_v3.simulator import FullDisassemblySim
from disassembly_real_v3.source_collision import signed_material_distance


class SourceCollisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='source_mesh_collision_dev_')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def case(self, specs, rotation_degrees=0, mode='straight_world_axes'):
        rot = Rotation.from_euler('z', rotation_degrees, degrees=True)
        q = rot.as_quat()
        transform = np.eye(4)
        transform[:3, :3] = rot.as_matrix()
        parts = []
        for pid, position, extents, fixed in specs:
            mesh = trimesh.creation.box(extents=extents)
            target = self.folder / (pid + '.obj')
            mesh.export(target)
            parts.append(dict(id=pid, position=rot.apply(position).tolist(),
                              quaternion=[float(q[3]), *map(float, q[:3])],
                              visual_mesh=str(target), collision_meshes=[str(target)],
                              local_bounds=mesh.bounds.tolist(), mass_kg=.01, fixed=fixed))
        case = dict(id='source_collision_development_diagnostic', target_id='moving',
                    parts=parts, whole_assembly_rigid_transform=transform.tolist(),
                    physics=dict(gravity=[0, 0, 0], settle_seconds=.02,
                                 path_step_m=.0005, path_mode=mode,
                                 extraction_collision='source_mesh_bvh'))
        path = self.folder / 'case.json'
        path.write_text(json.dumps(case))
        return FullDisassemblySim(path, max_checks=20)

    def stack(self, overlap=0.):
        return self.case([('moving', [0, 0, .03-overlap], [.02, .02, .02], False),
                          ('base', [0, 0, .01], [.02, .02, .02], True)])

    def test_exact_touch_separation_and_tangential_slide_pass(self):
        for direction in ('+z', '+x'):
            sim = self.stack()
            result = sim.remove('moving', direction)
            self.assertTrue(result['committed'], result)

    def test_micrometre_overlap_tangent_passes_but_millimetre_deepening_fails(self):
        tangent = self.stack(overlap=.000001)
        result = tangent.remove('moving', '+x')
        self.assertTrue(result['committed'], result)
        deepening = self.stack(overlap=.000001)
        result = deepening.remove('moving', '-z')
        self.assertEqual(result['reason'], 'path_collision')
        self.assertLessEqual(result['collision_distance_m'], .0011)
        self.assertTrue(any(d['kind'] == 'source_material_sample' for d in result['collision_details']), result)

    def test_containment_rejected_in_both_surface_disjoint_orientations(self):
        for large_moving in (False, True):
            a, b = ([.1]*3, [.01]*3) if large_moving else ([.01]*3, [.1]*3)
            sim = self.case([('moving', [0, 0, .2], a, False),
                             ('outer_or_inner', [0, 0, .2], b, True)])
            result = sim.check('moving', '+x')
            self.assertEqual(result['reason'], 'path_collision')
            self.assertTrue(any(d['kind'] == 'solid_containment' for d in result['collision_details']), result)

    def test_near_coincident_nested_solids_are_not_a_tolerated_surface_contact(self):
        sim = self.case([('moving', [0, 0, .2], [.0998]*3, False),
                         ('outer', [0, 0, .2], [.1]*3, True)])
        result = sim.check('moving', '+x')
        self.assertEqual(result['reason'], 'path_collision')
        self.assertTrue(any(d['kind'] == 'solid_containment' for d in result['collision_details']), result)

    def test_offcentre_intersecting_bars_cannot_pass_on_initial_slack(self):
        sim = self.case([('moving', [0, 0, 1], [2, .1, .1], False),
                         ('bar', [.47, .2, 1], [.1, 2, .1], True)])
        result = sim.check('moving', '+x')
        self.assertEqual(result['reason'], 'path_collision')
        self.assertEqual(result['collision_distance_m'], 0.)

    def test_midpath_crossing_rejected_even_when_start_and_final_positions_are_clear(self):
        sim = self.case([('moving', [-.06, .013, .05], [.04, .004, .004], False),
                         ('bar', [0, 0, .05], [.004, .04, .004], True)])
        result = sim.remove('moving', '+x')
        self.assertEqual(result['reason'], 'path_collision')
        self.assertGreater(result['collision_distance_m'], .02)
        self.assertLess(result['collision_distance_m'], .08)

    def l_fixture(self, overlap):
        sim = self.case([('moving', [.02, 0, .015-overlap], [.01]*3, False),
                         ('fixture', [0, 0, 0], [.01]*3, True)])
        # One connected watertight L-shaped prism, with 1 micrometre floor
        # overlap supplying a finite near-contact witness. Its same-part end
        # wall must block later. Exact concave tangency can conservatively
        # reject as unresolved; exact convex tangency is tested separately.
        polygon = np.array([[0, 0], [.06, 0], [.06, .06], [.05, .06], [.05, .01], [0, .01]])
        vertices = np.array([[x, y, z] for y in [-.02, .02] for x, z in polygon])
        cap = np.array([[0, 1, 4], [0, 4, 5], [1, 2, 3], [1, 3, 4]])
        faces = [*cap.tolist(), *(cap[:, ::-1]+6).tolist()]
        for i in range(6):
            j = (i+1) % 6
            faces.extend([[i, j+6, j], [i, i+6, j+6]])
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        self.assertTrue(mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0)
        fixture_path = self.folder / 'fixture_l.obj'
        mesh.export(fixture_path)
        case = sim.case
        part = next(p for p in case['parts'] if p['id'] == 'fixture')
        part.update(visual_mesh=str(fixture_path), collision_meshes=[str(fixture_path)],
                    local_bounds=mesh.bounds.tolist())
        path = self.folder / 'l_fixture_case.json'
        path.write_text(json.dumps(case))
        return FullDisassemblySim(path)

    def test_initial_floor_contact_does_not_whitelist_new_wall_collision_on_same_part(self):
        sim = self.l_fixture(overlap=.000001)
        result = sim.remove('moving', '+x')
        self.assertEqual(result['reason'], 'path_collision')
        self.assertGreater(result['collision_distance_m'], .015)
        self.assertIn('fixture', result['blockers'])

    def test_known_limit_exact_concave_L_tangency_rejects_conservatively(self):
        sim = self.l_fixture(overlap=0.)
        result = sim.check('moving', '+x')
        self.assertEqual(result['reason'], 'path_collision')
        self.assertEqual(result['collision_distance_m'], 0.)
        self.assertTrue(any(d['kind'] == 'unresolved_surface_intersection'
                            for d in result['collision_details']))

    def test_rotated_corridor_preserves_source_axis_and_blocks_world_axis(self):
        specs = [('moving', [0, 0, .05], [.008]*3, False),
                 ('wall1', [0, .017, .05], [.08, .01, .024], True),
                 ('wall2', [0, -.017, .05], [.08, .01, .024], True)]
        sim = self.case(specs, 45, 'straight_source_axes')
        self.assertTrue(sim.check('moving', '+x')['valid'])
        sim = self.case(specs, 45, 'straight_world_axes')
        self.assertEqual(sim.check('moving', '+x')['reason'], 'path_collision')

    def test_surface_band_and_inside_outside_sign_are_explicit_and_deterministic(self):
        mesh = trimesh.creation.box(extents=[.1]*3)
        points = np.array([[0, 0, 0], [.1, 0, 0], [.05, 0, 0], [.05+1e-9, 0, 0],
                           [.1, .1, 0], [.1, .1, .1]])
        first = signed_material_distance(mesh, points)
        second = signed_material_distance(mesh, points)
        np.testing.assert_array_equal(first, second)
        np.testing.assert_allclose(first, [.05, -.05, 0, 0, -np.sqrt(2)*.05, -np.sqrt(3)*.05], atol=1e-12)

    def test_previous_development_CAD_still_completes_new_collision_mode(self):
        workspace = Path(__file__).resolve().parents[2]
        source = workspace / 'disassembly_real_v2/cases/fresh_anchor_frozen_01/asap_00494.json'
        if not source.exists():
            self.skipTest('Preserved development CAD unavailable')
        case = json.loads(source.read_text())
        case['physics']['extraction_collision'] = 'source_mesh_bvh'
        case['physics']['path_mode'] = 'straight_world_axes'
        for part in case['parts']:
            part['visual_mesh'] = str((source.parent / part['visual_mesh']).resolve())
            part['collision_meshes'] = [str((source.parent / p).resolve()) for p in part['collision_meshes']]
        path = self.folder / 'old_development_cad_bvh.json'
        path.write_text(json.dumps(case))
        sim = FullDisassemblySim(path, max_checks=10)
        for pid, direction in [('0', '+z'), ('1', '+x'), ('2', '+x'), ('3', '+z')]:
            result = sim.remove(pid, direction)
            self.assertTrue(result['committed'], result)
        self.assertTrue(sim.success)


if __name__ == '__main__':
    unittest.main()

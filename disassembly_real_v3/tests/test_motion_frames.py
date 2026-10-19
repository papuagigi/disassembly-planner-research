"""Actual MuJoCo frame/transaction regressions on local diagnostic boxes.

The corridor is a deliberately constructed diagnostic, not a CAD benchmark or
held-out product. It isolates frame expressiveness while using the real contact
checker. These tests make no provider calls and do not learn a skill.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scipy.spatial.transform import Rotation
import trimesh

from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_recovery.shared_api import physical_state_key
from disassembly_real_v2.simulator import FullDisassemblySim as OldSim
from disassembly_real_v3.simulator import FullDisassemblySim


def physical_result(value):
    return {k: v for k, v in value.items()
            if k not in {'elapsed_seconds', 'path_mode', 'resolved_direction_world', 'extraction_collision'}}


class MotionFrameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='motion_frame_dev_')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def corridor(self, mode, degrees=45):
        rotation = Rotation.from_euler('z', degrees, degrees=True)
        matrix = np.eye(4)
        matrix[:3, :3] = rotation.as_matrix()
        xyzw = rotation.as_quat()
        parts = []
        for pid, center, extent, fixed in [
                ('moving', [0, 0, .05], [.008, .008, .008], False),
                ('wall1', [0, .017, .05], [.08, .01, .024], True),
                ('wall2', [0, -.017, .05], [.08, .01, .024], True)]:
            mesh = trimesh.creation.box(extents=extent)
            path = self.folder / (pid + '.obj')
            mesh.export(path)
            parts.append(dict(id=pid, position=rotation.apply(center).tolist(),
                quaternion=[float(xyzw[3]), *map(float, xyzw[:3])],
                visual_mesh=str(path), collision_meshes=[str(path)],
                local_bounds=mesh.bounds.tolist(), mass_kg=.01, fixed=fixed))
        case = dict(id='synthetic_frame_corridor_development_only', target_id='moving',
                    whole_assembly_rigid_transform=matrix.tolist(), parts=parts,
                    physics=dict(path_mode=mode, gravity=[0, 0, 0], settle_seconds=.04))
        target = self.folder / (mode + '.json')
        target.write_text(json.dumps(case))
        return target

    def test_rotated_corridor_source_axis_clear_world_axis_blocked(self):
        old_frame = FullDisassemblySim(self.corridor('straight_world_axes'), max_checks=10)
        source_frame = FullDisassemblySim(self.corridor('straight_source_axes'), max_checks=10)
        blocked = old_frame.check('moving', '+x')
        clear = source_frame.check('moving', '+x')
        self.assertEqual(blocked['reason'], 'path_collision')
        self.assertEqual(blocked['blockers'], ['wall2'])
        self.assertEqual(clear['reason'], 'ok')
        np.testing.assert_allclose(clear['resolved_direction_world'], [2**-.5, 2**-.5, 0], atol=1e-12)
        self.assertGreater(clear['path_samples'], 2)
        self.assertEqual(source_frame.remaining, ['moving', 'wall1', 'wall2'])

    def test_same_world_mode_matches_old_physical_outcomes_for_all_six_labels(self):
        path = self.corridor('straight_world_axes')
        old = OldSim(path, max_checks=10)
        new = FullDisassemblySim(path, max_checks=10)
        for direction in ('+x', '-x', '+y', '-y', '+z', '-z'):
            self.assertEqual(physical_result(old.check('moving', direction)),
                             physical_result(new.check('moving', direction)))
        self.assertEqual(old.export_state()['poses'], new.export_state()['poses'])

    def test_existing_development_CAD_four_step_sequence_matches_old_world_mode(self):
        workspace = Path(__file__).resolve().parents[2]
        case = workspace / 'disassembly_real_v2/cases/fresh_anchor_frozen_01/asap_00494.json'
        if not case.exists():
            self.skipTest('Preserved development CAD is unavailable')
        old = OldSim(case, max_checks=10)
        new = FullDisassemblySim(case, max_checks=10)
        for pid, direction in [('0', '+z'), ('1', '+x'), ('2', '+x'), ('3', '+z')]:
            before_old = physical_state_key(old.export_state())
            before_new = physical_state_key(new.export_state())
            self.assertEqual(before_old, before_new)
            old_result = old.remove(pid, direction)
            new_result = new.remove(pid, direction)
            self.assertTrue(old_result['committed'])
            self.assertEqual(physical_result(old_result), physical_result(new_result))
            self.assertEqual(physical_state_key(old.export_state()), physical_state_key(new.export_state()))
        self.assertTrue(old.success and new.success)

    def test_identity_frame_has_identical_paths_and_stability(self):
        path = self.corridor('straight_source_axes', degrees=0)
        old = OldSim(path, max_checks=10)
        new = FullDisassemblySim(path, max_checks=10)
        for direction in ('+x', '-x', '+y', '-y', '+z', '-z'):
            self.assertEqual(physical_result(old.check('moving', direction)),
                             physical_result(new.check('moving', direction)))

    def test_frame_mapping_is_not_affected_by_setup_translation(self):
        path = self.corridor('straight_source_axes')
        case = json.loads(path.read_text())
        case['whole_assembly_rigid_transform'][0][3] = 20
        path.write_text(json.dumps(case))
        sim = FullDisassemblySim(path)
        np.testing.assert_allclose(sim.extraction_vector('+x'), [2**-.5, 2**-.5, 0], atol=1e-12)

    def test_source_removal_capture_and_shared_restore_preserve_contract(self):
        sim = FullDisassemblySim(self.corridor('straight_source_axes'), max_checks=10, capture=True)
        api = SharedAPI(sim, max_checks=10)
        initial = sim.export_state()
        initial_key = physical_state_key(initial)
        checkpoint = api.checkpoint()
        result = api.remove('moving', '+x')
        self.assertTrue(result['committed'])
        self.assertEqual(sim.remaining, ['wall1', 'wall2'])
        self.assertEqual(sim.checks, 1)
        extraction = [f for f in sim.frames if f['phase'] == 'extraction']
        self.assertGreater(len(extraction), 2)
        for frame in extraction:
            delta = np.asarray(frame['poses']['moving']['position']) - initial['poses']['moving']['position']
            self.assertAlmostEqual(delta[0], delta[1], places=12)
            self.assertAlmostEqual(delta[2], 0, places=12)
            np.testing.assert_allclose(frame['poses']['moving']['quaternion'],
                                       [*initial['poses']['moving']['quaternion'][1:],
                                        initial['poses']['moving']['quaternion'][0]], atol=1e-12)
        api.restore(checkpoint)
        self.assertEqual(physical_state_key(sim.export_state()), initial_key)
        self.assertEqual(sim.checks, 1)
        self.assertEqual(len(sim.trace), 1)
        self.assertEqual(sim.actions, [])
        self.assertEqual(api.snapshot()['action_frame'], 'source_assembly')
        self.assertEqual(api.snapshot()['recovery']['successful_restores'], 1)

    def test_rejects_unknown_mode_and_nonrigid_setup(self):
        path = self.corridor('unsupported_force_mode')
        with self.assertRaisesRegex(ValueError, 'Unsupported path_mode'):
            FullDisassemblySim(path)
        path = self.corridor('straight_source_axes')
        case = json.loads(path.read_text())
        case['whole_assembly_rigid_transform'][0][0] *= 2
        path.write_text(json.dumps(case))
        with self.assertRaisesRegex(ValueError, 'proper and orthonormal'):
            FullDisassemblySim(path)

    def test_collision_failure_is_transactional_and_spends_one_check(self):
        sim = FullDisassemblySim(self.corridor('straight_source_axes'), max_checks=1)
        before = copy.deepcopy(sim.export_state())
        result = sim.remove('moving', '+y')
        self.assertEqual(result['reason'], 'path_collision')
        self.assertFalse(result['committed'])
        self.assertEqual(before['remaining'], sim.remaining)
        self.assertEqual(before['poses'], sim.poses)
        self.assertEqual(sim.checks, 1)
        with self.assertRaisesRegex(RuntimeError, 'budget exhausted'):
            sim.check('moving', '+x')
        self.assertEqual(sim.checks, 1)


if __name__ == '__main__':
    unittest.main()

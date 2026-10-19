"""Small physical task-adapter regressions; no live provider or scored CAD.

The separated cubes test endpoint/namespace/state semantics, not CAD planning
performance. The original MuJoCo path and residual-stability checks run normally.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from disassembly_hybrid.graph import canonical_candidates
from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_recovery.shared_api import physical_state_key
from disassembly_real_v3.simulator import FullDisassemblySim
from disassembly_real_v3.memory import SkillBank
from disassembly_real_v3 import code_actor, controller, runtime
from disassembly_mujoco.simulator import DisassemblySim as SelectiveSim


ROOT = Path(__file__).resolve().parents[1]
CUBE = '''v -0.005 -0.005 -0.005
v 0.005 -0.005 -0.005
v 0.005 0.005 -0.005
v -0.005 0.005 -0.005
v -0.005 -0.005 0.005
v 0.005 -0.005 0.005
v 0.005 0.005 0.005
v -0.005 0.005 0.005
f 1 3 2
f 1 4 3
f 5 6 7
f 5 7 8
f 1 2 6
f 1 6 5
f 2 3 7
f 2 7 6
f 3 4 8
f 3 8 7
f 4 1 5
f 4 5 8
'''


class ScriptProvider:
    """Returns fixed local policies; never invokes a backend."""
    timeout = 60

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.prompts = []

    def complete(self, prompt, schema, call):
        self.prompts.append(prompt)
        return {'code': self.scripts[len(self.prompts)-1], 'summary': 'fixed local regression'}, {}


class TaskAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='full_task_adapter_')
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        (folder/'cube.obj').write_text(CUBE)
        parts = []
        for pid, position, fixed in [('2', [-.03, 0, .005], False),
                                     ('10', [0, 0, .005], False),
                                     ('3', [.03, 0, .005], False),
                                     ('base', [0, .04, .005], True)]:
            parts.append(dict(id=pid, position=position, quaternion=[1,0,0,0],
                visual_mesh='cube.obj', collision_meshes=['cube.obj'],
                local_bounds=[[-.005]*3,[.005]*3], mass_kg=.001,
                fixed=fixed, allowed_directions=['+z']))
        self.case = folder/'case.json'
        self.case.write_text(json.dumps(dict(id='local_task_regression', target_id='2', parts=parts)))

    def sim_api(self):
        sim = FullDisassemblySim(self.case, max_checks=40)
        api = SharedAPI(sim, max_checks=40)
        return sim, api

    def test_stage_focus_removal_is_not_goal_and_final_anchored_base_is_goal(self):
        sim, api = self.sim_api()
        original_case = copy.deepcopy(sim.case)
        self.assertEqual(api.snapshot()['target_id'], '2')
        self.assertTrue(api.remove('2', '+z')['committed'])
        self.assertFalse(sim.success)
        self.assertTrue(sim.target_removed)  # legacy diagnostic only
        obs = api.snapshot()
        self.assertEqual(obs['target_id'], '10')  # string order, not numeric order
        self.assertEqual(obs['completed_removals'], 1)
        self.assertEqual(obs['required_removals'], 3)
        self.assertFalse(obs['goal_reached'])
        self.assertEqual(sim.case, original_case)
        api.remove('10', '+z')
        self.assertFalse(sim.success)
        api.remove('3', '+z')
        self.assertEqual(sim.remaining, ['base'])
        self.assertTrue(sim.success)
        self.assertEqual(api.snapshot()['target_id'], None)
        self.assertEqual(api.snapshot()['goal_type'], 'full_disassembly')
        self.assertEqual(api.snapshot()['completed_removals'], 3)

    def test_unanchored_any_final_part_satisfies_n_minus_one(self):
        raw = json.loads(self.case.read_text())
        raw['parts'][-1]['fixed'] = False
        self.case.write_text(json.dumps(raw))
        sim, api = self.sim_api()
        for pid in ('10', '3', 'base'):
            self.assertTrue(api.remove(pid, '+z')['committed'])
        self.assertEqual(sim.remaining, ['2'])
        self.assertTrue(sim.success)
        self.assertFalse(sim.target_removed)

    def test_restore_recomputes_focus_without_cost_or_history_reset(self):
        sim, api = self.sim_api()
        root = api.checkpoint()
        original = physical_state_key(sim.export_state())
        api.remove('2', '+z')
        child = api.checkpoint()
        api.remove('10', '+z')
        self.assertEqual(api.snapshot()['target_id'], '3')
        checks, trace = sim.checks, copy.deepcopy(sim.trace)
        api.restore(child)
        self.assertEqual(api.snapshot()['target_id'], '10')
        api.restore(root)
        self.assertEqual(api.snapshot()['target_id'], '2')
        self.assertEqual(physical_state_key(sim.export_state()), original)
        self.assertEqual(sim.checks, checks)
        self.assertEqual(sim.trace, trace)
        self.assertFalse(sim.success)

    def test_same_frozen_bank_ledger_persists_across_focus_changes(self):
        sim, api = self.sim_api()
        api.checkpoint()
        bank = SkillBank(ROOT/'memory/S6.json')
        root_key = physical_state_key(sim.export_state())
        for expected in ('2', '10'):
            observation = api.snapshot()
            self.assertEqual(observation['target_id'], expected)
            proposal = bank.plan(observation, canonical_candidates(observation), sim.trace, api.checkpoints(), [])
            self.assertIsNone(proposal['error'])
            step = proposal['next_step']
            self.assertEqual(step['operation'], 'remove')
            self.assertEqual(step['action']['part_id'], expected)
            api.remove(**step['action'])
            api.checkpoint()
        observation = api.snapshot()
        self.assertEqual(observation['target_id'], '3')
        proposal = bank.plan(observation, canonical_candidates(observation), sim.trace, api.checkpoints(), [])
        self.assertIsNone(proposal['error'])
        memory = bank.export_state()
        self.assertIn(['2', '+z'], memory['attempted'][root_key])
        self.assertEqual(memory['history_cursor'], 2)
        self.assertGreaterEqual(len(memory['attempted']), 2)
        self.assertEqual(bank.sha256, SkillBank(ROOT/'memory/S6.json').sha256)

    def test_restricted_worker_continues_after_focus_and_stops_at_full_goal(self):
        first = runtime.run_code(self.case, "api.remove('2', '+z')", max_checks=40,
                                 max_steps=10000000, timeout_seconds=60)
        self.assertIsNone(first['error'])
        self.assertFalse(first['success'])
        self.assertTrue(first['initial_focus_removed'])
        self.assertEqual(first['observation']['target_id'], '10')
        self.assertEqual(first['checker_calls'], 1)
        final = runtime.run_code(self.case,
            "api.remove('10', '+z')\napi.remove('3', '+z')\napi.check('base', '+z')",
            state=first['state'], recovery_state=first['recovery_state'],
            max_checks=40, max_steps=10000000, timeout_seconds=60)
        self.assertIsNone(final['error'])
        self.assertTrue(final['success'])
        self.assertEqual(final['goal_type'], 'full_disassembly')
        self.assertEqual(final['halt_reason'], 'goal_reached')
        self.assertEqual(final['checker_calls'], 3)  # no post-goal fourth query
        self.assertEqual(final['state']['remaining'], ['base'])

    def test_generated_actors_take_second_turn_after_initial_focus(self):
        for library in (None, ROOT/'memory/S6.json'):
            provider = ScriptProvider(["api.remove('2', '+z')",
                                       "api.remove('10', '+z')\napi.remove('3', '+z')"])
            result = code_actor.solve_code(self.case, provider, library=library,
                max_checks=40, max_steps=10000000, timeout_seconds=60)
            self.assertTrue(result['success'], result.get('error'))
            self.assertEqual(result['llm_calls'], 2)
            self.assertEqual(result['state']['remaining'], ['base'])
            self.assertEqual(result['required_removals'], 3)
            self.assertFalse(result['goal_reached_after_deadline'])
            self.assertIn('"target_id": "10"', provider.prompts[1])

    def test_fixed_controller_also_finishes_full_sequence(self):
        result = controller.solve(self.case, None, SkillBank(ROOT/'memory/S6.json'),
            llm_rank=False, max_checks=40, max_steps=10000000, timeout_seconds=60)
        self.assertTrue(result['success'], result.get('error'))
        self.assertEqual(result['state']['remaining'], ['base'])
        self.assertEqual(result['checker_calls'], 3)
        self.assertEqual(result['goal_type'], 'full_disassembly')
        self.assertEqual(result['completed_removals'], result['required_removals'])

    def test_task_prompts_have_no_selective_completion_instruction(self):
        self.assertNotIn('immediately upon verified target removal', code_actor.SPEC)
        self.assertNotIn('immediately after verified target removal', code_actor.SPEC)
        self.assertNotIn('Optimize target recovery', controller.INSTRUCTIONS)
        self.assertIn('Removing that focus is NOT success', code_actor.SPEC)
        self.assertIn('full-sequence success', controller.INSTRUCTIONS)

    def test_old_development_witness_keeps_identical_physics_but_not_early_goal(self):
        """An old fixture is development evidence only, never a scored product."""
        index = ROOT.parent/'disassembly_abc_v4/outputs/input_audit/development_cases.json'
        entry = json.loads(index.read_text())['development'][0]
        selective = SelectiveSim(entry['case_path'], max_checks=40)
        full = FullDisassemblySim(entry['case_path'], max_checks=40)
        for action in entry['reference']['sequence']:
            before = selective.remove(**action)
            after = full.remove(**action)
            self.assertTrue(before['committed'])
            metadata = {'elapsed_seconds', 'path_mode', 'resolved_direction_world', 'extraction_collision'}
            self.assertEqual({k:v for k,v in before.items() if k not in metadata},
                             {k:v for k,v in after.items() if k not in metadata})
            self.assertEqual(physical_state_key(selective.export_state()),
                             physical_state_key(full.export_state()))
        self.assertTrue(selective.success)
        self.assertFalse(full.success)
        self.assertTrue(full.initial_focus_removed)
        self.assertGreater(full.snapshot()['remaining_part_count'], 1)


if __name__ == '__main__':
    unittest.main()

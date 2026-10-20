"""Synthetic tests for v7.3 changes: R7 recoverable responses, note recorded-sequence block, E1 equality, contract."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from disassembly_repair_v7.tests.fake_world import trap_world
from disassembly_repair_v7.offline.providers import FunctionProvider, read_then
from disassembly_repair_v7_3.common import V6, read, write

S0 = V6 / 'memory/S0.json'
S3 = V6 / 'memory/S3.json'
SOLVE = 'def run(api):\n    api.remove("a", "+z")\n    api.remove("b", "+z")\n    api.remove("t", "+x")\nrun(api)\n'


def execute(code, applied):
    return dict(operation='execute', skill_ids=[], code=code, ordered_actions=[], applied_skill_ids=list(applied),
                document_plan=[dict(skill_id=i, observed_trigger='t', procedure_step='s', intended_action_change='c') for i in applied],
                summary='x')


class ProviderError(RuntimeError):   # same class name as planner2d.llm.ProviderError (matched by name)
    pass


class RecoverableResponses(unittest.TestCase):
    def test_contract_violation_is_reasked_then_solved(self):
        from disassembly_repair_v7_3.actors import solve
        ids = [r['id'] for r in read(S3)['skills']]

        def later(prompt, call):
            if call == 2:
                return execute(SOLVE, ids[:1])          # omits one loaded document -> rejected, re-asked
            assert 'previous_response_rejected' in prompt
            return execute(SOLVE, ids)
        r = solve('fake', FunctionProvider(read_then(later, ids)), S3, 'code', sim_factory=lambda: trap_world())
        self.assertTrue(r['success'])
        self.assertEqual(r['llm_calls'], 3)              # read + rejected + re-ask, all counted
        self.assertEqual([x['reason'] for x in r['recoverable_rejections']], ['required physical procedure review was omitted'])

    def test_tool_use_rejection_is_reasked(self):
        from disassembly_repair_v7_3.actors import solve
        state = dict(n=0)

        class Flaky(FunctionProvider):
            def complete(self, prompt, schema, call_index):
                state['n'] += 1
                if state['n'] == 1:
                    raise ProviderError('Model used tools; response rejected to preserve the planner input boundary')
                return super().complete(prompt, schema, call_index)
        r = solve('fake', Flaky(lambda p, s, c: execute(SOLVE, [])), S0, 'code', sim_factory=lambda: trap_world())
        self.assertTrue(r['success'])
        self.assertEqual(r['llm_calls'], 2)
        self.assertTrue(r['recoverable_rejections'][0]['reason'].startswith('tool_use_rejected'))

    def test_reasks_are_bounded(self):
        from disassembly_repair_v7_3.actors import solve
        ids = [r['id'] for r in read(S3)['skills']]
        r = solve('fake', FunctionProvider(read_then(lambda p, c: execute(SOLVE, ids[:1]), ids)), S3, 'code',
                  sim_factory=lambda: trap_world())
        self.assertFalse(r['success'])
        self.assertEqual(len(r['recoverable_rejections']), 3)   # first answer + 2 re-asks
        self.assertEqual(r['llm_calls'], 4)
        self.assertEqual(r['termination'], 'execution_or_provider_error')

    def test_timeouts_stay_terminal(self):
        from disassembly_repair_v7_3.actors import solve

        class Slow(FunctionProvider):
            def complete(self, prompt, schema, call_index):
                raise ProviderError('LLM timeout after 120.0 seconds')
        r = solve('fake', Slow(lambda p, s, c: None), S0, 'code', sim_factory=lambda: trap_world())
        self.assertEqual(r['recoverable_rejections'], [])
        self.assertEqual(r['termination'], 'execution_or_provider_error')


class NoteBlock(unittest.TestCase):
    def _result(self, folder, name, success, actions, checks):
        vec = {'+x': [1., 0., 0.], '+z': [0., 0., 1.]}
        write(folder / name, dict(condition=name[0], success=success, actions=[dict(part_id=p, direction=d) for p, d in actions],
                                  trace=[{}] * checks, required_removals=3, initial_observation=dict(direction_vectors_world=vec)))
        return folder / name

    def test_success_with_fewest_checks_else_longest_partial(self):
        from disassembly_repair_v7_3.skill_writer import recorded_sequence
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a = self._result(d, 'A.json', True, [('a', '+z'), ('b', '+z'), ('t', '+x')], 40)
            b = self._result(d, 'B.json', True, [('a', '+z'), ('b', '+z'), ('t', '+x')], 12)
            c = self._result(d, 'C.json', False, [('a', '+z')], 5)
            block, best = recorded_sequence([a, b, c])
            self.assertEqual(best['condition'], 'B')
            self.assertIn('complete success', block)
            self.assertIn('1. part `a` direction `+z` (world [0.0, 0.0, 1.0])', block)
            block, best = recorded_sequence([c, self._result(d, 'X.json', False, [('a', '+z'), ('b', '+z')], 90)])
            self.assertEqual(best['condition'], 'X')
            self.assertIn('PARTIAL', block)


class FastGeometry(unittest.TestCase):
    def test_threaded_winding_matches_original(self):
        import trimesh
        from disassembly_repair_v7_3 import fast_geometry as fg
        mesh = trimesh.creation.icosphere(subdivisions=3)
        rng = np.random.default_rng(0)
        points = rng.uniform(-1.3, 1.3, size=(400, 3))
        self.assertTrue(np.array_equal(fg.ORIGINAL(mesh, points), fg.threaded_winding_inside(mesh, points)))
        self.assertTrue(np.array_equal(fg.original_winding_values(mesh, points), fg.winding_values(mesh, points)))
        self.assertEqual(len(fg.threaded_winding_inside(mesh, points[:0])), 0)


class Contract(unittest.TestCase):
    def test_v73_notes(self):
        from disassembly_repair_v7_3.contracts import COMMON, VERSION, LIMITS
        from disassembly_repair_v7_2.contracts import LIMITS as V72
        self.assertEqual(VERSION, 'v7.3')
        self.assertEqual(LIMITS, V72)
        for text in ('assembly-note-', 'direction_vectors_world', 'asks the same request'):
            self.assertIn(text, COMMON)


if __name__ == '__main__':
    unittest.main()

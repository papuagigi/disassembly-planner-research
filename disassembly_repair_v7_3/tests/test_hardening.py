"""Synthetic tests for v7.2 hardening (no model, no MuJoCo path sweeps)."""
import time
import unittest

from disassembly_repair_v7.tests.fake_world import trap_world, wide_world
from disassembly_repair_v7.offline.providers import FunctionProvider
from disassembly_repair_v7_3.common import V6
from disassembly_repair_v7_3.shared_api import HardenedAPI, DeadlineReached

S0 = V6 / 'memory/S0.json'


class RejectionCache(unittest.TestCase):
    def test_exact_repeat_is_uncharged_and_not_traced(self):
        sim = trap_world()
        api = HardenedAPI(sim)
        first = api.remove('b', '+x')
        self.assertFalse(first['valid'])
        self.assertEqual(sim.checks, 1)
        again = api.remove('b', '+x')
        self.assertTrue(again['cached'])
        self.assertEqual(again['reason'], first['reason'])
        self.assertEqual(sim.checks, 1)
        self.assertEqual(len(sim.trace), 1)
        self.assertEqual(len(api.export_recovery_state()['cached_rejections']), 1)

    def test_state_change_makes_a_new_query(self):
        sim = trap_world()
        api = HardenedAPI(sim)
        api.remove('b', '+z')                 # rejected: a still present
        api.remove('a', '+z')                 # accepted -> new state
        r = api.remove('b', '+z')             # new exact state -> real query
        self.assertNotIn('cached', r)
        self.assertEqual(sim.checks, 3)

    def test_accepted_actions_are_not_cached(self):
        sim = trap_world()
        api = HardenedAPI(sim)
        root = api.checkpoint()
        self.assertTrue(api.remove('t', '+x')['valid'])
        api.restore(root)
        again = api.remove('t', '+x')          # same exact state, previously ACCEPTED: real (charged) query
        self.assertTrue(again['valid'])
        self.assertNotIn('cached', again)
        self.assertEqual(sim.checks, 2)
        self.assertEqual(api.export_recovery_state().get('cached_rejections', []), [])


class Deadline(unittest.TestCase):
    def test_api_raises_after_deadline_without_charge(self):
        sim = trap_world()
        api = HardenedAPI(sim)
        api.deadline = time.monotonic() - 1
        with self.assertRaises(DeadlineReached):
            api.remove('a', '+z')
        self.assertEqual(sim.checks, 0)
        self.assertEqual(len(api.export_recovery_state()['deadline_stops']), 1)

    def test_runtime_stops_policy_at_api_deadline(self):
        from disassembly_repair_v7_3 import runtime
        runtime.guards.memory_check = lambda: None
        sim = wide_world(max_checks=10**6)
        sim.rule = lambda remaining, pid, d: (False, 'path_collision', ['base'])
        code = 'def run(api):\n    while True:\n        for p in api.snapshot()["remaining_parts"]:\n            api.remove(p["id"], "+x")\nrun(api)\n'
        t = time.monotonic()
        payload = dict(code=code, max_checks=10**6, max_steps=10**12, timeout_seconds=600., recovery_state=None,
                       max_checkpoints=128, max_restores=256, deadline_monotonic=time.monotonic() + 1.0)
        r = runtime.execute_payload(payload, sim, callback=lambda e: None)
        self.assertLess(time.monotonic() - t, 5)
        self.assertEqual(r['error']['type'], 'WallTimeLimit')


class Contract(unittest.TestCase):
    def test_limits_and_prompt(self):
        from disassembly_repair_v7_3.contracts import LIMITS, COMMON
        from disassembly_repair_v7.contracts import LIMITS as V7
        self.assertEqual(LIMITS['max_rss_bytes'], 8 * 1024 ** 3)
        self.assertEqual({k: v for k, v in LIMITS.items() if k != 'max_rss_bytes'},
                         {k: v for k, v in V7.items() if k != 'max_rss_bytes'})
        self.assertIn('Exact-state rejection cache', COMMON)

    def test_actor_code_arm_runs_with_cache(self):
        from disassembly_repair_v7_3.actors import solve
        # A program that keeps re-trying one rejected action: after the first check every repeat is cached,
        # so the turn makes no new progress and the v7 no-progress rule ends the episode after two such turns.
        code = 'def run(api):\n    for i in range(5):\n        api.remove("t", "+y")\nrun(api)\n'
        provider = FunctionProvider(lambda p, s, c: dict(operation='execute', skill_ids=[], code=code, ordered_actions=[],
                                                         applied_skill_ids=[], document_plan=[], summary='x'))
        r = solve('fake', provider, S0, 'code', sim_factory=lambda: trap_world())
        self.assertEqual(r['checker_calls'], 1)
        self.assertEqual(r['termination'], 'no_progress_stop')
        self.assertEqual(len(r['recovery_state']['cached_rejections']), 4 + 5 + 5)


if __name__ == '__main__':
    unittest.main()


class C72Scheduler(unittest.TestCase):
    def test_rank_when_stuck_not_on_first_visit(self):
        import json
        from disassembly_repair_v7_3.actors import solve
        from disassembly_repair_v7.offline.providers import read_then
        from disassembly_repair_v7_3.common import read
        S3 = V6 / 'memory/S3.json'
        ids = [r['id'] for r in read(S3)['skills']]

        def rank(prompt, call):
            cands = json.loads(prompt.split('\nPUBLIC INPUT:\n', 1)[1])['architecture_context']['candidate_actions']
            return dict(operation='execute', skill_ids=[], code='', ordered_actions=list(reversed(cands)), applied_skill_ids=ids,
                        document_plan=[dict(skill_id=i, observed_trigger='t', procedure_step='s', intended_action_change='c') for i in ids],
                        summary='r')
        r = solve('fake', FunctionProvider(read_then(rank, ids)), S3, 'graph_dfs', limits=dict(max_checks=120),
                  sim_factory=lambda: wide_world(max_checks=120))
        reasons = [d['call_reason'] for d in r['decisions']]
        self.assertEqual(reasons[:2], ['document_read_phase', 'first_ranking'])
        self.assertNotIn('first_visit_of_exact_state', reasons)
        self.assertTrue(r['success'])
        self.assertLess(r['llm_calls'], 8)   # easy descent: inherited orders, no call per new state


LOOP_CODE = 'def run(api):\n    while True:\n        api.remove("b", "+x")\nrun(api)\n'   # never excludes its own rejection


class CachedRepeatLoop(unittest.TestCase):
    def test_api_stops_after_limit_without_charge(self):
        from disassembly_repair_v7_3.shared_api import RepeatedRejectionLoop
        sim = trap_world()
        api = HardenedAPI(sim)
        api.remove('b', '+x')                       # charged rejection
        for _ in range(64):
            self.assertTrue(api.remove('b', '+x')['cached'])
        with self.assertRaises(RepeatedRejectionLoop):
            api.remove('b', '+x')
        self.assertEqual(sim.checks, 1)
        rec = api.export_recovery_state()
        self.assertEqual(len(rec['cached_rejections']), 64)
        self.assertEqual(rec['repeat_loop_stops'][0]['consecutive_cached'], 64)

    def test_streak_resets_on_a_charged_query_and_can_be_disabled(self):
        sim = trap_world()
        api = HardenedAPI(sim)
        api.remove('b', '+x')
        for _ in range(60):
            api.remove('b', '+x')
        api.remove('b', '+z')                       # new charged query resets the streak
        for _ in range(60):
            api.remove('b', '+x')
        api.cached_streak_limit = None
        for _ in range(200):
            api.remove('b', '+x')
        self.assertEqual(sim.checks, 2)

    def test_runtime_turn_ends_with_loop_error_not_instruction_budget(self):
        from disassembly_repair_v7_3 import runtime
        runtime.guards.memory_check = lambda: None
        sim = trap_world()
        payload = dict(code=LOOP_CODE, max_checks=240, max_steps=10**7, timeout_seconds=600., recovery_state=None,
                       max_checkpoints=128, max_restores=256, deadline_monotonic=time.monotonic() + 600)
        r = runtime.execute_payload(payload, sim, callback=lambda e: None)
        self.assertEqual(r['error']['type'], 'RepeatedRejectionLoop')
        self.assertEqual(sim.checks, 1)
        self.assertLess(r['steps'], 10**6)

    def test_actor_continues_to_next_turn_after_loop_stop(self):
        from disassembly_repair_v7_3.actors import solve
        provider = FunctionProvider(lambda p, s, c: dict(operation='execute', skill_ids=[], code=LOOP_CODE, ordered_actions=[],
                                                         applied_skill_ids=[], document_plan=[], summary='x'))
        r = solve('fake', provider, S0, 'code', sim_factory=lambda: trap_world())
        errors = [d.get('execution_error', {}).get('type') for d in r['decisions'] if d.get('execution_error')]
        self.assertEqual(errors, ['RepeatedRejectionLoop'] * 3)   # turn 1 (1 check), turns 2-3 without progress
        self.assertEqual(r['termination'], 'no_progress_stop')
        self.assertEqual(r['checker_calls'], 1)
        self.assertIn('RepeatedRejectionLoop', str(r['turn_progress']))   # the next prompt's turn_progress_feedback

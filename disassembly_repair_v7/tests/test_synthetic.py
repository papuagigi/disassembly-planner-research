"""Fast synthetic tests (no model, no MuJoCo path sweeps).

The A program used here is the preserved v6 A/05954 generated code, unchanged.
"""
import json
import unittest

from disassembly_repair_v7.common import V6, read, v6_trial
from disassembly_repair_v7.tests.fake_world import trap_world, wide_world
from disassembly_repair_v7.offline.providers import FunctionProvider, read_then

S0 = V6 / 'memory/S0.json'
S3 = V6 / 'memory/S3.json'


def a_code():
    return read(v6_trial('asap_05954', 'A'))['decisions'][0]['response']['code']


def run_v6_runtime(sim, code, max_checks):
    from disassembly_real_v3 import runtime as old
    old.memory_check = lambda: None
    old.guards.memory_check = lambda: None
    payload = dict(code=code, exports=[], library_bank=None, max_checks=max_checks, max_steps=10_000_000,
                   timeout_seconds=60., recovery_state=None, max_checkpoints=128, max_restores=256)
    return old.execute_payload(payload, sim, callback=lambda e: None)


def run_v7_runtime(sim, code, max_checks):
    from disassembly_repair_v7 import runtime
    runtime.guards.memory_check = lambda: None
    payload = dict(code=code, max_checks=max_checks, max_steps=10_000_000, timeout_seconds=60.,
                   recovery_state=None, max_checkpoints=128, max_restores=256)
    return runtime.execute_payload(payload, sim, callback=lambda e: None)


def reentries(trace):
    seen, n = set(), 0
    for t in trace:
        if t.get('committed'):
            key = (t['physical_state_key_before'], t['part_id'], t['direction'])
            n += key in seen
            seen.add(key)
    return n


class ReentryGuard(unittest.TestCase):
    def test_v6_reproduces_reentry_loop_with_preserved_a_code(self):
        sim = trap_world(max_checks=60)
        result = run_v6_runtime(sim, a_code(), 60)
        self.assertFalse(result['success'])
        self.assertEqual(result['error']['type'], 'BudgetLimit')
        self.assertGreater(reentries(sim.trace), 10)  # accepted dead-end edge re-entered repeatedly

    def test_v7_guard_stops_reentry_and_same_code_finishes(self):
        sim = trap_world(max_checks=60)
        result = run_v7_runtime(sim, a_code(), 60)
        self.assertTrue(result['success'], result['error'])
        self.assertEqual(reentries(sim.trace), 0)
        guarded = result['recovery_state'].get('guarded_requests', [])
        self.assertGreaterEqual(len(guarded), 1)
        # Guarded requests are not physics checks and never enter the trace.
        self.assertTrue(all(t.get('reason') != 'known_dead_end_child' for t in sim.trace))
        self.assertEqual(sim.checks, len(sim.trace))

    def test_ledger_marks_recursive_dead_end_and_auto_checkpoints(self):
        from disassembly_repair_v7.shared_api import LedgerAPI
        sim = trap_world()
        api = LedgerAPI(sim)
        root = api.snapshot()['state_key']
        api.remove('t', '+x')
        mid = api.snapshot()['state_key']
        for d in ('+x', '-x', '+y', '-y', '+z', '-z'):
            api.remove('b', d)
        api.remove('a', '+z')
        leaf = api.snapshot()
        for d in ('+x', '-x', '+y', '-y', '+z', '-z'):
            api.remove('b', d)
        led = api.snapshot()['search_ledger']
        rows = {r['state_key']: r for r in led['states']}
        self.assertTrue(rows[leaf['state_key']]['known_dead_end'])
        self.assertFalse(rows[mid]['known_dead_end'])  # a's other directions untested
        self.assertEqual(len(api.checkpoints()), 2)   # one per committed state
        handle = [c['handle'] for c in api.checkpoints() if c['state_key'] == mid][0]
        api.restore(handle)
        g = api.remove('a', '+z')
        self.assertEqual(g['reason'], 'known_dead_end_child')
        self.assertEqual(sim.checks, 14)               # 1 + 6 + 1 + 6, guard uncharged
        for d in ('+x', '-x', '+y', '-y', '-z'):
            api.remove('a', d)
        rows = {r['state_key']: r for r in api.snapshot()['search_ledger']['states']}
        self.assertTrue(rows[mid]['known_dead_end'])
        self.assertFalse(rows[root]['known_dead_end'])
        resumable = api.snapshot()['search_ledger']['resumable_checkpoints']
        self.assertEqual([r['state_key'] for r in resumable], [])  # root has no checkpoint in this bare test
        self.assertEqual(api.checkpoint(), api.checkpoint())       # exact-state checkpoint reuse


def first_listed_order(prompt):
    payload = json.loads(prompt.split('\nPUBLIC INPUT:\n', 1)[1])
    return payload


class NoProgressRule(unittest.TestCase):
    def test_code_arm_stops_after_two_zero_check_turns(self):
        from disassembly_repair_v7.actors import solve
        idle = 'def run(api):\n    s = api.snapshot()\n    return\nrun(api)\n'

        def execute(prompt, call):
            return dict(operation='execute', skill_ids=[], code=idle, ordered_actions=[], applied_skill_ids=[],
                        document_plan=[], summary='idle')
        provider = FunctionProvider(lambda p, s, c: execute(p, c))
        result = solve('fake', provider, S0, 'code', sim_factory=lambda: trap_world())
        self.assertEqual(result['termination'], 'no_progress_stop')
        self.assertEqual(result['llm_calls'], 2)
        payload = first_listed_order(provider.prompts[1])
        self.assertEqual(payload['consecutive_execute_turns_without_progress'], 1)
        self.assertFalse(payload['turn_progress_feedback'][0]['progress'])

    def test_progress_resets_streak(self):
        from disassembly_repair_v7.actors import solve
        step = 'def run(api):\n    s = api.snapshot()\n    for p in s["remaining_parts"]:\n        if not p["fixed"]:\n            api.remove(p["id"], "+y")\n            return\nrun(api)\n'
        provider = FunctionProvider(lambda p, s, c: dict(operation='execute', skill_ids=[], code=step,
                                                         ordered_actions=[], applied_skill_ids=[], document_plan=[], summary='s'))
        result = solve('fake', provider, S0, 'code', sim_factory=lambda: trap_world())
        self.assertEqual(result['termination'], 'call_budget_exhausted')
        self.assertEqual(result['llm_calls'], 8)
        self.assertTrue(all(r['progress'] for r in result['turn_progress']))


class CScheduler(unittest.TestCase):
    def test_paced_windows_and_per_state_orders(self):
        from disassembly_repair_v7.actors import solve
        bank = read(S3)
        ids = [r['id'] for r in bank['skills']]

        def rank(prompt, call):
            payload = first_listed_order(prompt)
            cands = payload['architecture_context']['candidate_actions']
            # A deliberately unhelpful but stable order: reverse canonical.
            return dict(operation='execute', skill_ids=[], code='', ordered_actions=list(reversed(cands)),
                        applied_skill_ids=ids, document_plan=[dict(skill_id=i, observed_trigger='t', procedure_step='s',
                                                                   intended_action_change='c') for i in ids], summary='r')
        provider = FunctionProvider(read_then(rank, ids))
        result = solve('fake', provider, S3, 'graph_dfs', limits=dict(max_checks=120),
                       sim_factory=lambda: wide_world(max_checks=120))
        reasons = [d['call_reason'] for d in result['decisions']]
        self.assertEqual(reasons[0], 'document_read_phase')
        self.assertEqual(reasons[1], 'first_visit_of_exact_state')
        hist = result['rank_history']
        # Same-state re-rank happens only after the committed window was fully tried.
        root = hist[0]['state_key']
        root_rows = [h for h in hist if h['state_key'] == root]
        self.assertEqual(root_rows[0]['committed_window'], 18)   # ceil(120/(6+1))
        checks_at = [d['checks_before'] for d in result['decisions'] if d.get('rank_audit', {}).get('state_key') == root]
        gaps = [b - a for a, b in zip(checks_at, checks_at[1:])]
        self.assertTrue(all(g >= 18 for g in gaps[:1]), gaps)
        self.assertTrue(result['success'], result['termination'])

    def test_v6_policy_would_rerank_every_six(self):
        # Documentation test of the preserved v6 rule (no execution of v6 actors).
        src = (V6 / 'actors.py').read_text()
        self.assertIn('dfs.failures_since_rank>=6', src)


if __name__ == '__main__':
    unittest.main()


class PromptView(unittest.TestCase):
    def test_prompt_view_drops_bulk_only_in_copy(self):
        from disassembly_repair_v7.actors import prompt_view, context_view
        r = read(v6_trial('asap_06444', 'C'))
        obs = dict(current_state_feedback=r['trace'][:5], history_feedback=[dict(part_id='1', remaining_before=['a'], remaining_after=['a'])],
                   recovery=dict(checkpoints=[dict(handle='h', state_key='k', removed_count=0, support_edges=[1, 2], remaining_parts=['a'])]))
        view = prompt_view(obs)
        self.assertNotIn('collision_policy', view['current_state_feedback'][0])
        self.assertIn('collision_policy', obs['current_state_feedback'][0])  # original untouched
        self.assertEqual(set(view['recovery']['checkpoints'][0]), {'handle', 'state_key', 'removed_count'})
        self.assertNotIn('remaining_before', view['history_feedback'][0])
        ctx = context_view(dict(directed_graph=dict(edges=[{'from': 'a', 'to': 'b', 'direction': '+x', 'state_key': 'k', 'semantics': 's'}])))
        self.assertEqual(ctx['directed_graph']['edges'][0], {'from': 'a', 'to': 'b', 'direction': '+x'})

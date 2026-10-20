"""C controller v7: the v6 fixed graph/DFS with per-state orders and paced re-ranking.

Unchanged from v6 (disassembly_final_v6/controller.py, imported, not edited):
exact-state conditional blocking graph, unknown actions stay candidates, a
child is entered after an accepted removal, the parent is restored only after
the child frontier is exhausted, and the LLM order decides which untried
candidate is removed next.

Changed scheduling/bookkeeping (v6 evidence: C/06444 re-ranked every 6
failures, moved an untested action 11th->55th, and spent all 8 calls by
check 36; the single global order was also reused across parent/child):
  * order memory is per exact state; a new state inherits the nearest
    ancestor's order until it receives its own ranking;
  * a ranking call is requested on the first visit of an exact state, or at a
    state whose committed window is exhausted, or after a new instability
    there. A restore back to a ranked state reuses that state's order;
  * committed window W = max(6, ceil(remaining_checks / (remaining_calls+1)))
    at ranking time: the top-W untried actions of an order are all tried
    before that state is re-ranked (pacing the 8-call cap over 240 checks).
"""
from __future__ import annotations
import math

from disassembly_final_v6.controller import DFS as V6DFS
from disassembly_hybrid.graph import action_key, physical_state_key

MIN_WINDOW = 6


class DFS7(V6DFS):
    def __init__(self):
        super().__init__()
        self.orders = {}          # state key -> effective order (list of action dicts)
        self.windows = {}         # state key -> committed window length
        self.fails_since = {}     # state key -> rejected attempts since its last ranking
        self.unstable_since = {}  # state key -> instability observed since its last ranking
        self.rank_history = []    # audit rows

    def current_key(self):
        return self.stack[-1]['key'] if self.stack else None

    def inherited_order(self, key):
        if key in self.orders:
            return self.orders[key], key
        for node in reversed(self.stack):
            if node['key'] in self.orders:
                return self.orders[node['key']], node['key']
        return [], None

    def ranking_reason(self, key):
        if key not in self.orders:
            return 'first_visit_of_exact_state'
        if self.unstable_since.get(key):
            return 'new_instability_at_state'
        if self.fails_since.get(key, 0) >= self.windows.get(key, MIN_WINDOW):
            return 'committed_window_exhausted'
        return None

    @staticmethod
    def window(checks_remaining, calls_remaining_after):
        if calls_remaining_after <= 0:
            return max(MIN_WINDOW, checks_remaining)
        return max(MIN_WINDOW, math.ceil(checks_remaining / (calls_remaining_after + 1)))

    def set_state_order(self, key, proposed, candidates, window, call, reason):
        allowed = {action_key(a): a for a in candidates}
        seen, ordered, dropped = set(), [], 0
        for a in proposed:
            if not isinstance(a, dict) or set(a) != {'part_id', 'direction'}:
                dropped += 1
                continue
            k = action_key(a)
            if k in allowed and k not in seen:
                ordered.append(dict(a))
                seen.add(k)
            else:
                dropped += 1
        listed = len(ordered)
        previous, source = self.inherited_order(key)
        effective = ordered + [dict(a) for a in candidates if action_key(a) not in seen]
        self.orders[key] = effective
        self.windows[key] = window
        self.fails_since[key] = 0
        self.unstable_since[key] = False
        self.order = effective  # keep the v6 attribute meaningful for context/debugging
        self.failures_since_rank = 0
        prev_pos = {action_key(a): i for i, a in enumerate(a for a in previous if action_key(a) in allowed)}
        shifts = [i - prev_pos[action_key(a)] for i, a in enumerate(effective) if action_key(a) in prev_pos]
        row = dict(call=call, reason=reason, state_key=key, candidates=len(candidates),
                   model_listed_valid=listed, dropped_entries=dropped, committed_window=window,
                   previous_order_source=('same_state' if source == key else ('ancestor' if source else 'none')),
                   effective_order=[[a['part_id'], a['direction']] for a in effective],
                   mean_abs_position_change=(sum(abs(s) for s in shifts) / len(shifts)) if shifts else None,
                   max_position_increase=max(shifts) if shifts else None)
        self.rank_history.append(row)
        return row

    def step(self, sim, api):
        f = self.frame(sim, api)
        candidates = self.candidates(sim, api)
        if not candidates:
            self.exhausted.add(f['key'])
            self.stack.pop()
            if not self.stack:
                return 'exhausted'
            api.restore(self.stack[-1]['handle'])
            self.epoch += 1
            return 'restored'
        order, _ = self.inherited_order(f['key'])
        ranks = {action_key(a): i for i, a in enumerate(order)}
        action = min(candidates, key=lambda a: ranks.get(action_key(a), len(ranks)))
        pair = action_key(action)
        f['attempted'].add(pair)
        result = api.remove(action['part_id'], action['direction'])
        self.graph.add(f['key'], result)
        if result['valid']:
            f['children'][pair] = physical_state_key(sim.export_state())
            if not sim.success:
                self.frame(sim, api)
            return 'descended'
        self.failures_since_rank += 1
        self.fails_since[f['key']] = self.fails_since.get(f['key'], 0) + 1
        if result.get('reason') == 'unstable_remainder':
            self.unstable_since[f['key']] = True
        return 'rejected'

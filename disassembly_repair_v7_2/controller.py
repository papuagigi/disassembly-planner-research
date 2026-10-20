"""C7.2 scheduler (C-specific architecture change, recorded): rank when stuck, not on every first visit.

v7.1 evidence: C spent all 8 calls on the first visits of the first 8 states when descent
was easy (06146 by check 14, 03012 by 53, 05902 by 36), so later states that actually got
stuck had no model guidance. C7.2 keeps every v7 DFS7 rule except WHEN a new state asks:
  * the very first ranking (no ranked ancestor yet) is requested immediately;
  * a state without its own ranking inherits its nearest ranked ancestor's order and asks
    only after STUCK_FAILURES rejections there ('stuck_on_inherited_order');
  * a state with its own order re-ranks after its committed window W (unchanged) or after
    a new instability there (unchanged).
The LLM still only ranks; the host DFS, graph, restore and candidate rules are unchanged.
"""
from __future__ import annotations

from disassembly_repair_v7.controller import DFS7, MIN_WINDOW

STUCK_FAILURES = 3


class DFS72(DFS7):
    def ranking_reason(self, key):
        if not self.orders:
            return 'first_ranking'
        if self.unstable_since.get(key):
            return 'new_instability_at_state'
        fails = self.fails_since.get(key, 0)
        if key not in self.orders:
            return 'stuck_on_inherited_order' if fails >= STUCK_FAILURES else None
        if fails >= self.windows.get(key, MIN_WINDOW):
            return 'committed_window_exhausted'
        return None

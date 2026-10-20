"""v7 common API: exact-state search ledger, dead-end re-entry guard, state checkpoints.

Identical for A, B and C. These are bookkeeping primitives derived only from
the episode's own recorded physics results (sim.trace) and public part data.
They choose no action, keep no frontier order and never restore by themselves.

1. search_ledger (in every snapshot): for each exact physical state seen in the
   trace, the canonical candidate actions, which were rejected, which were
   accepted into which child state, and whether the state is a KNOWN DEAD END:
   every candidate was rejected there or was accepted into a known dead end.
   Physics is deterministic given the exact state key (v6 A/05954 re-entered
   the same edge 59 times and always reached the same child key), so a known
   dead end cannot yield a different result on re-entry.
2. Dead-end re-entry guard: check/remove of an action already accepted at this
   exact state into a known-dead-end child returns valid=False,
   reason='known_dead_end_child' WITHOUT physics. It is not charged to the
   240 physics-check budget and is recorded in recovery_state['guarded_requests'].
3. State checkpoints: after every committed removal the host stores one
   checkpoint for the new exact state if none exists (same 128 cap; skipped,
   and recorded, when the cap is reached). checkpoint() on an exact state that
   already has a checkpoint returns that handle instead of using another slot.
   Restoring remains the planner's decision.
"""
from __future__ import annotations

import copy

from disassembly_learning_v3.shared_api import SharedAPI as V3SharedAPI
from disassembly_recovery.shared_api import physical_state_key

DIRECTIONS = ('+x', '-x', '+y', '-y', '+z', '-z')
GUARD_REASON = 'known_dead_end_child'
LEDGER_SEMANTICS = (
    'Facts from this episode only. known_dead_end=true means every candidate action at that exact state '
    'was rejected there or was accepted into a known dead end; physics is deterministic for an exact state key. '
    'untested_action_count counts candidate actions never tried at that exact state. '
    'resumable_checkpoints lists saved states that are not known dead ends. No action order is implied.')


def _candidates(parts, remaining):
    return {(pid, d) for pid in remaining if not parts[pid].get('fixed', False)
            for d in parts[pid].get('allowed_directions', DIRECTIONS) if d in DIRECTIONS}


class SearchLedger:
    """Derived from (trace, parts). Rebuilt on demand; holds no hidden state."""

    def __init__(self, parts, trace, total_parts):
        self.parts = parts
        self.total = total_parts
        self.states = {}
        for t in trace:
            before = t.get('physical_state_key_before')
            if before is None or t.get('remaining_before') is None:
                continue
            s = self._state(before, t['remaining_before'])
            action = (t.get('part_id'), t.get('direction'))
            if action not in s['candidates']:
                continue  # malformed/fixed/unknown requests are not physical evidence
            if t.get('valid'):
                if t.get('committed') and t.get('physical_state_key_after'):
                    s['accepted'][action] = t['physical_state_key_after']
                    self._state(t['physical_state_key_after'], t['remaining_after'])
                else:
                    s['valid_uncommitted'].add(action)
            else:
                s['rejected'][action] = t.get('reason')
        self._dead = {}

    def _state(self, key, remaining):
        if key not in self.states:
            remaining = list(remaining)
            self.states[key] = dict(remaining=remaining, candidates=_candidates(self.parts, remaining),
                                    rejected={}, accepted={}, valid_uncommitted=set())
        return self.states[key]

    def tested(self, key):
        s = self.states.get(key)
        if s is None:
            return set()
        return set(s['rejected']) | set(s['accepted']) | s['valid_uncommitted']

    def dead_end(self, key):
        if key in self._dead:
            return self._dead[key]
        s = self.states.get(key)
        if s is None or len(s['remaining']) <= 1:
            self._dead[key] = False
            return False
        # Removals shrink the remaining set, so accepted edges form a DAG.
        value = all(a in s['rejected'] or (a in s['accepted'] and self.dead_end(s['accepted'][a]))
                    for a in s['candidates'])
        self._dead[key] = value
        return value

    def accepted_child(self, key, part_id, direction):
        s = self.states.get(key)
        return None if s is None else s['accepted'].get((part_id, direction))

    def describe(self, current_key, current_remaining, checkpoints):
        if current_key not in self.states:
            self._state(current_key, current_remaining)
        handles = {}
        for cp in checkpoints:
            handles.setdefault(cp['state_key'], []).append(cp['handle'])

        def row(key):
            s = self.states[key]
            untested = len(s['candidates'] - self.tested(key))
            return dict(state_key=key, removed_count=self.total - len(s['remaining']),
                        candidate_action_count=len(s['candidates']), untested_action_count=untested,
                        rejected_action_count=len(s['rejected']), accepted_edge_count=len(s['accepted']),
                        known_dead_end=self.dead_end(key), checkpoint_handles=handles.get(key, []))

        s = self.states[current_key]
        current = row(current_key)
        current['accepted_edges'] = [
            dict(part_id=p, direction=d, child_state_key=child,
                 child_removed_count=self.total - len(self.states[child]['remaining']),
                 child_known_dead_end=self.dead_end(child))
            for (p, d), child in sorted(s['accepted'].items())]
        rows = sorted((row(k) for k in self.states), key=lambda r: (-r['removed_count'], r['state_key']))
        resumable = [dict(handle=h, state_key=r['state_key'], removed_count=r['removed_count'],
                          untested_action_count=r['untested_action_count'])
                     for r in rows if not r['known_dead_end'] for h in r['checkpoint_handles']]
        return dict(semantics=LEDGER_SEMANTICS, current=current, states=rows,
                    resumable_checkpoints=resumable,
                    known_dead_end_state_count=sum(r['known_dead_end'] for r in rows))


class LedgerAPI(V3SharedAPI):
    """v3 API plus the three v7 primitives above. Same budgets and restore semantics."""

    def _ledger(self):
        return SearchLedger(self._sim.parts, self._sim.trace, len(self._sim.parts))

    def snapshot(self):
        value = super().snapshot()
        key = physical_state_key(self._sim.export_state())
        value['search_ledger'] = self._ledger().describe(key, list(self._sim.remaining), self.checkpoints())
        value['search_ledger']['guarded_request_count'] = len(self._recovery.get('guarded_requests', []))
        return value

    observe = snapshot

    def _existing_handle(self, key):
        for handle, cp in self._recovery['checkpoints'].items():
            if cp['metadata']['state_key'] == key:
                return handle
        return None

    def checkpoint(self):
        key = physical_state_key(self._sim.export_state())
        existing = self._existing_handle(key)
        if existing is None:
            return super().checkpoint()
        event = self._begin('checkpoint')
        self._finish(event, handle=existing, valid=True, reused_existing_exact_state_checkpoint=True)
        return existing

    def _operation(self, kind, part_id, direction):
        key = physical_state_key(self._sim.export_state())
        ledger = self._ledger()
        child = ledger.accepted_child(key, part_id, direction)
        if child is not None and ledger.dead_end(child):
            event = self._begin(kind, part_id=part_id, direction=direction, guard=GUARD_REASON)
            result = dict(valid=False, committed=False, reason=GUARD_REASON, part_id=part_id,
                          direction=direction, blockers=[], stability=None, checker_call=None,
                          charged_physics_check=False, child_state_key=child,
                          physical_state_key_before=key, physical_state_key_after=key,
                          api_event_index=event['event_index'],
                          scope='Recorded accepted edge into a known dead end at this exact state; no physics run, no check charged.')
            self._recovery.setdefault('guarded_requests', []).append(dict(
                event_index=event['event_index'], kind=kind, part_id=part_id, direction=direction,
                state_key=key, child_state_key=child, checks_at_request=self._sim.checks))
            self._finish(event, valid=False, committed=False, reason=GUARD_REASON, checker_call=None,
                         charged_physics_check=False)
            return copy.deepcopy(result)
        trace_length = len(self._sim.trace)
        try:
            return super()._operation(kind, part_id, direction)
        finally:
            # Only a record appended by THIS operation can trigger the state checkpoint
            # (also when the goal exception is propagating after a committed removal).
            if kind == 'remove' and len(self._sim.trace) > trace_length and self._sim.trace[-1].get('committed'):
                self._auto_checkpoint()

    def _auto_checkpoint(self):
        key = physical_state_key(self._sim.export_state())
        log = self._recovery.setdefault('auto_checkpoints', [])
        if self._existing_handle(key) is not None:
            return
        if len(self._recovery['checkpoints']) >= self._max_checkpoints:
            log.append(dict(state_key=key, created=False, reason='checkpoint_cap_reached', checks=self._sim.checks))
            return
        handle = self.checkpoint()  # subclasses (runtime facade) still emit their progress events
        log.append(dict(state_key=key, created=True, handle=handle, checks=self._sim.checks))

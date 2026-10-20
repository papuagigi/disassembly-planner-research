"""v7.2 common API = v7 LedgerAPI + two engine hardenings (identical for A, B and C).

H1. Episode deadline inside the API. Before any check/remove (including guarded
    or cached answers) the API raises the configured deadline exception once
    the episode deadline has passed. v7.1 05902/B kept issuing 7 checks for 18 s
    after its 900 s budget; this makes the stop deterministic at the next query.
H2. Exact-state rejection cache. A check/remove of an action already REJECTED
    for a physical reason (path_collision, unstable_remainder) at this exact
    state returns that recorded rejection without physics and without charging
    a check. Physics is deterministic per exact state key, so a repeat cannot
    give new information. v7.1 06146/B repeated 51 and 05902/B 24 such checks.
Accepted actions are never cached here (v7's dead-end guard still applies).
H6. Cached-repeat loop stop (added after validation, before the retry freeze). Validation
    asap_02402/B_r2 re-requested one cached rejection 2,992 times: its program counted
    rejections from current_state_feedback, which records only charged checks, so its
    "defer after 3 rejections" rule never fired and the episode burned the 10M instruction
    budget with 2 checks. After more consecutive cached answers than 12 x part count
    (min 64; i.e. more than every action at a state twice) the API raises
    RepeatedRejectionLoop. Generated code cannot catch it (BaseException, like the other
    guards); it ends the current code turn only, and the error text reaches the next turn.
    No physics, no check, no event. Replays disable it (they re-issue events across turns).
"""
from __future__ import annotations

import copy
import time

from disassembly_recovery.shared_api import physical_state_key
from disassembly_repair_v7.shared_api import LedgerAPI, SearchLedger  # noqa: F401

CACHE_REASON_TAG = 'cached_exact_state_rejection'
CACHEABLE = ('path_collision', 'unstable_remainder')


CACHED_STREAK_FLOOR = 64


class DeadlineReached(RuntimeError):
    pass


class RepeatedRejectionLoop(BaseException):
    """H6: not catchable by generated code (the runtime guards are BaseException subclasses too)."""


class HardenedAPI(LedgerAPI):
    deadline = None                      # time.monotonic() value; None = no deadline
    deadline_exception = DeadlineReached
    cached_streak_limit = 'auto'         # H6: 'auto' = max(64, 12 x part count); None disables (replay)
    _cached_streak = 0

    def _check_cached_streak(self, kind, part_id, direction, key):
        limit = self.cached_streak_limit
        if limit == 'auto':
            limit = max(CACHED_STREAK_FLOOR, 12 * len(self._sim.parts))
        self._cached_streak += 1
        if limit is not None and self._cached_streak > limit:
            self._recovery.setdefault('repeat_loop_stops', []).append(dict(
                kind=kind, part_id=part_id, direction=direction, state_key=key, consecutive_cached=self._cached_streak - 1,
                checks=self._sim.checks))
            raise RepeatedRejectionLoop(
                f'{self._cached_streak - 1} consecutive requests repeated rejections already recorded at their exact states '
                f'(no new physics; last: {part_id} {direction}). This code turn was stopped. Before choosing, exclude every '
                '(part_id, direction) already rejected at the current state: each one appears once in current_state_feedback; '
                'cached repeats are not added there, so counting rows never grows for a repeated action.')

    def _check_deadline(self, kind, part_id, direction):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self._recovery.setdefault('deadline_stops', []).append(dict(
                kind=kind, part_id=part_id, direction=direction, checks=self._sim.checks,
                late_seconds=time.monotonic() - self.deadline))
            raise self.deadline_exception('whole_episode_wall_deadline (checked inside the common API)')

    def _recorded_rejection(self, key, part_id, direction):
        for record in reversed(self._sim.trace):
            if (record.get('physical_state_key_before') == key and record.get('part_id') == part_id
                    and record.get('direction') == direction and not record.get('valid')
                    and record.get('reason') in CACHEABLE):
                return record
        return None

    def _operation(self, kind, part_id, direction):
        self._check_deadline(kind, part_id, direction)
        key = physical_state_key(self._sim.export_state())
        record = self._recorded_rejection(key, part_id, direction)
        if record is not None:
            self._check_cached_streak(kind, part_id, direction, key)
            event = self._begin(kind, part_id=part_id, direction=direction, guard=CACHE_REASON_TAG)
            result = {k: copy.deepcopy(record.get(k)) for k in
                      ('valid', 'reason', 'blockers', 'stability', 'part_id', 'direction', 'collision_distance_m',
                       'extraction_distance_m', 'collision_details')}
            result.update(committed=False, checker_call=None, charged_physics_check=False, cached=True,
                          cached_from_checker_call=record.get('checker_call'),
                          physical_state_key_before=key, physical_state_key_after=key,
                          api_event_index=event['event_index'],
                          scope='Exact repeat of a recorded rejection at this exact state; no physics run, no check charged.')
            self._recovery.setdefault('cached_rejections', []).append(dict(
                event_index=event['event_index'], kind=kind, part_id=part_id, direction=direction, state_key=key,
                cached_from_checker_call=record.get('checker_call'), checks_at_request=self._sim.checks))
            self._finish(event, valid=False, committed=False, reason=record.get('reason'), checker_call=None,
                         charged_physics_check=False, cached=True)
            return copy.deepcopy(result)
        self._cached_streak = 0
        return super()._operation(kind, part_id, direction)

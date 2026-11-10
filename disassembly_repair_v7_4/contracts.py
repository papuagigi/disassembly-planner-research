"""v7.3 contract = v7.2 contract (unchanged text) + V73_COMMON notes 8-10 (identical for A/B/C).

v7.3 additions: R7 recoverable responses (note 8), exact-assembly notes first (note 9), action directions are
world vectors, not label names (note 10). Limits unchanged from v7.2.

v7.2 docstring: v7 contract (unchanged text) + H1/H2 notes; RSS guard raised to 8 GiB.

Recorded protocol changes vs v7.1 (identical for A/B/C): 8 GiB resident-memory guard
(observed transient physics peak 5.45 GiB on 06146), API-level deadline, exact-state
rejection cache. Model, calls, checks, wall time and every other cap are unchanged.
Note 7 (H6 cached-repeat loop stop) was added after validation, before the retry freeze; validation prompts had
notes 5-6 only (outputs/protocol/validation_code_snapshot/contracts.py).
"""
from disassembly_repair_v7.contracts import (COMMON as V7_COMMON, CODE_SPEC, C_SPEC as V7_C_SPEC, SCHEMA, LIMITS as V7_LIMITS,  # noqa: F401
                                             MODEL, EFFORT, ARMS, NO_PROGRESS_LIMIT, PHYSICS_NOTES)

LIMITS = {**V7_LIMITS, 'max_rss_bytes': 8 * 1024 ** 3}

V72_COMMON = '''
V7.2 ENGINE NOTES, IDENTICAL IN A, B AND C:
5. Exact-state rejection cache: api.check/api.remove of an action already REJECTED (path_collision or
   unstable_remainder) at this exact state returns that recorded rejection with cached=True, checker_call=None,
   charged_physics_check=False, without running physics. Physics is deterministic for an exact state, so a repeat
   cannot change the answer. After any state change the action is a new query.
6. The episode wall deadline is also enforced inside the API: after it passes, the next check/remove raises.
7. A cached repeat is NOT added to current_state_feedback. A generated program that receives more than
   max(64, 12 x part count) cached answers in a row (no new physics check in between) is stopped for that turn
   with RepeatedRejectionLoop; the episode continues with the next model call.
'''

V72_C = '''
C7.2 SCHEDULING CHANGE (C only): a newly entered state does NOT ask for a ranking on its first visit. It uses its
nearest ranked ancestor's order and asks you only after 3 rejections there (call_reason=stuck_on_inherited_order),
or after a new instability there. The very first ranking and the committed-window rule for states with their own
order are unchanged. Spend your ranking on what the recorded failures at THIS state show.
'''

V73_COMMON = '''
V7.3 NOTES, IDENTICAL IN A, B AND C:
8. A response that breaks the schema/contract rules or calls any tool is not used; the host asks the same request
   again (at most twice), and every re-ask is a counted model call. Tools are never available.
9. Exact-assembly notes: a loaded document whose skill id starts with "assembly-note-" was written from earlier
   attempts on THIS exact assembly (same geometry fingerprint). Its "Recorded sequence" block lists (part_id, direction
   label) pairs copied from those records. When such a note is loaded, try that recorded sequence first, in order,
   checking each step; switch to general procedures only when a recorded step is rejected or the block ends.
   In CODE: put the recorded sequence in your program before any generic search loop.
   In GRAPH_DFS: at each state rank the next recorded action first.
10. Direction labels are names, not geometry: always read observation.direction_vectors_world (the world vector of
   each label; world +z is up against gravity). "Up/lateral/down" in any document means world vectors.
'''

COMMON = V7_COMMON + V72_COMMON + V73_COMMON
C_SPEC = V7_C_SPEC + V72_C
VERSION = 'v7.3'

"""v7 contract: v6 text, limits, schema, model and arms unchanged; v7 notes APPENDED.

The appended paragraphs describe the v7 common API (all arms), the A/B turn
lifecycle rule and the C scheduler. No v6 sentence is edited, so the prompt
delta is exactly V7_COMMON (+ V7_CODE for A/B, + V7_C for C).
"""
from disassembly_final_v6.contracts import (COMMON as V6_COMMON, CODE_SPEC as V6_CODE_SPEC,
                                            C_SPEC as V6_C_SPEC, SCHEMA, LIMITS, MODEL, EFFORT, ARMS)

NO_PROGRESS_LIMIT = 2

V7_COMMON = '''
V7 COMMON API ADDITIONS, IDENTICAL IN A, B AND C (bookkeeping only; they choose no action and never restore for you):
1. snapshot['search_ledger'] summarizes THIS episode's recorded physics results per exact physical state:
   current = {state_key, removed_count, candidate_action_count, untested_action_count, rejected_action_count,
   accepted_edge_count, known_dead_end, checkpoint_handles, accepted_edges=[{part_id, direction, child_state_key,
   child_removed_count, child_known_dead_end}]}; states = the same summary row for every exact state seen;
   resumable_checkpoints = [{handle, state_key, removed_count, untested_action_count}] for saved states that are not
   known dead ends; known_dead_end_state_count; guarded_request_count.
   known_dead_end=true means every candidate action at that exact state was rejected there, or was accepted into a
   known dead end. Physics is deterministic for an exact state key, so re-entering a known dead end cannot help.
2. Dead-end re-entry guard: api.check/api.remove of an action that was already ACCEPTED at this exact state into a
   known-dead-end child returns valid=False, reason='known_dead_end_child', checker_call=None,
   charged_physics_check=False, without running physics and without charging a physics check. Treat it like a
   rejection at this exact state. Other actions are never blocked by this guard.
3. After every committed removal the host keeps one checkpoint for the new exact state (same checkpoint limit;
   skipped when the limit is reached). api.checkpoint() on an exact state that already has a checkpoint returns
   that existing handle. Checkpoints persist across model turns. Whether, when and where to restore is your choice.
4. Prompt view: the observation in THIS prompt is a compact copy (see observation.prompt_view_note). Repeated
   per-check collision_policy boilerplate and bulky checkpoint context are omitted here only; api.snapshot() and
   api.checkpoints() at runtime return the full objects.
'''

V7_CODE = '''
V7 A/B TURN LIFECYCLE (identical for A and B): your generated program's local variables still do NOT survive a new
model turn, but search_ledger and every checkpoint do. A turn makes progress only if it runs at least one new charged
physics check; a model response, a restore, a checkpoint or a guarded request alone is not progress.
turn_progress_feedback reports each previous execute turn's checks, removals, restores and whether it ended at a known
dead end. After ''' + str(NO_PROGRESS_LIMIT) + ''' consecutive execute turns without progress the host ends the episode
with termination=no_progress_stop. Within these rules you still own all search, ordering, caching and restoring.
'''

V7_C = '''
V7 C SCHEDULING: the controller keeps one order per exact state. It asks you to rank when an exact state is visited
for the first time, when the committed window of that state's current order has been tried (all top-W untried
actions of your order), or after a new instability there. architecture_context.call_reason and committed_window state
which. W = max(6, ceil(checks_remaining / (model_calls_remaining_after_this_call + 1))). When the DFS returns to an
already ranked state it reuses that state's order; a new state without its own ranking inherits its nearest ranked
ancestor's order. All other v6 controller behavior is unchanged.
'''

COMMON = V6_COMMON + V7_COMMON
CODE_SPEC = V6_CODE_SPEC + V7_CODE
C_SPEC = V6_C_SPEC + V7_C
VERSION = 'v7.0'

# Physics condition notes (prompt text identical for A/B/C within a condition).
PHYSICS_NOTES = {
    'P2_persist_up_to_stable_penetration': '''
V7.1 PHYSICS CONDITION P2 (identical for A, B and C): the source-mesh extraction check lets pre-existing CAD
interference of at most stable_penetration_m (1 mm) persist along a path, but it may not grow by more than
resting_contact_slack_m (0.02 mm); deeper initial interference, any new penetration above
penetration_tolerance_m (0.2 mm), containment and floor rules still reject. observation.physics.initial_interference_rule
states this rule. Straight six-label extraction, fixture and MuJoCo residual stability are unchanged.
''',
}

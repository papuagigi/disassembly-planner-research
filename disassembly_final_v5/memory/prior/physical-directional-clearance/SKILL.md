---
name: "physical-directional-clearance"
description: "A portable, evidence-limited procedure for handling direction-specific CAD extraction collisions by testing alternative available directions for the same target."
---
# Directional Clearance Procedure

## Purpose

Use measured physical feedback to decide what to test after an extraction path is rejected for collision. The procedure focuses on a direction-specific option: retain the target and try other currently available directions, including the opposite direction when available. It proposes a test order; it cannot predict acceptance. Evidence IDs below refer to the supplied physical traces.

## Triggers

Apply when the trusted physical validator reports `path_collision` for a target and direction. This is especially useful when the same target has other available directions. The traces repeatedly show a rejected direction alongside a different direction for that target that the validator accepted (D01–D07, D09–D16, D18, D20–D23, D25, D28–D36, D39, D42–D46, D48, D51–D57, D59–D60, D62, D64–D66, D69–D70, D72, D74–D77, D79–D80, D82–D83, D86–D87, D89).

## Diagnosis

A path collision concerns the tested target-direction pair in its current assembly state. It does not show that the target is unextractable in every direction: many traces pair a collision in one direction with an accepted alternate for the same target (for example D01, D04, D10, D22). Some traces have only rejected directions and no accepted query (D08, D17, D19, D24, D26–D27); do not infer a repair where no accepted alternative was measured.

Direction strings such as `+x` are action labels. They do not define world orientation. The supplied traces map the same labels to different world vectors across assemblies (D01, D02, D03, D04, D05). If world vectors are available, inspect them and the geometry; still use physical validation to decide.

## Numbered executable-by-the-planner steps

1. On collision, record the exact assembly state, target, attempted direction, reported blockers, and whether the action was committed. Treat a rejected, uncommitted query as no removal.
2. Keep the target eligible for later testing. Do not convert a single direction’s collision into a target-wide ban. Repeatedly blocked directions for the same target can coexist with a clear alternate (D01, D04, D10, D22).
3. List the target’s other currently available directions. Use available geometry and world vectors to order them by plausible clearance. If the opposite direction is available, include it as a candidate; traces show both opposite-direction alternatives and other-axis alternatives succeeding (D06, D16, D21; D04, D10, D22). This is a candidate-generation rule, not a claim that the opposite will work.
4. Query one candidate direction with the trusted physical validator. Do not assume geometric inspection or a previous acceptance is sufficient. Every removal still needs validation.
5. If rejected, record the result against the exact state, target, and direction, then test remaining available directions. Keep unknown and untested options available. If all tested options fail, report that this state has no measured accepted direction among those tested; do not claim no direction can work.
6. If accepted as a hypothetical check but not committed, record it as a promising direction only. If removal is committed, use the new assembly state and reassess candidates; do not transfer prior direction results as guarantees. D54 includes an accepted, stable check and a later committed removal for the same action.
7. Preserve alternatives and exact-state failure memory. A failure should lower priority only for its recorded state and direction. After any state change, reconsider directions under fresh geometry and validation.

## CODE versus GRAPH_DFS application

- **CODE:** Incorporate these rules into the planner’s own candidate generation and history. After a collision, retain the target and enumerate its other available directions. Store each result with exact state, target, direction, blockers, and commit status. Submit every chosen removal to the trusted validator.
- **GRAPH_DFS:** Rank only currently available actions. After a collision, lower that target-direction pair for the recorded state and raise other available directions for the same target as candidates. Preserve all untested actions and exact-state history. The host remains responsible for traversal, state tracking, recovery, and validator calls; ranking alone does not execute or validate a removal.

## Expected trusted feedback

A candidate direction is supported only when the physical validator returns an accepted result and reports a stable remainder. A completed removal requires a committed result and confirmed state change. A collision response with blockers explains the tested path; it does not certify other paths. The traces include stable accepted checks for alternate directions (D01, D04, D10, D22) and a committed accepted removal (D54). Every removal still requires validation.

## Non-applicability

Do not apply this direction-search procedure to failures other than path collision. It does not repair instability, determine which blocker to remove, or prescribe a universal extraction direction. Do not infer physical orientation from direction labels, turn one rejected direction into a global prohibition, or treat an accepted hypothetical check as a committed removal.

## Evidence limitations

The supplied evidence consists of measured traces with many path-collision failures and some accepted alternative-direction checks. Several traces have no accepted query, so alternatives are not guaranteed. The data do not provide new evaluation cases, independent validation, or evidence of universal success. These rules describe a testable response to observed direction-specific collisions; they do not establish why a path is clear or whether this procedure improves overall task success. No answer sequence or API repair is prescribed.

---
name: "physical-clearance-chain"
description: "Evidence-limited planner procedure for resolving reported path blockers through validated removals and retesting, while preserving exact-state failure history."
---
# Physical Clearance Chain

## Purpose

Use trusted collision feedback to order a short chain of removals that may clear a reported extraction path. This procedure captures measured blocker removal followed by a later accepted extraction. It guides candidate order; it does not guarantee a complete disassembly. Keep using the existing directional-clearance and failure-repair procedures.

## Observed triggers

Apply after a trusted `path_collision` response names one or more remaining components as blockers. The failed query must be a verified physical result. Resource limits, timeouts, provider errors, and engine warnings are not physical failure evidence.

## Numbered planner actions

1. Record the physical state identity, target, attempted direction, reported blockers, and commit status. A failed removal query does not commit, so the assembly state remains unchanged; it alone does not call for checkpoint restoration.
2. Keep the rejected target-direction pair in exact-state failure history. Do not retry it while the physical state is unchanged. Preserve other untested directions for that target.
3. For each named blocker, check whether it is a current removable candidate and list its available directions. Rank removable reported blockers ahead of unrelated candidates as a test order. A blocker report identifies geometry in the attempted path; it does not establish support, precedence, or that removing the blocker will succeed.
4. Query a blocker removal with the trusted validator. If it is rejected, retain that exact-state result and consider other current candidates or directions. Do not restore solely because of a failed query.
5. After an accepted, committed removal, use the new physical state and recompute current candidates and paths. Retest the deferred target only if its direction is available and the state has changed; every attempted removal still requires physical validation.
6. If the target remains blocked, repeat from its new feedback. Do not retry unchanged known failures. If a committed removal was later undone by restoration, retain the exact-state records, inspect the restored state, and follow the host planner’s recovery rules.

## Expected trusted physical feedback

A useful sequence is: collision with a named blocker; accepted and committed removal of a current blocker; then an accepted, committed target removal in the changed state. Each accepted removal must be physically validated, and state change must be confirmed. L01 records a collision for part 10 naming part 11, followed by committed removals of 11 and then 10. L04 records part 2 blocked by part 6, then accepted removal of part 2 in the opposite direction; this supports retaining alternate directions, not assuming the blocker must be removed. These are examples, not a general causal rule.

## Backtracking and limitations

Observed restoration events in L05 and L08 show host restores after committed branches. They do not establish that restoring after an uncommitted failed query is useful or that this procedure’s blocker ordering caused recovery. No successful backtracking repair is established here. Exact-state failure records survive restoration; do not retry an unchanged known failure. Never invent hidden support, rotation, grasp, or collision exemptions. Support/contact relations are clues, not a complete physical model. A blocker may be fixed or otherwise unavailable; do not assume it can be removed. Stop claims at the tested state and directions.

## Planner applicability

- **Generated-code B:** Use the blocker-first ranking as a heuristic in the planner’s own candidate ordering and retain exact-state failure history. The generated planner still owns its frontier, execution, and recovery; validate each action physically.
- **Fixed Graph/DFS C:** Apply the procedure only to rank currently available actions. The fixed DFS controls branch traversal and restore timing. This document does not change that behavior or direct a restore; it only guides ordering within the host’s controls.

## Evidence and scope

Usable physical feedback supports the measured examples in L01, L02, L04, L05, L07, L08, L09, and L10. L03 is excluded for native engine warnings; L06 has no observed physical rejection and is excluded for a memory limit. Operational stops are not physical failures. The evidence covers 10 episodes on 8 unique long CADs: eight inherited 1 GiB episodes (five capped at 240 checks, three at 600) and two additional episodes that repeat existing training CADs with 600 checks, 900 seconds, 8 calls, and 4 GiB. These are not 10 independent products, and the extra effort is not a matched-policy performance gain. Prior-version validation outcomes, independent validation, and final test CADs are withheld. Treat this procedure as provisional; do not claim general efficacy or successful independent validation.

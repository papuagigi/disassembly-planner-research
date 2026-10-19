---
name: "physical-long-horizon-clearance"
description: "Evidence-limited procedure for coordinating blocker removal, direction alternatives, and exact-state feedback during long-horizon physical disassembly."
---
---
name: "physical-long-horizon-clearance"
description: "Evidence-limited procedure for coordinating blocker removal, direction alternatives, and exact-state feedback during long-horizon physical disassembly."
---
# Physical Long-Horizon Clearance Procedure

## Purpose

Guide candidate ordering over many removals using trusted physical feedback. The measured traces support two practical patterns: try another available direction after a path collision, and when a reported blocker itself has an accepted extraction, reassess the blocked target in the changed state. These patterns guide queries; they do not guarantee task completion. Every accepted removal requires physical validation.

## Observed triggers

Apply when a current removable candidate receives a trusted `path_collision` result. Record its reported blockers and exact state. The evidence shows both same-state alternate directions accepted (L01, L02, L04, L05) and accepted removal of a reported blocker followed by a later accepted removal of the previously blocked target (L01: 10 blocked by 11, 11 removed, then 10 removed; L04: 5 blocked by 9, 9 removed, then 5 removed). L04 also shows a target with several rejected directions accepted in another available direction.

This is long-horizon ordering evidence, not a universal strategy. L05 exhausted its check budget without reaching the goal despite accepted removals and repeated direction trials.

## Numbered planner actions

1. **Establish the current state.** List only currently removable candidates and their available actions. Keep an exact-state record of prior query results.
2. **On collision, record the observation.** Store state identity, target, direction, blockers, result, and commit status. A failed removal query does not commit or change the physical state; it alone does not require checkpoint restoration.
3. **Try available directions for the same target.** Order them using available geometry and world vectors, if provided. Direction labels alone do not establish world orientation. Query each chosen candidate with the trusted validator. A collision for one direction does not prohibit the target in other directions.
4. **Use named blockers as ordering clues.** If the target remains blocked, consider current removable blockers named by the validator. This only prioritizes a test; it does not prove a support relation or that removing the blocker will clear the path.
5. **Validate every removal.** Commit only when the trusted validator accepts the proposed removal. After commitment, use the resulting physical state and refresh candidate availability, blockers, and directions.
6. **Reconsider deferred targets after relevant changes.** When a blocker has been removed or the state otherwise changes, query the deferred target again if available. Rejections remain tied to their exact recorded state and action. Exact-state records survive restoration; do not retry an unchanged known failure. A different state requires fresh assessment, not an assumption of success.
7. **Continue with remaining candidates and report limits.** If tested actions fail, preserve untested actions and state only that no tested action was accepted in that state. Do not infer that the assembly is impossible to disassemble.

## Expected trusted physical feedback

A rejected collision query identifies a tested path and may name blockers; it is not a removal. An accepted, committed result should confirm the removed component and changed physical state. Reassessing after blocker removal may then produce a newly accepted removal, as observed in L01 and L04. These observations do not establish causation beyond the measured sequence or predict future acceptance.

## CODE and fixed Graph/DFS applicability

- **Generated-code B:** Use the procedure to order its own available candidate queries and retain exact-state feedback. Preserve untested actions. Do not replace the host’s execution, validation, or state tracking.
- **Fixed Graph/DFS C:** Use this document only to rank currently available actions. The fixed DFS controls traversal and restore timing. The document does not change that control flow or prescribe restoration. Failed queries alone do not require restoration. Preserve exact-state failure records across restoration and avoid retrying an unchanged known failure.

## Limitations and evidence status

L01, L02, and L04 reached their measured goals; L05 did not, despite many accepted removals and 40 restores. L03 is excluded because native engine warnings made its physical-procedure evidence unusable. These are development observations, not independent validation. Evaluation and independent validation CADs are withheld.

Alternating directions and prioritizing named blockers are observed query-order patterns. The explanation that a blocker’s removal enables the target is a hypothesis beyond the measured sequence. Do not infer hidden supports, rotations, grasp changes, or collision exemptions. Do not claim successful backtracking as a repair: although L05 records restores, the evidence does not establish successful backtracking. This procedure does not supersede prior direction-specific clearance or failure-repair guidance and does not establish universal disassembly success.

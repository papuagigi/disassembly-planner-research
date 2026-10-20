---
name: "physical-disassembly-failure-repair"
description: "Conditional procedure for reprioritizing physical removal actions after instability or path-collision rejection, based on CAD/MuJoCo feedback."
---
# Physical Disassembly Failure-Repair Procedure

**Version:** 1.0

## Purpose

Use trusted physical feedback to reprioritize removal actions after an extraction fails. This procedure proposes testable priorities; it does not predict success. Every action still requires the trusted physical validator.

## Applicability and observable triggers

Apply when a current removable component’s extraction is rejected with either:

- **Unstable remainder:** the path check did not report a collision, but the remainder failed stability criteria. Inspect `stability.unstable_parts`, displacement, rotation, speed, penetration, and whether the action was committed.
- **Path collision:** the proposed extraction path intersects remaining geometry. Inspect the reported blockers and whether the action was committed.

Use only current state and current removable candidates. Fixed or absent components cannot be removed. This procedure does not prescribe repairs for other failure reasons.

## Diagnosis

These failures imply different next priorities. Instability means the attempted removal disturbed one or more remaining bodies; it does not establish that the target directly supports each unstable body. Balancing, interlocking, contacts, or other geometric constraints may explain the motion. A collision names geometry in the attempted path; it does not establish a universal removal order.

Support/contact edges are clues, not a guaranteed precedence graph or complete stability model. Direction labels are not physical directions: inspect `direction_vectors_world` for the actual world-space vector and reason about that path.

## Numbered repair procedure

1. **Record the rejected query.** Record the exact physical-state identity, target, action direction and corresponding world vector, reason, blockers or unstable-part IDs, stability metrics, and committed status. A failed hypothetical check leaves committed state unchanged; do not count it as a removal.

2. **If the remainder is unstable, defer that target in this state.** First prioritize current removable candidates explicitly listed in `unstable_parts`. Next prioritize other current removable components whose observed geometry or contacts could constrain those unstable bodies. This second group is a hypothesis for testing, not a required support-edge relation. Do not assume a candidate will stabilize the remainder before validation.

3. **If geometry blocks the path, prioritize removable blockers.** For the rejected target and direction, first consider current removable components named as blockers. Among them, rank candidates with an apparently collision-free available extraction path ahead of those whose own paths are blocked. If no blocker is removable, consider other current removable candidates whose removal could change the reported obstruction. Keep the rejected target and all untested actions available; one collision does not show that every direction or future state is impossible.

4. **Select candidate directions from geometry.** Inspect each prioritized candidate’s available actions, current component geometry, and `direction_vectors_world`. Use the actual world vector to judge whether the swept path could clear geometry. Do not infer physical orientation from the action label.

5. **Query the trusted validator.** Test prioritized candidates without committing rejected checks. Preserve each result in the history for its exact physical state. If one fails, continue to other current candidates or directions; do not restore solely because one candidate failed, and do not apply a global action blacklist.

6. **After an accepted removal, reassess.** Use the resulting physical state and geometry to recompute removable candidates, blockers, and instability risks. Previous failures apply only to the exact state in which they occurred. An explicit restoration also requires fresh assessment. Do not carry a past rejection forward as a prohibition.

7. **Retry the deferred target when evidence changes.** After an accepted removal plausibly changes a constraint on the unstable body, or removes/changes a reported blocker, reconsider the rejected target and query the validator again. If no relevant state change has occurred, keep it lower priority while testing other evidence-backed current candidates. A retry is a new physical query, not an assumed success.

## CODE / GRAPH_DFS application

Both roles must change physical action priorities according to this procedure, while retaining failed candidate history.

- **CODE:** Generate your own executable program, frontier, and record keeping. Apply the conditional priorities above to your own available actions. Keep unknown and untested actions available. Key recorded failures to exact physical state and reassess after accepted removals or restoration. This document is not a stored search implementation and does not replace host recovery or frontier logic.
- **GRAPH_DFS:** Rank only currently available candidate actions. Raise the priority of candidates supported by the observed instability or blocker evidence, and lower the rejected target only for that diagnosed state. Preserve unknown and untested actions. The host remains responsible for DFS, frontier and recovery, state tracking, and validator queries; ranking cannot replace them.

## Expected physical feedback

Progress is verified only by a trusted validator response that accepts and commits a removal, reports a stable remainder, and confirms the resulting state change. Relevant evidence can include a named blocker no longer being present or a previously unstable body no longer appearing in the instability report. A ranking change or geometric hypothesis is not verification. No success is known before the query.

## Exclusions

Do not use this procedure for fixed or absent components, or as a substitute for physical validation. Do not treat support edges as mandatory precedence, unstable IDs as necessarily supported directly by the target, a single failed candidate as grounds for restoration, or any rejection as a global blacklist. Do not assume an action accepted in one state will succeed in another.

## Evidence and validation

Evidence is summarized in generic `outputs/development/failure_evidence.json`; admission status is in `references/admission.json`. The traces show both collision rejections naming blockers and stability rejections naming unstable remainder bodies, followed in some cases by accepted removals after the assembly changed. They also show unstable bodies that are not outgoing support-edge targets and direction labels that map to different world vectors across traces. These observations motivate conditional priorities, but do not establish a universal cause or repair.

**Admission: pending means provisional.** Independent actors must test this procedure on reproduced physical failures without its authors’ code or any future answer sequence. Development diagnostics are not admission. Do not claim validation or efficacy before admission.

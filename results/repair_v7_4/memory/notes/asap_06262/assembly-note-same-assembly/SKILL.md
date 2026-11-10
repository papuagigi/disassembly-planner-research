---
name: "assembly-note-same-assembly"
description: "First-attempt guidance for replaying and adapting this assembly’s recorded removal path."
---
## Triggers

Use this note only when the same assembly geometry fingerprint is recognized. Part ids and direction labels refer to the planner records.

## Procedure

Start by trying the appended **Recorded sequence** in order, checking each removal before proceeding. It is a complete successful path from condition A: parts `0`, `1`, `4`, `5`, then `3`, all in `+x`.

If a step is rejected, keep the already accepted removals and replan from the resulting state; do not assume later steps remain valid. For parts `0` and `1`, condition B and C also show successful removals in `-y`. After those two removals, condition B removed `3`, `4`, `5` in `+x`; condition C removed `5`, `4`, `3` in `-x`. These alternatives are recorded successful paths, not guarantees for every planner condition.

At the start, the records do not show that any part was blocked in many directions: condition A succeeded in five checks with no recorded rejection. In conditions B and C, parts `0` and `1` were removable first in `-y`. For parts `3`, `4`, and `5`, `-y` was rejected in B; after `0` and `1` were removed, B removed all three in `+x`. In C, `+y` and `-y` were rejected for `3` and `5`, and `+y`, `-x`, and `-y` for `4`; after removing `0` and `1`, C removed `5`, `4`, and `3` in `-x`. Thus the records support the practical ordering “clear `0` and `1` first, then retry the remaining parts along an observed successful axis.”

Direction labels map to world vectors as follows: `+x` = `[1, 0, 0]`, `-x` = `[-1, 0, 0]`, `+y` = `[0, 0, -1]`, `-y` = `[0, 0, 1]`, `+z` = `[0, 1, 0]`, and `-z` = `[0, -1, 0]`. Across the recorded checks, the never-accepted labels were `+y` (world `[0, 0, -1]`) and `-y` (world `[0, 0, 1]`) for parts `3`, `4`, and `5`. Also, `-x` (world `[-1, 0, 0]`) was rejected for part `4` in condition C, though it succeeded for parts `5`, `4`, and `3` later in that same condition after blockers were removed. No rejection is recorded for `+z` or `-z`; that does not establish they work.

## CODE application

Replay the complete appended sequence first. If a check rejects a step, retain the successful prefix and use the observed alternatives: for the initial pair try `-y` if needed; after clearing parts `0` and `1`, try the remaining parts in `+x` (condition B pattern) or `-x` in order `5`, `4`, `3` (condition C pattern). Avoid spending checks on the recorded rejected labels for parts `3`–`5` unless the changed state gives a specific reason to retry.

## GRAPH_DFS application

Use the appended sequence as the first preferred path. If it is partial or a branch fails, continue search from the deepest accepted state, preserving the prefix. Prioritize the recorded state transition after removing `0` and `1`, then try the demonstrated suffixes: `3 → 4 → 5` in `+x`, or `5 → 4 → 3` in `-x`. Do not repeatedly sweep all six directions for parts `3`, `4`, and `5`: the records show repeated unsuccessful vertical-label checks and a rejected `-x` check for part `4` before a later successful `-x` removal.

## Evidence

All three first attempts succeeded, each removing all five required parts. Condition A completed in 5 checks and 166 seconds, with no recorded rejections; its committed sequence is the appended block. Condition B completed in 8 checks and 145 seconds: `0` and `1` in `-y`, then `3`, `4`, `5` in `+x`; its checks 3–5 were rejected `-y` attempts for parts `3`–`5`. Condition C completed in 15 checks and 235 seconds: `0` and `1` in `-y`, then `5`, `4`, `3` in `-x`; its rejection record lists vertical-label failures for `3`–`5` and an earlier `-x` rejection for `4`.

The extra checks and elapsed time in B and C are consistent with wasted rejected-direction checks. The records do not identify the duration of individual checks, so they do not establish that any particular check was slow or unstable. Condition C’s successful `-x` removal of part `4` after an earlier rejection shows that its removability depended on the assembly state.

## Limits

These are planner first-attempt records, not reference solutions. They establish successful paths and specific rejected attempts only for the recorded conditions and states. No attempt failed or ended partial, so there is no evidence-based recovery path for a deepest partial state beyond retaining the accepted prefix and trying the successful patterns above. The records do not report checks for every part-direction pair; untried directions remain unknown.

## Recorded sequence

Source: first-attempt condition A, complete success, 5 of 5 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `0` direction `+x` (world [1.0, 0.0, 0.0])
2. part `1` direction `+x` (world [1.0, 0.0, 0.0])
3. part `4` direction `+x` (world [1.0, 0.0, 0.0])
4. part `5` direction `+x` (world [1.0, 0.0, 0.0])
5. part `3` direction `+x` (world [1.0, 0.0, 0.0])

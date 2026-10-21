---
name: "assembly-note-all-parts-positive-z"
description: "Assembly-specific guidance based on three successful first-attempt records for this geometry fingerprint."
---
## Triggers

Use this note only when the planner sees the same assembly geometry fingerprint. It is based on first-attempt conditions A, B, and C.

## Procedure

Start with the appended **Recorded sequence**: remove parts `1` through `8` in order, each along `+z` (world `[0, 0, 1]`). Condition B committed this full path with 8 checks and no recorded rejections. If a step is rejected, keep the already accepted prefix, then retry from that current state; do not assume later steps remain valid. Condition A shows an alternative order and directions that succeeded, while condition C shows that other parts can become removable after earlier removals. Recheck the blocked part at the new state before choosing another direction.

At the initial state, condition A recorded rejections for parts `1`, `2`, `3`, and `5` along `+x` and `+y`, and for part `7` along `+x`. Condition C rejected `+z` for parts `2`–`8` before their later acceptance in that attempt; its accepted order began with part `1`, then parts `5`–`8`, then `2`–`4`. This demonstrates that a direction rejected at one state may work after other parts are removed.

## CODE application

Prioritize the recorded all-`+z` path. If the CODE search rejects a step, retain the accepted prefix and consider the successful condition A sequence as a fallback: `1:+z`, `2:+z`, `3:+z`, `4:+x`, `5:+z`, `6:+x`, `7:+y`, `8:+x`. Recheck candidates after each removal; avoid repeatedly testing the same rejected direction without a state change.

## GRAPH_DFS application

Use the recorded path as the first branch and expand from its accepted prefix if a step fails. Condition C provides evidence for a useful alternate ordering: after removing part `1` along `+z`, try `5`, `6`, `7`, and `8` along `+z`, then `2`, `3`, and `4` along `+z`. Treat prior rejections as state-specific, not permanent constraints.

## Evidence

All three first-attempt conditions succeeded, each removing all 8 required parts. Condition A used 17 checks and took 22 seconds; condition B used 8 checks and took 34 seconds; condition C used 15 checks and took 30 seconds. In B, every accepted removal was `+z`, in numerical part order, with no rejected directions recorded. In A, the accepted sequence was `1:+z`, `2:+z`, `3:+z`, `4:+x`, `5:+z`, `6:+x`, `7:+y`, `8:+x`. In C, all parts were ultimately accepted along `+z` in the order stated above, despite earlier `+z` rejections for parts `2`–`8`.

Recorded failed direction labels and world vectors: `+x` = `[1, 0, 0]` and `+y` = `[0, 1, 0]` were rejected for parts `1`, `2`, `3`, and `5` in A; `+x` was also rejected for part `7` in A. `+z` = `[0, 0, 1]` was rejected for parts `2`–`8` in C at earlier states. These labels were not universally impossible: `+z` succeeded for every part in the completed paths, and `+x` or `+y` succeeded for some parts in A.

No broad six-direction sweep or repeated loop is recorded. Condition A has three checks per first three removals, indicating several failed direction checks before acceptance; B reached completion in one check per part. The records provide total elapsed time only, so they do not identify any particular check as slow or unstable.

## Limits

These are planner first-attempt outcomes, not reference solutions. The records do not establish a geometric reason for any rejection, do not show whether direction feasibility is stable across planner conditions, and do not give per-check timings. The recorded sequence is a successful observed path for this fingerprint; individual steps may still need revalidation when the current planner state differs.

## Recorded sequence

Source: first-attempt condition B, complete success, 8 of 8 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `1` direction `+z` (world [0.0, 0.0, 1.0])
2. part `2` direction `+z` (world [0.0, 0.0, 1.0])
3. part `3` direction `+z` (world [0.0, 0.0, 1.0])
4. part `4` direction `+z` (world [0.0, 0.0, 1.0])
5. part `5` direction `+z` (world [0.0, 0.0, 1.0])
6. part `6` direction `+z` (world [0.0, 0.0, 1.0])
7. part `7` direction `+z` (world [0.0, 0.0, 1.0])
8. part `8` direction `+z` (world [0.0, 0.0, 1.0])

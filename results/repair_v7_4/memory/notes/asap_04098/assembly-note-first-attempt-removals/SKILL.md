---
name: "assembly-note-first-attempt-removals"
description: "Assembly-specific guidance based on the planner’s three first-attempt records for this geometry fingerprint."
---
## Triggers

Use this note only when the planner identifies the same assembly geometry fingerprint. It records first-attempt behavior for conditions A, B, and C; the successful removal order varies by condition.

## Procedure

1. Try the host-provided **Recorded sequence** first, checking each removal in order. It is a complete successful path from condition C: parts `5` and `6` along `-y`, then `7` along `+x`, then `8` along `-x`.
2. If a step is rejected, keep the already committed prefix and search from the current state. Do not assume another condition’s full sequence will work unchanged. The records show that `5` and `6` can each be removed in different directions or orders depending on the path.
3. If the sequence is partial, continue from its deepest committed state, first trying directions with recorded successes for the remaining part. Recheck feasibility after each removal; later removals may become possible after earlier parts are cleared.

Parts `5` and `6` were both rejected along the same vertical-ish direction in each of the three starts: `-z` in A and B, `+z` in C. Both later became removable: A removed `7` and `8` first, then `6` and `5`; B removed `7` and `8` first, then `5` and `6`; C removed `5` and `6` first, then `7` and `8`. The records do not identify the exact blocker geometry, so treat the observed order as guidance rather than a proven causal explanation.

## CODE application

Start with the Recorded sequence as the action order for this exact assembly. Preserve its committed prefix if a check fails, then try a recorded successful alternative for the rejected part: `5` succeeded along `-y` (C), `+x` (B), and `-x` (A); `6` succeeded along `-y` (C), `+x` (B), and `-x` (A). Parts `7` and `8` succeeded along `-z` in A and B; C instead removed them along `+x` and `-x`, respectively. Revalidate each action in the current state.

## GRAPH_DFS application

Use the Recorded sequence as the first branch. Prune the observed failed part-direction pairs: `5/-z` and `6/-z` in A and B, and `5/+z` and `6/+z` in C. If the active condition is unknown, these are observed failures across the available attempts, not a proof that the directions always fail. Avoid repeating an identical rejected action at an unchanged state. After a prefix succeeds, prioritize the recorded continuation from that same condition where available.

## Evidence

- Condition A succeeded in 9 checks and 23 seconds: `7/-z`, `8/-z`, `6/-x`, `5/-x`.
- Condition B succeeded in 10 checks and 24 seconds: `7/-z`, `8/-z`, `5/+x`, `6/+x`.
- Condition C succeeded in 7 checks and 20 seconds: `5/-y`, `6/-y`, `7/+x`, `8/-x`.
- Across all three attempts, every direction label had at least one accepted removal. No label is supported as a direction that never worked. The recorded failures are limited to the part-direction pairs listed above.
- The direction labels use world vectors with world `+z` up: `+x = [1, 0, 0]`, `-x = [-1, 0, 0]`, `+y = [0, -0.999310454, -0.037129723]`, `-y = [0, 0.999310454, 0.037129723]`, `+z = [0, 0.037129723, -0.999310454]`, `-z = [0, -0.037129723, 0.999310454]`. Thus the `+z` label points mostly downward in world coordinates; `-z` points mostly upward.
- The records report 7–10 checks and 20–24 seconds per successful attempt. They do not identify any slow unstable checks, broad six-direction sweeps, or repeated loops, so no such waste pattern can be established from these records.

## Limits

These are three successful first attempts, not a reference solution or an exhaustive search. Rejections are recorded only for specified part-direction pairs; lack of a rejection entry does not prove a direction was tested or will work. The records do not expose per-check durations, intermediate blocker geometry, or whether alternative sequences were tried. The Recorded sequence is a committed successful path for condition C and may need adaptation if the current condition or state differs.

## Recorded sequence

Source: first-attempt condition C, complete success, 4 of 4 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `5` direction `-y` (world [0.0, 0.999, 0.037])
2. part `6` direction `-y` (world [0.0, 0.999, 0.037])
3. part `7` direction `+x` (world [1.0, 0.0, 0.0])
4. part `8` direction `-x` (world [-1.0, 0.0, 0.0])

---
name: "assembly-note-recorded-path"
description: "First-attempt guidance for replaying this assembly’s successful removal path and handling rejected or incomplete steps."
---
## Triggers

Use this note only when the planner recognizes this same assembly geometry fingerprint. Part IDs and direction labels refer to the first-attempt records.

## Procedure

Start by replaying the host’s **Recorded sequence** in order. It is a complete first-attempt path: condition C removed all 10 required parts in 35 checks. Treat each accepted step as state-dependent; after each removal, update the assembly state before proceeding.

If a step is rejected, do not keep repeating that part-direction check in the unchanged state. Resume from the current state and prioritize the remaining suffix of the recorded sequence. If a recorded direction was rejected earlier, that rejection was in a different state and does not rule out trying it after preceding removals. Condition C itself rejected `-z` for parts `2`, `3`, `4`, `5`, and `8` before those parts were later removed in `-z`; replay the sequence’s preceding removals before applying those steps.

If the available path is partial, preserve its accepted prefix and continue from the deepest reached state. Prefer the next recorded action when available. Avoid broad sweeps of all six directions: the records show repeated rejected checks and long delays before some removals.

At the start, parts `1`–`6` were blocked in many tested directions across attempts. Part `8` was also broadly blocked in condition A, then removed after part `0` in condition B using `-y`, or later using `-z` in successful condition C. Part `9` had `+z` rejected in A and `-y` rejected in B; it became removable in `-z` in A and C after part `0` was removed. In successful condition C, parts `2`–`5` and `8` became removable in `-z` after the earlier sequence steps, even though their initial `-z` checks were rejected. Parts `1` and `6` were removed last in `-y`, after parts `9`, `2`, `3`, `4`, `5`, `8`, and `7` had been removed.

## CODE application

For CODE replay, seed the successful sequence as the preferred ordered plan. Validate each action against the live state, then continue from the accepted prefix if an action fails. Do not interpret a rejection from an earlier state as a permanent direction ban.

## GRAPH_DFS application

For GRAPH_DFS, use the recorded path to guide branch order: try its next action first, and explore alternatives only after rejection in the current state. Track visited states or failed state-action pairs to avoid repeated loops. The records do not establish whether either planner mode will reproduce the timings or outcomes exactly.

## Evidence

Condition C succeeded: 10/10 removals in 35 checks over 785 seconds. Its accepted order is shown in the host’s **Recorded sequence**. Condition A and B each removed only 3/10 before exhausting a 900- or 901-second wall-time budget.

Direction labels that never worked in any recorded attempt, with their recorded WORLD vectors:

- `+x`: `[0.9999999999999999, 0.0, 1.5504980169254497e-08]`
- `-x`: `[-0.9999999999999999, 0.0, -1.5504980169254497e-08]`
- `+y`: `[1.5504980169254503e-08, 0.0, -0.9999999999999999]`

These labels were rejected whenever they were checked. In particular, `+y` was only recorded as rejected for part `1` in C; no successful use is recorded. `-y` did work for parts `0`, `8`, `1`, and `6` in the records, and `+z` and `-z` also had successful uses. The vectors show that world `+z` is up; direction labels do not correspond to assumed world axes.

Checks and time were spent on broad direction sweeps and retries: A used 33 checks and 901 seconds for 3 removals; B used 43 checks and 900 seconds for 3 removals. In B, part `7` was accepted only at check 43. The successful C path still took 785 seconds, with later removals of parts `7`, `1`, and `6` at checks 30, 34, and 35. Favor the known path to limit repeated checks.

## Limits

These are planner first-attempt records, not reference solutions or proof that rejected directions are geometrically impossible. Rejections are tied to the state in which each check occurred. The records give no exact blocker geometry, so do not infer specific contacts or clearances beyond the observed state-dependent removals.

## Recorded sequence

Source: first-attempt condition C, complete success, 10 of 10 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `0` direction `-y` (world [-0.0, 0.0, 1.0])
2. part `9` direction `-z` (world [0.0, -1.0, 0.0])
3. part `2` direction `-z` (world [0.0, -1.0, 0.0])
4. part `3` direction `-z` (world [0.0, -1.0, 0.0])
5. part `4` direction `-z` (world [0.0, -1.0, 0.0])
6. part `5` direction `-z` (world [0.0, -1.0, 0.0])
7. part `8` direction `-z` (world [0.0, -1.0, 0.0])
8. part `7` direction `+z` (world [0.0, 1.0, 0.0])
9. part `1` direction `-y` (world [-0.0, 0.0, 1.0])
10. part `6` direction `-y` (world [-0.0, 0.0, 1.0])

---
name: "assembly-note-five-part-removal"
description: "Use the recorded successful removal path for this exact assembly and recover from rejected or incomplete steps using observed attempts."
---
## Triggers

Use this note only when the assembly geometry fingerprint matches this same five-part assembly. Part ids and direction labels refer to the planner records. World +z is up.

## Procedure

Start with the host-appended **Recorded sequence** and try its steps in order, checking each removal before committing it. It is a complete successful first-attempt path for all 5 required removals.

If a step is rejected, do not assume later steps in that sequence remain valid. Continue from the current assembly state: try the recorded alternatives that succeeded in other conditions, and check removability again after each accepted removal. The records show part `3` can be removed in `-x` after parts `1` and `2`, as in condition A, or in `+x` after parts `1`, `2`, `4`, and `5`, as in conditions B and C.

If the sequence is partial, resume from its last committed state. Prefer the successful continuation matching the removals already made: after `1` then `2`, condition A removed `3 (-x)`, then `4 (+x)`, then `5 (+x)`; conditions B and C removed `4 (+x)`, `5 (+x)`, then `3 (+x)`.

At the start, part `1` was accepted in `+y` in all three conditions. Part `2` was rejected in `+y` in all three conditions and became removable in `+x` after part `1`. Parts `4` and `5` were each rejected in `+y` in all three conditions; they became removable in `+x` after parts `1` and `2`. Part `3` was rejected in `+y` in all three conditions and in `+x` in two conditions; it was accepted in `-x` after parts `1` and `2` in condition A, and in `+x` after parts `1`, `2`, `4`, and `5` in conditions B and C. Condition A also rejected `3 (+z)`; the other conditions did not record that check.

The direction labels that never worked in the recorded checks were `+y` for parts `2`, `3`, `4`, and `5`, and `+x` for part `3` in conditions A and B. Their world vectors are `+y = [0.0, 0.0, 1.0]` and `+x = [-1.0, 0.0, 0.0]`. These are labels with observed failures, not proof that every untried direction fails. No rejection was recorded for the other labels, so do not infer that they were tested and rejected.

## CODE application

Use the committed path as the initial action order. After any rejection, retain the current state and recheck candidate removals there; for part `3`, use the state-matched successful options above. Avoid repeatedly probing known rejected directions without a state change.

## GRAPH_DFS application

Seed the search with the recorded sequence. If a branch is rejected, backtrack to the last committed state and try the other recorded successful continuation. Prioritize removing `4` and `5` before `3` when following the B/C branch; the A branch removes `3` earlier using `-x`.

## Evidence

All three first attempts succeeded, each removing 5 of 5 parts. Conditions B and C recorded the same complete path as the host block; condition A used `3 (-x)` after `1` and `2`. Accepted removals occurred at checks 1, 6, 8, 10, and 11 in B; checks 5, 10, 13, 16, and 17 in C; and checks 1, 6, 12, 15, and 17 in A. Elapsed time was 16 seconds (A), 26 seconds (B), and 30 seconds (C).

The records do not identify which rejected checks were slow or unstable. Conditions A and C used 17 checks, compared with 11 in B; C also took longer than B despite the same path. This indicates additional check cost or overhead, but does not establish its cause. No broad six-direction sweep or repeated loop is documented, so avoid claiming those occurred.

## Limits

This note is based only on three planner first attempts for this geometry fingerprint. It records observed outcomes, not a reference solution or a guarantee that the same path will be accepted under changed planner settings or geometry. The records do not list every attempted direction or per-check timing, so unrecorded directions and slow individual checks remain unknown.

## Recorded sequence

Source: first-attempt condition B, complete success, 5 of 5 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `1` direction `+y` (world [0.0, 0.0, 1.0])
2. part `2` direction `+x` (world [-1.0, 0.0, 0.0])
3. part `4` direction `+x` (world [-1.0, 0.0, 0.0])
4. part `5` direction `+x` (world [-1.0, 0.0, 0.0])
5. part `3` direction `+x` (world [-1.0, 0.0, 0.0])

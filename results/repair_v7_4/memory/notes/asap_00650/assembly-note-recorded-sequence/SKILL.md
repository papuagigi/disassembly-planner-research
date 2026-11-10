---
name: "assembly-note-recorded-sequence"
description: "Assembly-specific guidance based on three successful first-attempt records for this geometry fingerprint."
---
## Triggers

Use this note only when the same assembly geometry fingerprint is recognized. The recorded sequence came from condition B; conditions A and C also reached the goal, with different valid paths.

## Procedure

1. Try the appended **Recorded sequence** in order, checking each proposed removal. It records a complete successful path of 6 required removals.
2. If a step is rejected, stop that path and replan from the current state. Use the successful alternatives in the Evidence section as candidate next steps only when their preceding removals match the current state; the records do not establish that arbitrary steps can be mixed between paths.
3. If the sequence is partial in a future record, execute its committed prefix first, then search from the resulting state. These records do not contain a partial path to extend.
4. At the initial state, avoid repeating directions already rejected for the same part across all three conditions. A rejection is evidence for that recorded check, not a proof that the direction is impossible in every later state.

## CODE application

Start with the appended sequence as the candidate path. If a check rejects a step, retain the accepted prefix and test a different recorded successful path only from a state whose prior removals match that path. In particular, conditions A and C show alternatives for the first removal and subsequent order; do not splice their suffixes without checking each move.

## GRAPH_DFS application

Prioritize the recorded complete path. If searching from the initial state, try the observed successful first moves: part `1` in `+z` (B or C), or part `3` in `-z` (A). Then follow only the matching successful path. Keep rejected part-direction pairs as state-specific pruning hints; do not globally prune them after removals change the geometry.

## Evidence

- All three first attempts succeeded, each removing all 6 required parts.
- Condition B's complete path is the appended **Recorded sequence**: `1 +z`, `2 +z`, `3 +z`, `0 +z`, `6 +z`, `5 +x`. Its accepted removals occurred at checks 12, 14, 16, 17, 19, and 21.
- Other successful paths: A: `3 -z`, `6 +x`, `2 -z`, `1 -x`, `0 +z`, `5 -z`; C: `1 +z`, `6 +z`, `5 -z`, `2 +z`, `3 +z`, `0 -z`.
- At the initial state, parts `0` and `6` had five rejected directions in at least one condition (B and A, respectively). Part `0` also had five rejected directions in C. Their successful later removals show state-dependent access: part `0` was removed after `1,2,3` in B (and after `3,6,2,1` in A); part `6` after `1,2,3,0` in B, after `1` in C, and after `3` in A.
- `+y` was rejected for parts `0,1,2,3,5,6` across the records. Its world vector is `[0.0, 0.0, 1.0]`. It never succeeded. Other recorded rejected labels and vectors: `+x` = `[-1.0, 0.0, 0.0]` was rejected for parts `0,1,5,6`; `-x` = `[1.0, 0.0, 0.0]` for `0,1,6`; `-z` = `[0.0, -1.0, 0.0]` for `0,1,5`; `-y` = `[0.0, 0.0, -1.0]` for `0,5`. Each of these labels did succeed for at least one part, so they are not globally failed directions. World `+z` is `[0.0, 1.0, 0.0]` and succeeded repeatedly.
- Checks and elapsed time: A used 37 checks / 207 seconds; B 21 / 205 seconds; C 26 / 137 seconds. A and B consumed about 205 seconds despite relatively few checks, indicating substantial wall time per check in these runs. The records give no per-check durations or explicit search-loop trace, so they do not identify a particular slow check or prove that a six-direction sweep caused the delay.

## Limits

These are planner first-attempt records, not reference solutions. They establish successful paths and observed rejections only for the recorded conditions and states. They do not prove that rejected directions are geometrically impossible, explain timing costs, or guarantee that a path will be accepted under a changed condition or geometry.

## Recorded sequence

Source: first-attempt condition B, complete success, 6 of 6 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `1` direction `+z` (world [0.0, 1.0, 0.0])
2. part `2` direction `+z` (world [0.0, 1.0, 0.0])
3. part `3` direction `+z` (world [0.0, 1.0, 0.0])
4. part `0` direction `+z` (world [0.0, 1.0, 0.0])
5. part `6` direction `+z` (world [0.0, 1.0, 0.0])
6. part `5` direction `+x` (world [-1.0, 0.0, 0.0])

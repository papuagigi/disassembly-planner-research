---
name: "assembly-note-upward-and-sideways-disassembly"
description: "First-attempt guidance for the exact assembly geometry, based on three recorded successful paths."
---
## Triggers

Use this note only when the geometry fingerprint matches this assembly. The records include three successful first attempts, each removing all 12 required parts.

## Procedure

Start by following the host's **Recorded sequence** exactly: remove each listed part in order using its listed direction. Condition A completed this path in 12 checks. If a step is rejected, stop replaying that path at the rejected step and try the other observed complete path: condition B's sequence removes parts in alternating `+x` and `-x` directions. If the host sequence is partial in a future record, replay its committed prefix, then use the observed complete paths to guide the next attempt; do not assume an unrecorded continuation.

The records do not identify which parts were blocked in many directions at the start. They show that condition C rejected `-y` for every part, then accepted every part in `+y` order. This supports avoiding `-y` as a general direction here, but does not establish that any specific part was blocked in many directions initially.

## CODE application

For CODE, prioritize the recorded complete sequence as the initial candidate path. If a transition fails, resume from the last accepted state and try the condition B ordering and directions, checking each action before committing it. The records provide no algorithm-specific CODE behavior, so this is a path recommendation only.

## GRAPH_DFS application

For GRAPH_DFS, use the successful `+y` path as the first branch ordering. Avoid spending branches on `-y`, which was rejected for all 12 parts in condition C. If that branch is unavailable or rejected, try condition B's recorded alternating side directions. The records do not show search-tree behavior, so this guidance does not establish a GRAPH_DFS-specific performance effect.

## Evidence

- Condition A: 12/12 removals, 12 checks, 35 seconds. Its committed path is the host's Recorded sequence.
- Condition B: 12/12 removals, 12 checks, 54 seconds. Its complete path was `4 +x`, `10 -x`, `9 -x`, `3 +x`, `8 -x`, `5 +x`, `2 +x`, `11 -x`, `6 +x`, `12 -x`, `7 -x`, `1 +x`.
- Condition C: 12/12 removals, 24 checks, 37 seconds. It accepted `+y` for all parts and rejected `-y` for all parts. The committed order was `1, 10, 11, 12, 2, 3, 4, 5, 6, 7, 8, 9`.
- Direction labels map to world vectors as recorded: `+y` = `[0, 0, 1]` (up), `-y` = `[0, 0, -1]`, `+x` = `[-1, 0, 0]`, and `-x` = `[1, 0, 0]`. `+z` = `[0, 1, 0]` and `-z` = `[0, -1, 0]`.
- The only direction label with recorded failures is `-y` (world `[0, 0, -1]`), rejected for every part in C. No failures were recorded for other labels. No `+z` or `-z` actions appear in accepted paths.

## Limits

All attempts succeeded, so there is no deepest failed state or untested-action recommendation supported by these records. The records do not report initial per-part directional checks, unstable checks, broad six-direction sweeps, or repeated loops; do not infer that these occurred or identify specific initially blocked parts. Conditions A, B, and C differ in their recorded outcomes, but the records do not explain their setup differences. These are planner first-attempt observations, not a reference solution or proof that the paths will always be accepted.

## Recorded sequence

Source: first-attempt condition A, complete success, 12 of 12 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `9` direction `+y` (world [0.0, 0.0, 1.0])
2. part `8` direction `+y` (world [0.0, 0.0, 1.0])
3. part `7` direction `+y` (world [0.0, 0.0, 1.0])
4. part `6` direction `+y` (world [0.0, 0.0, 1.0])
5. part `5` direction `+y` (world [0.0, 0.0, 1.0])
6. part `4` direction `+y` (world [0.0, 0.0, 1.0])
7. part `3` direction `+y` (world [0.0, 0.0, 1.0])
8. part `2` direction `+y` (world [0.0, 0.0, 1.0])
9. part `12` direction `+y` (world [0.0, 0.0, 1.0])
10. part `11` direction `+y` (world [0.0, 0.0, 1.0])
11. part `10` direction `+y` (world [0.0, 0.0, 1.0])
12. part `1` direction `+y` (world [0.0, 0.0, 1.0])

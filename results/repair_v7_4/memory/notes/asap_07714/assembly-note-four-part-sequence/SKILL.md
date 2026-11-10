---
name: "assembly-note-four-part-sequence"
description: "Assembly-specific guidance from three successful first-attempt records for this geometry fingerprint."
---
## Triggers

Use this note only when the planner identifies the same assembly geometry fingerprint. The direction labels are planner names; use the recorded world vectors when interpreting them.

## Procedure

Start by replaying the host-provided **Recorded sequence** in order: remove part `1` along `+z`, then part `2` along `-y`, part `3` along `-y`, and part `0` along `+y`. The sequence is a complete path that succeeded in condition C.

Check each action before committing it. If a step is rejected, do not keep repeating that part-direction pair. Resume from the current assembly state and try the corresponding successful path from condition A or B, where it fits the remaining parts and state. Those paths also completed all four removals:

- Condition A: parts `1`, `2`, `3`, `0`, each along `-z`.
- Condition B: part `1` along `+z`; parts `2` and `3` along `-y`; part `0` along `+y`.

If the planner has only a partial path, retain its committed removals and use the successful records to guide the remaining order. A part that was rejected at the start may become removable after earlier parts leave; re-check the next action in the resulting state rather than treating a starting-state rejection as permanent.

## CODE application

Try the recorded condition C sequence first, checking one action at a time. If its next action is rejected, use condition B's corresponding order and directions as an alternative. Condition A supplies another complete fallback: remove parts `1`, `2`, `3`, then `0`, all with label `-z` (world `[0.0, -1.0, 0.0]`). Avoid a broad six-direction sweep: these records contain complete paths, so begin with those known actions.

## GRAPH_DFS application

Seed the search with the successful recorded path and preserve its order. If a branch is rejected, backtrack to the most recent state where an alternative recorded continuation is applicable. In particular, conditions B and C agree on the complete order and directions, while condition A provides a second path with the same part order. Do not prune a part-direction action solely because it failed in the initial state: the records show successful removals as the assembly changes.

## Evidence

All three first attempts reached the goal and removed all 4 required parts. Condition C completed in 12 checks and 22 seconds; its committed sequence is the host-provided Recorded sequence. Condition A completed in 14 checks and 18 seconds with all four parts removed along `-z`. Condition B completed in 22 checks and 51 seconds with the same order as C.

At the start, the records show rejected directions for:

- Part `1`: `-x` in A, B, and C; additionally `+y` in B and C, and `-y` in C.
- Part `2`: `-x` in A, B, and C; additionally `+y` and `+z` in B.
- Part `3`: `-x` in A, B, and C; additionally `+z` in B.
- Part `0`: `-x` in A, B, and C; additionally `+y`, `+z`, `-y`, and `-z` in B.

Condition B's accepted removals show parts becoming removable as preceding parts leave: part `1` at check 10, part `2` at check 18 after part `1`, part `3` at check 20 after part `2`, and part `0` at check 22 after part `3`. Condition C records the same order at checks 4, 7, 10, and 12. These are observed check numbers, not proof that every listed rejection occurred before the first removal.

The label `-x`, world `[0.0, 0.0, 1.0]`, was rejected for every part in all three attempts. No other label was rejected for every part across all three records. Condition A's `-z` actions all succeeded; in B and C, `-y` and `+y` succeeded for some parts despite rejections of those labels elsewhere.

Condition B took the most checks and elapsed time (22 checks, 51 seconds). There is no recorded per-check duration, so the records do not identify a particular slow or unstable check. The record shows no explicit repeated-loop or six-direction-sweep log; avoid those strategies because the successful paths already provide targeted actions.

## Limits

These records describe three first attempts under conditions A, B, and C. They establish successful paths and observed rejections in those episodes, but do not establish that a rejected action is impossible in every later state, or that a successful path will always be accepted on replay. No attempt failed, so there is no failed deepest state from which to infer additional untested actions or blockers.

## Recorded sequence

Source: first-attempt condition C, complete success, 4 of 4 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `1` direction `+z` (world [0.0, 1.0, 0.0])
2. part `2` direction `-y` (world [1.0, 0.0, 0.0])
3. part `3` direction `-y` (world [1.0, 0.0, 0.0])
4. part `0` direction `+y` (world [-1.0, 0.0, 0.0])

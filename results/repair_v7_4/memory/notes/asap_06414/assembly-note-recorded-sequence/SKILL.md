---
name: "assembly-note-recorded-sequence"
description: "Assembly-specific guidance based only on the three first-attempt planner records for this geometry fingerprint."
---
## Triggers

Use this note only when the same assembly geometry fingerprint is encountered. The recorded sequence comes from condition B and completed all five required removals.

## Procedure

First replay the appended **Recorded sequence** in order: parts `1`, `2`, `3`, `4`, `5`, each in direction `+y`. If a step is rejected, keep the already committed removals, then recheck the remaining parts and try `+y` again as the assembly state has changed. Condition C rejected `-y` for every part before accepting the same `+y` sequence; do not treat those `-y` rejections as evidence against `+y`.

If the sequence is unavailable or cannot be completed, condition A provides another complete path: part `3` `+x`, part `2` `-x`, part `4` `+x`, part `5` `-x`, then part `1` `+y`. Recheck removability after each accepted removal rather than repeating broad direction sweeps.

## CODE application

Use the recorded sequence as the initial ordered removal plan. After each accepted removal, update the assembly state and continue with the next listed part. If a listed move fails, retain the successful prefix and probe the next recorded move against the new state before switching to condition A's alternate path.

## GRAPH_DFS application

Prioritize the condition B branch: successive `+y` removals of parts `1` through `5`. Condition C shows that a `+y` path succeeds even after early `-y` checks fail. If search explores alternate branches, condition A's successful order is a grounded fallback. Avoid revisiting equivalent states through repeated `-y` attempts.

## Evidence

- Condition B succeeded in 5 checks and 29 seconds, removing all five parts in `+y` order `1, 2, 3, 4, 5`, with no rejected directions recorded.
- Condition C succeeded in 13 checks and 31 seconds with the same removal order and direction. It rejected `-y` for all five parts; part `1` was accepted at check 6, then parts `2`–`5` at checks 10–13.
- Condition A also succeeded, in 10 checks and 30 seconds: `3 +x`, `2 -x`, `4 +x`, `5 -x`, `1 +y`. At the start it recorded rejections for part `1` in `+x` and `-x`, part `2` in `+x`, and part `5` in `+x`; later it removed parts `2` and `5` in `-x` after preceding removals. Thus those directions became usable for those parts as the state changed.
- The only direction label rejected in every recorded attempt where it was tried was `-y`. Its world vector was approximately `[5.67394e-06, -0.00232631, -0.99999729]`, nearly world-down. `+y` was approximately `[-5.67394e-06, 0.00232631, 0.99999729]`, nearly world-up. Condition A's `+x` and `-x` labels map approximately to world `-x` and world `+x`, respectively.
- Conditions A and C spent checks on rejected directions before succeeding. Condition C's four checks before its first acceptance and four checks between its first and second acceptances show the cost of unproductive probes. No record identifies individual check latency, so slow or unstable checks cannot be singled out. The recorded episodes do not show a repeated loop.

## Limits

These are first-attempt planner records, not reference solutions. Rejection lists only report directions actually tried; the records do not establish outcomes for untried directions. The three conditions differ in their recorded checks and ordering, but the data do not explain what condition changes. The recorded sequence is a successful observed path for this fingerprint, not a guarantee that every future planner state will accept every step.

## Recorded sequence

Source: first-attempt condition B, complete success, 5 of 5 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `1` direction `+y` (world [-0.0, 0.002, 1.0])
2. part `2` direction `+y` (world [-0.0, 0.002, 1.0])
3. part `3` direction `+y` (world [-0.0, 0.002, 1.0])
4. part `4` direction `+y` (world [-0.0, 0.002, 1.0])
5. part `5` direction `+y` (world [-0.0, 0.002, 1.0])

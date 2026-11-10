---
name: "assembly-note-six-part-sequence"
description: "First-attempt records for this six-part assembly show three complete successful removal paths and identify directions to avoid."
---
## Triggers

Use this note only when the planner sees this same assembly geometry fingerprint. The records identify parts by ids `0`–`5` and direction labels whose world vectors are listed below.

## Procedure

Start with the appended **Recorded sequence**. It is condition A’s complete successful path, with 6 of 6 parts removed. Check each listed part and direction in order. If a step is rejected, do not assume the rest of the sequence still applies: try a different recorded complete path from condition B or C, respecting its order, or resume from the current state using the successful transition evidence below. If the available path is partial, continue from its deepest committed state; only try a removal when its direction is supported by evidence at that state. A rejection in one state does not establish that the direction will fail after other parts are removed.

At the initial state, repeated rejections show that `5` and `4` were blocked in several directions: both rejected `+x`, `+y`, and `-z` in A; B also records `5` rejecting `-z` and `4` rejecting `-z`. Part `1` was especially constrained in B, rejecting all six labels. The records do not give a complete per-state direction map, so avoid inferring that a rejected direction stays blocked after a removal.

Successful removals demonstrate these later opportunities:

- Remove `2` along `+x` first in A; B also succeeds with `2` along `+x` after removing `0`.
- In A, after `2`, remove `5` along `-x`, then `4` along `-x`.
- In B, `4` becomes removable along `-x` after `0`, `2`, and `3` have been removed.
- Part `1`, which rejected `+x` in B, succeeds along `-x` late in B after `0`, `2`, `3`, and `4`; A instead removes `1` along `+x` last, after `2`, `5`, `4`, `3`, and `0`.
- Condition C shows another successful route: after removing `0` along `+x`, remove `2` and `5` along `-z`, then `4` along `-x`, `3` along `+x`, and `1` along `-x`.

Prefer the appended sequence first because it is a complete path from the recorded attempts. If it fails, the B and C orders are also observed complete paths, not guarantees for every planner state or run.

## CODE application

Try the appended sequence as the ordered candidate path. If CODE proposes a direction rejected at the current state, discard or defer that candidate and consider a recorded successful transition that matches the current remaining-part state. In particular, do not rule out `-x` for `4` or `1` merely because other directions were rejected earlier; both succeed in B after prior removals. Avoid restarting broad six-direction sweeps when a successful ordered path is available.

## GRAPH_DFS application

Use the appended path as the first branch. If a branch fails, backtrack to the nearest state with another recorded successful continuation: B’s order (`0 +x`, `2 +x`, `3 +x`, `4 -x`, `1 -x`, `5 -x`) or C’s order (`0 +x`, `2 -z`, `5 -z`, `4 -x`, `3 +x`, `1 -x`). Preserve each path’s order; the evidence does not prove that arbitrary interleavings work. Treat rejected directions as state-specific observations, not permanent graph constraints.

## Evidence

All three first attempts succeeded, each removing all 6 required parts:

- A: 16 checks, 29 seconds. Its complete path is copied in the appended **Recorded sequence**.
- B: 21 checks, 83 seconds; path: `0 +x`, `2 +x`, `3 +x`, `4 -x`, `1 -x`, `5 -x`.
- C: 36 checks, 89 seconds; path: `0 +x`, `2 -z`, `5 -z`, `4 -x`, `3 +x`, `1 -x`.

Across the records, label `-z` was rejected at least once for every part: `2`, `5`, `4`, `3`, `0`, and `1`. This is not a universal prohibition: C successfully removes `2` and `5` along `-z` after `0` is removed. Label `+x` was rejected for `5`, `4`, and `1` in recorded states; `+y` was rejected for `5`, `4`, and `1`; `-y` was rejected for `1`. No record shows a rejection for `-x` on any part. Do not treat labels with no recorded rejection as guaranteed successes.

World vectors from the records (rounded to three decimals) are: `+x` `[-1.000, -0.001, -0.000]`; `-x` `[1.000, 0.001, 0.000]`; `+y` `[-0.001, 0.991, 0.132]`; `-y` `[0.001, -0.991, -0.132]`; `+z` `[0.000, 0.132, -0.991]`; `-z` `[0.000, -0.132, 0.991]`. Thus the label `+z` points mostly downward in world coordinates, and `-z` points mostly upward. No label was shown to fail on every attempt or in every state; only the stated per-part rejections are supported.

Checks and time varied substantially: A completed in 16 checks and 29 seconds, while B and C took 83 and 89 seconds. B records five rejected directions for part `1`; C records many rejections across parts before completion. The records provide totals and rejection lists, but do not identify check duration, unstable checks, or whether a broad sweep or loop caused the elapsed time. Use the successful paths to reduce unnecessary direction probing, but do not attribute the extra time to a specific cause from these records alone.

## Limits

These are planner first-attempt records, not reference solutions. They establish three successful paths and state-specific accepted or rejected checks. They do not identify exact blocker geometry, guarantee repeatability, establish a universal blocked direction, or explain the source of elapsed time. The appended block is the host-provided verbatim path; this note refers to it without replacing it.

## Recorded sequence

Source: first-attempt condition A, complete success, 6 of 6 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `2` direction `+x` (world [-1.0, -0.001, -0.0])
2. part `5` direction `-x` (world [1.0, 0.001, 0.0])
3. part `4` direction `-x` (world [1.0, 0.001, 0.0])
4. part `3` direction `+x` (world [-1.0, -0.001, -0.0])
5. part `0` direction `+x` (world [-1.0, -0.001, -0.0])
6. part `1` direction `+x` (world [-1.0, -0.001, -0.0])

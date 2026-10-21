---
name: "assembly-note-tilted-y-release"
description: "Assembly-specific guidance for replaying the recorded successful removal path and handling rejected steps."
---
## Triggers

Use this note only when the geometry fingerprint matches this assembly.

## Procedure

Start by attempting the appended **Recorded sequence** in order, one action at a time. Treat each accepted removal as the next state transition. If a step is rejected, keep the already accepted prefix and try the other successful orders observed in the records: parts `1` and `2` can exchange order around part `4` (`1 → 2 → 4` in A/B; `1 → 4 → 2` in C). Parts `5` through `8` were all removed in direction `-y`, with some order variation. Retry part `0` only after parts `1, 2, 4, 5, 6, 7, 8` are removed; its recorded final direction differs by attempt (`-y` in A, `+x` in B/C), so check both at that state if needed.

If the host supplies a partial sequence instead, replay its recorded prefix first. On rejection, do not repeat the same rejected action in the same state; try a direction that succeeded for that part in another recorded path, or make progress on a different part whose recorded prerequisites have been cleared. Re-evaluate removability after every accepted removal.

At the initial state, parts `1`, `2`, `5`, `6`, `7`, and `8` repeatedly rejected the four labels `+x`, `+y`, `+z`, `-x` in condition B; part `0` rejected all six labels in A/B/C. Part `4` rejected `+x` and `+y` in B and `-x` in C. These are observed initial-state rejections, not proof that every unrecorded action is impossible. Later, parts `1` and `2` became removable along `-y`, part `4` along `+z`, and parts `5`–`8` along `-y`; part `0` became removable only at the end of successful paths.

Direction labels map to these world vectors: `+x` = [0.987, 0, 0.160], `-x` = [-0.987, 0, -0.160], `+y` = [0.160, 0, -0.987], `-y` = [-0.160, 0, 0.987], `+z` = [0, 1, 0], `-z` = [0, -1, 0]. The labels `+y` and `-z` never appear as accepted directions in any attempt. `+x` was accepted for part `0` in B and C, `-y` was accepted for part `0` in A, and `+z` was accepted for part `4` in all three attempts; do not treat any of those labels as globally impossible.

## CODE application

Use the Recorded sequence as the preferred candidate action order and validate each move with the planner. If a move fails, preserve the accepted prefix and update the state before selecting a fallback. Avoid broad six-direction sweeps on already blocked initial parts: the records show all-six rejection for part `0`, while its successful directions appeared only after the other removals.

## GRAPH_DFS application

Seed the search with the successful A path. For branch generation, include the observed order swap `1 → 4 → 2` and the alternative final move for part `0` (`+x` as well as `-y`). Avoid cycling through the same rejected part-direction-state combination. Recompute candidate actions after each removal so newly available moves are not missed.

## Evidence

All three first attempts succeeded, each removing all 8 required parts. Condition A completed in 54 checks and 135 seconds with path `1(-y), 2(-y), 4(+z), 5(-y), 6(-y), 7(-y), 8(-y), 0(-y)`. B completed in 76 checks and 188 seconds; C in 68 checks and 228 seconds. Across all successes, parts `1`, `2`, `5`, `6`, `7`, and `8` were removed along `-y`, and part `4` along `+z`; part `0` used `-y` in A and `+x` in B/C. The label `+y` was rejected for part `1` in C and for part `0` in all attempts; `-z` was rejected for parts `2` and `8` in C and part `0` in all attempts. Neither label was accepted in the recorded attempts.

## Limits

These are first-attempt planner records, not reference solutions. Rejections are tied to the recorded state and do not establish impossibility in another state. The records identify successful orders and tested directions but do not provide per-check durations, so the elapsed totals cannot identify individual slow checks. No attempt failed or ended partial, so there is no observed deepest partial state or verified untested action from which to propose a recovery.

## Recorded sequence

Source: first-attempt condition A, complete success, 8 of 8 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `1` direction `-y` (world [-0.16, 0.0, 0.987])
2. part `2` direction `-y` (world [-0.16, 0.0, 0.987])
3. part `4` direction `+z` (world [0.0, 1.0, 0.0])
4. part `5` direction `-y` (world [-0.16, 0.0, 0.987])
5. part `6` direction `-y` (world [-0.16, 0.0, 0.987])
6. part `7` direction `-y` (world [-0.16, 0.0, 0.987])
7. part `8` direction `-y` (world [-0.16, 0.0, 0.987])
8. part `0` direction `-y` (world [-0.16, 0.0, 0.987])

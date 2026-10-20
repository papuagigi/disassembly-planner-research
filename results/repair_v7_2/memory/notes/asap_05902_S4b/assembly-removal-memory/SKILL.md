---
name: "assembly-removal-memory"
description: "First-attempt removal guidance for this assembly fingerprint, including accepted moves, failed directions, and search costs."
---
## Triggers

Use this note only when the planner sees the same assembly geometry fingerprint. Direction labels use the recorded world vectors: `+x` = `[1,0,0]`, `-x` = `[-1,0,0]`, `+y` = `[0,0,-1]`, `-y` = `[0,0,1]`, `+z` = `[0,1,0]`, and `-z` = `[0,-1,0]`.

## Procedure

For the successful A run, replay the accepted removal order:

1. `11 -z`
2. `2 +z`
3. `8 +z`
4. `10 -z`
5. `9 -z`
6. `6 +z`
7. `7 -z`
8. `0 +z`
9. `1 -z`
10. `3 -z`
11. `5 -z`

This sequence removed all 11 required parts in 81 checks. The accepted check numbers were 3, 5, 7, 15, 17, 26, 71, 73, 76, 79, and 81 respectively. Treat the order as the observed successful sequence; intervening accepted moves for part 3 are discussed below.

At the start, parts `0`, `1`, `5`, `7`, and `9` were rejected in all six directions in A. Parts `2`, `8`, `10`, and `11` had `-y` rejected but were accepted later in one direction each. Part `6` had `+x` and `-y` rejected, and was accepted `+z`. Part `3` had `+x`, `+y`, `-x`, and `-y` rejected, but `-z` was accepted.

Do not spend an opening sweep on every direction for the initially blocked parts. Condition B spent checks on broad rejection lists and removed only three parts before its 900-second budget ended. In A, several parts initially rejected in every direction became removable later, so defer them and retry after the early accepted removals rather than treating initial rejection as permanent.

## CODE application

Try the A sequence directly as the next candidate procedure. Preserve its recorded order and directions. If an attempted move fails in the current state, continue the search rather than concluding that the part is permanently blocked: the records show successful later moves for parts that had six-direction rejection lists at the start.

Avoid repeating `7 +z` or `6 -z` as a preferred move. They appeared in B and C attempts, but neither is part of the complete A sequence; B later accepted `7 -z` and `6 -z` only after many checks, while C accepted `7 +z` and `6 -z` without completing. Evidence does not establish these as globally impossible, only that the successful full sequence uses different directions for those parts.

## GRAPH_DFS application

Prioritize the known successful edges in this order: `11 -z`, `2 +z`, `8 +z`, `10 -z`, `9 -z`, `6 +z`, `7 -z`, `0 +z`, `1 -z`, `3 -z`, `5 -z`. Use the successful prefix to guide branch ordering and avoid spending the wall-time budget on exhaustive direction sweeps for parts that the records show as initially blocked.

Part `3` has an unusual history in A: accepted `-z` at checks 41 and 79, and accepted `+z` at check 66, while the final sequence lists its successful removal once at check 79. The records do not explain why earlier accepted entries did not appear in the final removal sequence. Do not infer that these entries represent three distinct permanent removals; use the final sequence for the known completion order and treat the earlier entries as state-dependent search events.

## Evidence

- A succeeded: `goal_reached`, 81 checks, 11 of 11 removed, 684 seconds. Its final removal sequence is the 11-move procedure above.
- B exhausted its 900-second budget after 124 checks and 3 of 11 removals. It accepted `1 +z`, `6 +z`, and `7 +z` early, then logged repeated `7 -z` and `6 -z` acceptances at checks 92–120.
- C exhausted its 900-second budget after 100 checks and 5 of 11 removals. It accepted `6 -z`, `7 +z`, then `1 -z` and `1 +z`, followed by `2 +z`, `10 -z`, and `11 -z`; its final sequence lists five removals.
- All three records show repeated attempts or acceptances that do not correspond one-to-one with the final removal sequence. Check counts and accepted-event lists are therefore search history, not a simple count of distinct removed parts.

## Limits

Only first-attempt planner records were provided; there are no reference solutions or geometry details. A is the sole complete run. The B and C rejection lists do not give a reliable complete map of failed directions at the initial state, because their recorded accepted moves conflict with the apparent scope of those lists. The observations support prioritizing A's sequence, but do not prove alternate directions impossible or establish why B and C diverged.

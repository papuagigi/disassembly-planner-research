---
name: "assembly-note-upward-removal-sequence"
description: "Records the successful upward removal order and cautions against repeating rejected directions from the same assembly."
---
## Triggers

Use this note only when the same assembly geometry fingerprint is recognized.

## Procedure

Start with the appended **Recorded sequence** and attempt its committed steps in order: parts `1`, `2`, `3`, then `4`, each along `+z` (world `[0, 0, 1]`). Condition B completed all four removals in four checks, and condition C independently recorded the same sequence in four checks.

If a step is rejected, keep the already accepted prefix and re-evaluate the rejected part in the resulting assembly state. Do not assume its start-state result still applies after earlier removals. If the supplied sequence is partial in a future record, replay that prefix first, then search from its deepest accepted state for remaining parts and directions; this assembly's records contain a complete successful path, so no untested-action claim is needed here.

At the start, condition A rejected `+x`, `+y`, `-x`, and `-y` for every part. It later removed every part along `+z`, in order `1` through `4`. Treat those horizontal rejections as evidence about the initial state only; the recorded successful path is the actionable evidence.

## CODE application

Use the appended sequence directly as the first candidate path. Preserve its order and `+z` direction. If a step fails, retain the accepted prefix and retry planning from the updated state rather than restarting broad direction sweeps.

## GRAPH_DFS application

Seed the search with the recorded path. If search is needed after a rejection, start at the deepest accepted prefix and prioritize the next recorded `+z` removal. Do not prune a part solely because its horizontal directions failed before earlier removals.

## Evidence

- Condition B: success, 4/4 removals, 4 checks, 22 seconds; accepted parts `1`–`4` along `+z` at checks 1–4.
- Condition C: success, 4/4 removals, 4 checks, 18 seconds; same accepted order and directions at checks 1–4.
- Condition A: success, 4/4 removals, 44 checks, 39 seconds; same upward order, accepted at checks 17, 30, 39, and 44. For each part, `+x`, `+y`, `-x`, and `-y` were rejected.
- The only recorded accepted direction is `+z`, world vector `[0, 0, 1]`. No direction label was rejected in all attempts: `-z` was not tried, while the horizontal labels were rejected only in condition A.

## Limits

These are planner first-attempt records, not a reference solution or proof that unrecorded directions are impossible. The records do not identify the reason for any rejection or give per-check timing, so they do not establish which individual checks were unstable or slow. Condition A used many checks before success; conditions B and C show that broad initial sweeps are unnecessary when the recorded path is accepted.

## Recorded sequence

Source: first-attempt condition B, complete success, 4 of 4 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `1` direction `+z` (world [0.0, 0.0, 1.0])
2. part `2` direction `+z` (world [0.0, 0.0, 1.0])
3. part `3` direction `+z` (world [0.0, 0.0, 1.0])
4. part `4` direction `+z` (world [0.0, 0.0, 1.0])

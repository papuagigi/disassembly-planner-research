---
name: "assembly-note-upward-removal"
description: "First-attempt guidance for this exact assembly fingerprint, based only on the planner’s recorded attempts."
---
## Triggers

Use this note only when the planner identifies the same assembly geometry fingerprint. The part ids and direction labels below refer to these records.

## Procedure

Start by following the appended **Recorded sequence** in order, checking each proposed removal against the current assembly state. It is the complete successful path from condition A. If a step is rejected, do not assume the later steps still apply: keep accepted removals, then reconsider the rejected part and current blockers. In particular, condition B rejected part `0` in `+y` before accepting it after parts `1`–`5` were removed.

If the available path is partial, resume from its deepest committed state and use the same progression as a guide: attempt parts `2`, `3`, `4`, `5`, then `1`, then `0`, each in `+y`, rechecking after every accepted removal. The records do not establish that every intermediate ordering works in every planner condition.

## CODE application

Use the recorded path as the initial candidate sequence. Check one removal at a time and update the assembly state after each accepted step. Avoid broad direction sweeps when the candidate `+y` step is available. If a step fails, retry against the changed state rather than replaying the full sequence blindly.

## GRAPH_DFS application

Seed or prioritize the search with the recorded order: `2 → 3 → 4 → 5 → 1 → 0`, using `+y` for each. Treat accepted removals as state changes that can unlock later parts. If the search reaches a different state or a rejection, branch from that state and preserve the successful prefix; the records do not prove that all alternate branches are impossible.

## Evidence

All three first attempts succeeded, each removing all 6 required parts. Condition A completed in 6 checks and 22 seconds, with the appended sequence. Condition B completed in 11 checks and 27 seconds: part `0` in `+y` was rejected once, then accepted after parts `1`, `2`, `3`, `4`, and `5` were removed. Condition C completed in 13 checks and 31 seconds: parts `2`, `3`, `4`, and `5` each had `-y` rejected; accepted removals used `+y` in the order `2`, `1`, `3`, `4`, `5`, `0`.

`+y` maps to world vector `[0.0, 0.0, 1.0]` (world up). The only direction label with recorded rejections is `-y`, world vector `[0.0, 0.0, -1.0]`. No rejections are recorded for `+x`, `-x`, `+z`, or `-z`; those labels are not shown to have been tested. Direction-label mappings are: `+x` = `[-1.0, 0.0, 0.0]`, `-x` = `[1.0, 0.0, 0.0]`, `+z` = `[0.0, 1.0, 0.0]`, and `-z` = `[0.0, -1.0, 0.0]`.

Checks beyond the six accepted removals were spent on rejected attempts: B used five additional checks, including the initial rejection of part `0`; C used seven additional checks, including four `-y` rejections and other unitemized checks. The records give total elapsed time but no per-check timings, so they do not identify slow or unstable checks. No repeated loop or six-direction sweep is documented.

## Limits

These are first-attempt records from conditions A, B, and C, not reference solutions. All attempts succeeded, so no no-success recovery actions are supported by the data. The records show removability only at the observed states: they do not enumerate every initially blocked part or every direction tried. Do not claim that an unrecorded direction never works or that `-y` fails for every part and state.

## Recorded sequence

Source: first-attempt condition A, complete success, 6 of 6 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `2` direction `+y` (world [0.0, 0.0, 1.0])
2. part `3` direction `+y` (world [0.0, 0.0, 1.0])
3. part `4` direction `+y` (world [0.0, 0.0, 1.0])
4. part `5` direction `+y` (world [0.0, 0.0, 1.0])
5. part `1` direction `+y` (world [0.0, 0.0, 1.0])
6. part `0` direction `+y` (world [0.0, 0.0, 1.0])

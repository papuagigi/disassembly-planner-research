---
name: "assembly-note-removal-sequence"
description: "First-attempt evidence and actionable guidance for this exact assembly geometry fingerprint."
---
## Triggers

Use this note only when the planner recognizes the same assembly geometry fingerprint. The recorded sequence below is a first-attempt committed path, not a reference solution.

## Procedure

1. Replay the host-appended **Recorded sequence** in order, checking each removal. Do not change its direction labels or reorder its steps preemptively.
2. If a step is rejected, retain the already accepted prefix and replan from that exact remaining assembly state. Try directions or parts that succeeded in the other recorded successful attempt, but treat their directions as state-dependent; the records do not establish that a rejected action will work at every state.
3. If the available sequence is partial, replay its committed prefix, then continue from the deepest committed state. Avoid restarting broad sweeps from the initial assembly.
4. The records show multiple parts blocked in several directions at the start: condition A rejected parts 8, 6, 2, 5, 3, and 1 in ±x and ±z; condition B rejected parts 7, 4, and 1 in all six labels. These are observations from those attempts, not universal initial-state facts.
5. Removability changed as parts were removed. Condition B removed 9, 8, then 6; condition C removed 7, 8, 1, 2, 0, 4, 5, and 6 in +z, then 9 in -z and 3 in -y. Part 1, for example, was rejected in all six directions in B but later removed in +z in C. Part 3 was rejected in +x, +z, and -x in C's checks, then removed in -y at the end. Use these as evidence that earlier rejections do not rule out later access.

## CODE application

For CODE, seed its action ordering with the recorded successful sequence. Validate each proposed removal at the current state; after any rejection, preserve the accepted prefix and resume search from that state. Favor the successful direction for the same part when it is currently available, while allowing the other successful path's directions when state changes make them applicable.

## GRAPH_DFS application

For GRAPH_DFS, start at the root with the recorded path as a preferred branch. At a rejected edge, backtrack to the last accepted state and explore alternatives there rather than repeating the same failed edge. Cache or avoid repeating known failed state/action checks where supported; failures are tied to the tested state and should not be generalized to every later state.

## Evidence

Two of three first attempts succeeded. Condition C completed in 29 checks and 578 seconds; its full successful path is copied in the host's Recorded sequence. Condition B completed in 43 checks and 842 seconds with a different path: 9/-z, 8/-z, 6/-z, 7/+z, 5/-z, 3/-z, 2/-z, 0/-z, 4/-z, 1/-z.

Condition A exhausted its wall-time budget after 33 checks and 901 seconds, removing only 0/+z, 9/-z, and 8/-z. Its rejections included six parts tested in four directions (±x and ±z). This is evidence of time spent on broad direction checks and an incomplete search; it does not report per-check durations, so no individual check can be identified as slow or unstable.

Direction labels use these observed world vectors: +x=[1,0,0], -x=[-1,0,0], +y=[0,0,-1], -y=[0,0,1], +z=[0,1,0], -z=[0,-1,0] (rounded from the recorded values). Thus +y and -y are vertical-world directions despite their labels; world +z is not the label +z in these records. No label is shown to have never worked: successful paths use +z, -z, and -y, while +x, -x, +y, and -y had rejections in some states. The rejection logs alone do not establish that any label failed in every tested state.

## Limits

These are three first-attempt records for one geometry fingerprint. They do not include reference solutions, per-check timings, full state-by-state rejection histories, or evidence that any action remains valid after a changed state. The successful sequence is the best direct starting point; alternative sequences are recorded planner outcomes, not guaranteed solutions for a future run.

## Recorded sequence

Source: first-attempt condition C, complete success, 10 of 10 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `7` direction `+z` (world [0.0, 1.0, 0.0])
2. part `8` direction `+z` (world [0.0, 1.0, 0.0])
3. part `1` direction `+z` (world [0.0, 1.0, 0.0])
4. part `2` direction `+z` (world [0.0, 1.0, 0.0])
5. part `0` direction `+z` (world [0.0, 1.0, 0.0])
6. part `4` direction `+z` (world [0.0, 1.0, 0.0])
7. part `5` direction `+z` (world [0.0, 1.0, 0.0])
8. part `6` direction `+z` (world [0.0, 1.0, 0.0])
9. part `9` direction `-z` (world [0.0, -1.0, 0.0])
10. part `3` direction `-y` (world [-0.0, 0.0, 1.0])

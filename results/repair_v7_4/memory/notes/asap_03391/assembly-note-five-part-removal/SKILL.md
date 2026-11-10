---
name: "assembly-note-five-part-removal"
description: "First-attempt guidance for the exact five-part assembly, based on three successful planner runs."
---
## Triggers

Use this note only when the geometry fingerprint matches this assembly. It applies to parts `0`–`4` and the planner’s direction labels and world vectors listed below.

## Procedure

Start with the appended **Recorded sequence**: try its `-y` removals in order, from part `0` through part `4`. Condition B completed all five removals this way. If a step is rejected, keep the already accepted removals and recheck the remaining parts in the new state. Other successful first-attempt paths provide alternatives: condition C removed parts `1`, `0`, `2`, `3`, `4`, all along `+y`; condition A removed `4 +y`, `3 -y`, `0 -y`, `1 +x`, `2 +x`.

At the initial state, many tested directions were rejected: part `0` had rejections in all three conditions; part `3` had four rejected labels in A; and parts `1`, `2`, and `4` each had at least one rejection in every condition. Those rejections did not mean the parts were permanently blocked. The successful paths show that parts `0` and `3` became removable after earlier removals, and that parts `1` and `2` could be removed later in condition A after parts `4`, `3`, and `0`. Use the recorded successful ordering as the evidence-backed way to change the state before retrying a rejected part.

If the planner is using CODE or GRAPH_DFS, see the relevant section below. The records do not identify which search mode produced each condition, so treat the recommendations there as guidance, not as a guaranteed mode-specific recipe.

## CODE application

Prefer the recorded `-y` sequence as the initial candidate path. If CODE rejects a step, use the updated state to try the remaining parts and directions from the other successful paths; do not assume an initial-state rejection rules out a later attempt. The records do not expose CODE’s internal candidate ordering or state handling, so no more specific CODE setting is supported.

## GRAPH_DFS application

Use the recorded path as the first path to validate. If a step fails, continue from the deepest accepted state and try a different remaining-part action, using the successful `+y` path from condition C or the mixed-direction path from condition A as alternatives. The records do not show GRAPH_DFS’s traversal details, so they cannot establish a particular pruning or backtracking strategy.

## Evidence

All three first-attempt conditions reached the goal, removing all five required parts.

- Condition B succeeded in 13 checks and 31 seconds. Its committed path is the appended Recorded sequence. Rejections: part `0` (`+x`, `+y`, `-x`, `-z`); parts `1`–`4` (`-z` each).
- Condition C succeeded in 14 checks and 40 seconds. It removed `1`, `0`, `2`, `3`, `4`, all along `+y`. Rejections: part `0` (`+y`, `-z`); parts `1`–`4` (`-z` each).
- Condition A succeeded in 27 checks and 29 seconds. It removed `4 +y`, `3 -y`, `0 -y`, `1 +x`, `2 +x`. Rejections: part `4` (`+x`, `+z`); part `3` (`+x`, `+y`, `+z`, `-x`); part `0` (`+x`, `+y`, `+z`, `-x`); parts `1` and `2` (`+z` each).

Direction labels are names; their world vectors are: `+x` = `[1, 0, 0]`, `-x` = `[-1, 0, 0]`, `+y` = `[0, -1, 0]`, `-y` = `[0, 1, 0]`, `+z` = `[0, 0, -1]`, `-z` = `[0, 0, 1]`. World `+z` is up. The only direction label rejected in all three conditions is `-z`, world `[0, 0, 1]` (up); avoid spending checks on it. No other label was rejected across every condition.

Condition A used the most checks (27), while B and C completed in 13 and 14 checks. The records do not identify individual check durations or repeated loops, so they do not support claims about slow unstable checks, broad six-direction sweeps, or loop behavior. Elapsed times were 29–40 seconds across the successful runs.

## Limits

These are first-attempt planner records, not reference solutions. They show accepted paths and recorded rejected directions, but do not specify the search mode for each condition, check-level geometry, or why any check took time. All attempts succeeded, so there is no deepest failed state or evidence-backed untested action to recommend.

## Recorded sequence

Source: first-attempt condition B, complete success, 5 of 5 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `0` direction `-y` (world [0.0, 1.0, 0.0])
2. part `1` direction `-y` (world [0.0, 1.0, 0.0])
3. part `2` direction `-y` (world [0.0, 1.0, 0.0])
4. part `3` direction `-y` (world [0.0, 1.0, 0.0])
5. part `4` direction `-y` (world [0.0, 1.0, 0.0])

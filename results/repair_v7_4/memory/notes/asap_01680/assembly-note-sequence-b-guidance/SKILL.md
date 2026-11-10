---
name: "assembly-note-sequence-b-guidance"
description: "Guidance for reusing the recorded successful removal path on this assembly fingerprint."
---
## Triggers

Use this note only when the same assembly geometry fingerprint is detected. The recorded sequence is a successful planner path from condition B.

## Procedure

Start by following the appended **Recorded sequence** in order: remove part `2` along `-y`, then part `1` along `-y`, then parts `3`, `4`, `5`, and `6` along `+x`. Check each proposed action before committing it. If a check rejects an action, stop following the remaining sequence as written; retain the already accepted removals and replan from the current assembly state. If the sequence ends early or the planner cannot finish, continue from the deepest committed state by testing candidate directions there, prioritizing directions that succeeded in the other recorded attempts and avoiding directions repeatedly rejected for that part.

Parts `3` and `4` were rejected in all six directions in condition A and again in condition C, but became removable after parts `2` and `1` were removed: condition B accepted `3` then `4` along `+x`. This is strong evidence to clear `2` and `1` first, then retry those parts along `+x`.

## CODE application

Follow the appended sequence exactly as the initial candidate path. Conditions A and C show that parts `2` and `1` can be removed first along `-y`, followed by part `5` along `+x`; condition B provides the fastest recorded complete path and then removes `3`, `4`, `5`, and `6` along `+x` after the first two removals. Avoid broad direction sweeps when a recorded action is available. If an action fails, re-evaluate only the current state and use the successful alternatives in the evidence below.

## GRAPH_DFS application

Use the recorded order as the first branch: `2/-y`, `1/-y`, `3/+x`, `4/+x`, `5/+x`, `6/+x`. Preserve the committed prefix when backtracking. The records do not establish a universal dependency graph, but they show `2` and `1` are a successful initial pair, and that parts `3` and `4` become removable after that pair is cleared. Prefer `+x` for later parts because it completed the B path with only 11 checks.

## Evidence

- All three attempts succeeded, each removing all 6 required parts. Condition B completed in 11 checks and 39 seconds; A used 32 checks and 45 seconds; C used 42 checks and 105 seconds.
- The complete B sequence is the appended block. In B, `2/-y` was accepted at check 2, `1/-y` at check 3, then `3/+x`, `4/+x`, `5/+x`, and `6/+x` at checks 8–11.
- Conditions A and C also accepted `2/-y`, `1/-y`, and `5/+x`, though their committed final paths differ afterward. Part `6` was temporarily accepted along `+x` in A and C before a later acceptance in a different direction; do not mistake that intermediate acceptance for proof that it was permanently removed then.
- At the start, parts `3` and `4` were blocked in every tested direction in both A and C (all six labels). After `2` and `1` were removed, both were removed along `+x` in B and along `+x`/`-x` in C. This supports retrying them after clearing the initial pair.
- No direction label was rejected in all three attempts for the same part. In A and C, `+y` and `-y` were rejected for part `5`; their world vectors are `+y` = `[0.0, 2.220446049250313e-16, -1.0]` and `-y` = `[0.0, -2.220446049250313e-16, 1.0]`. For part `6`, A and C rejected `+y`, `-y`, and `-z`; C also lists `+z` as rejected despite later accepting it, so treat that rejection as state-specific, not permanent. The vectors are `+z` = `[0.0, 1.0, 2.220446049250313e-16]` and `-z` = `[0.0, -1.0, -2.220446049250313e-16]`. World `+z` is up.
- Wasted work is most evident in C: 42 checks and 105 seconds, including repeated trials of parts `3` and `4` across all six directions and multiple checks on part `6` before its final `+z` removal. A also used 32 checks and repeated checks for part `6`. B reached completion in 11 checks; use that as the efficiency target.

## Limits

These are planner first-attempt records, not reference solutions. Direction rejections are state-dependent: a rejected direction does not prove that the direction can never work after other parts are removed. The records do not give exact initial blocked-direction sets for every part or identify individual check durations, so avoid stronger claims about specific slow checks. All attempts succeeded, so no deepest partial state or untested-action recommendation is available.

## Recorded sequence

Source: first-attempt condition B, complete success, 6 of 6 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `2` direction `-y` (world [0.0, -0.0, 1.0])
2. part `1` direction `-y` (world [0.0, -0.0, 1.0])
3. part `3` direction `+x` (world [1.0, 0.0, 0.0])
4. part `4` direction `+x` (world [1.0, 0.0, 0.0])
5. part `5` direction `+x` (world [1.0, 0.0, 0.0])
6. part `6` direction `+x` (world [1.0, 0.0, 0.0])

---
name: "assembly-note-recorded-path-8c0e"
description: "Assembly-specific guidance based on three first-attempt records for this geometry fingerprint."
---
## Triggers

Use this note only when the planner identifies the same assembly geometry fingerprint. The records show three successful first attempts, each removing all 8 required parts.

## Procedure

Start with the appended **Recorded sequence** and try its steps in order. It is the complete path from condition B: parts `1`, `2`, `5`, `6`, `7`, `8`, and `0` in direction `-y`, then part `4` in direction `+x`.

If a step is rejected, do not assume later steps remain valid: re-check the current assembly state, then use the other successful records as alternate evidence. Conditions A and C both began with removing part `1` along `-y`. A removed part `4` along `+z` second; C removed it along `-z` second. Both then removed part `2` along `-y`, followed by parts `5`, `6`, `7`, and `8` along `-y`, and finally part `0` (A used `-y`; C used `+x`). These are observed successful paths, but the records do not establish that every mixed ordering will work.

At the initial state, parts `0` and `4` were blocked in many directions: condition A rejected all six labels for part `0`, and rejected `+x`, `+y`, `-x`, and `-y` for part `4`; condition C also rejected six directions for part `0`. Do not treat those initial rejections as permanent. Part `0` became removable last in all three successful records: after seven removals in A and C, and after seven in B. Part `4` became removable after part `1` in A and C, and last in B after parts `1`, `2`, `5`, `6`, `7`, `8`, and `0` had been removed.

Direction labels that never worked in any recorded attempt:

- `+y` = world `[0.1600714781, 0.0, -0.9871054781]`? Use the exact vector table below; labels and world axes are not interchangeable.
- `-x` was rejected for parts `0`, `1`, `2`, `4`, `5`, `6`, `7`, and `8` in condition C, and for parts `0` and `4` in A. It has world vector `[-0.9871054781296805, 0.0, -0.1600711561974078]`.
- `+y` has world vector `[0.1600714781296805, 0.0, -0.9871054781296805]`.
- `-z` has world vector `[0.0, -1.0, 0.0]`.

Correction: the records' exact `+y` vector is `[0.1600714781296805, 0.0, -0.9871054781296805]` only if transcribed as supplied; check the source record's vector table when interpreting labels. The supplied table lists `[0.1600714781296805, 0.0, -0.9871054781296805]`? (The table itself gives `[0.1600714781296805, 0.0, -0.9871054781296805]`.)

## CODE application

The successful CODE-like condition A spent 54 checks and 135 seconds. It accepted removals at checks 7, 14, 25, 32, 39, 46, 53, and 54. Its early sweep reached part `0` through all six directions, all rejected, before the final `-y` removal. Avoid repeating a broad six-direction sweep for part `0` at the start; defer it until the other parts are removed, where the records show it can succeed.

## GRAPH_DFS application

The successful GRAPH_DFS-like condition B was the most efficient recorded path: 19 checks and 60 seconds. Its accepted removals came at checks 2, 4, 7, 10, 13, 16, 17, and 19. Prefer its recorded order. Avoid looping on `-y` for parts `0` and `4`: B explicitly rejected that direction for both, then removed `0` along `-y` after six other removals and `4` along `+x` last. The records do not identify the internal cause of rejected checks or establish a general search policy beyond these observations.

## Evidence

The three complete first-attempt paths are: A `1(-y), 2(-y), 4(+z), 5(-y), 6(-y), 7(-y), 8(-y), 0(-y)`; B as in the appended sequence; and C `1(-y), 4(-z), 2(-y), 7(-y), 8(-y), 5(-y), 6(-y), 0(+x)`. Checks and elapsed times: A 54 / 135 s, B 19 / 60 s, C 55 / 199 s. World vectors from the records: `+x` `[0.9871054781296805, 0.0, 0.1600711561974078]`; `-x` `[-0.9871054781296805, 0.0, -0.1600711561974078]`; `+y` `[0.1600711561974078, 0.0, -0.9871054781296805]`; `-y` `[-0.1600711561974078, 0.0, 0.9871054781296805]`; `+z` `[0.0, 1.0, 0.0]`; `-z` `[0.0, -1.0, 0.0]`. The labels `+z` and `-z` therefore point along world up and down, respectively.

## Limits

All three attempts succeeded, so there is no deepest partial state requiring untested-action advice. Direction rejections are reported only where the records explicitly list them; absence from a rejection list does not prove a direction was tried. These records provide no reference solution and no geometric explanation for why checks passed or failed. The recorded sequence is the planner's own successful path, not an independent reference.

## Recorded sequence

Source: first-attempt condition B, complete success, 8 of 8 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `1` direction `-y` (world [-0.16, 0.0, 0.987])
2. part `2` direction `-y` (world [-0.16, 0.0, 0.987])
3. part `5` direction `-y` (world [-0.16, 0.0, 0.987])
4. part `6` direction `-y` (world [-0.16, 0.0, 0.987])
5. part `7` direction `-y` (world [-0.16, 0.0, 0.987])
6. part `8` direction `-y` (world [-0.16, 0.0, 0.987])
7. part `0` direction `-y` (world [-0.16, 0.0, 0.987])
8. part `4` direction `+x` (world [0.987, 0.0, 0.16])

---
name: "assembly-note-upward-y-removal"
description: "Records successful first-attempt removal orders and direction evidence for this exact assembly geometry."
---
## Triggers

Use this note only when the geometry fingerprint matches this assembly.

## Procedure

Start with the appended **Recorded sequence** and try each listed part and direction in order. Its source was a complete first-attempt success: all 8 required parts were removed in 8 accepted checks. If a step is rejected, retain the accepted prefix and resume from the resulting state; the records do not identify rejected directions or establish an alternate continuation. If the sequence is partial, follow its committed prefix, then explore from the deepest reached state rather than restarting blindly. Condition B made no removals and recorded no checks, so it gives no step-level blocker evidence.

The successful condition A sequence shows parts `5`, `3`, `6`, `2`, `0`, `8`, `7`, and `4` each removable along `-y` after the preceding removals in that sequence. Condition C also succeeded: it removed `0`, `2`, `3`, `4`, `5`, and `6` along `-y`, then `7` and `8` along `+x`. These two successful paths show that parts `7` and `8` were removable along `-y` after earlier removals in A, and along `+x` after removals `0`, `2`, `3`, `4`, `5`, and `6` in C. The records do not show which directions were blocked at the initial state or report any rejected direction checks.

## CODE application

Replay the recorded successful sequence as the first candidate path. After a rejected action, preserve the accepted removals and search from that state. If using the alternate successful order as guidance, note that condition C is a separate complete path, not evidence that its ordering will succeed under every planner condition.

## GRAPH_DFS application

Prioritize the recorded action at each matching state. If it is rejected, keep the accepted prefix and branch from the current state; the records support the two complete paths above but provide no rejection map for choosing other branches. Avoid broad six-direction sweeps without evidence: the successful attempts completed with 8 checks each, and no direction rejections were recorded.

## Evidence

- Condition A: success, 8/8 removed, 8 checks, 14 seconds; every action used `-y`.
- Condition C: success, 8/8 removed, 8 checks, 18 seconds; six actions used `-y`, then parts `7` and `8` used `+x`.
- Condition B: no-progress stop, 0/8 removed, 0 checks, 26 seconds.
- Direction labels are planner labels. In the recorded mapping, `-y` is world `[0.0, 0.0, 1.0]` (up), `+x` is `[1.0, 0.0, 0.0]`, and `+y` is `[0.0, 0.0, -1.0]`. No successful path used `+y`, `-x`, `+z`, or `-z`; these labels never worked in the recorded successful actions, but no rejected checks establish that they are impossible.
- The successful attempts show no slow unstable checks or repeated loops: both finished in 8 checks. Condition B consumed 26 seconds without any checks or removals; the records do not explain the delay.

## Limits

These are planner first-attempt records only. They provide no reference solution, rejected-direction data, intermediate blocker map, or evidence that a successful action order transfers across different planner conditions. No attempt was partial, so there is no deepest partial state from which to name promising untested actions or blockers to clear.

## Recorded sequence

Source: first-attempt condition A, complete success, 8 of 8 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `5` direction `-y` (world [0.0, 0.0, 1.0])
2. part `3` direction `-y` (world [0.0, 0.0, 1.0])
3. part `6` direction `-y` (world [0.0, 0.0, 1.0])
4. part `2` direction `-y` (world [0.0, 0.0, 1.0])
5. part `0` direction `-y` (world [0.0, 0.0, 1.0])
6. part `8` direction `-y` (world [0.0, 0.0, 1.0])
7. part `7` direction `-y` (world [0.0, 0.0, 1.0])
8. part `4` direction `-y` (world [0.0, 0.0, 1.0])

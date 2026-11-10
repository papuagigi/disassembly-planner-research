---
name: "assembly-note-first-attempt-removal-path"
description: "Records successful first-attempt removal paths and direction caveats for this assembly fingerprint."
---
## Triggers

Use this note only for the same assembly geometry fingerprint. The appended **Recorded sequence** is a complete first-attempt success from condition C; it is planner evidence, not a reference solution.

## Procedure

1. Try the appended **Recorded sequence** in order, checking each removal against the current assembly state.
2. If a step is rejected, keep the already accepted prefix and replan from that resulting state. Do not assume the rejected direction is impossible in every state: the records show that part `1` was rejected in several directions initially but was removed later by `+x` after other parts were removed.
3. If the sequence is partial in a future record, resume from its deepest committed state. Prioritize actions observed to succeed after the same preceding removals; validate each action before committing it.

Across the attempts, part `0` was rejected in `+x` and `+y` in condition A, yet was removed first in all three successful paths (`+z` in A/C, `-y` in B). Part `1` was rejected in five or six directions at the start in every condition, then removed last by `+x` in all three. Part `4` had `-y` rejected in B but was later removed by `+x`; it was removed by `-z` in C. These are state-dependent observations, not universal direction guarantees.

## CODE application

Start with the appended sequence as the prioritized candidate path. Preserve its order and test the next action in the current state. If a check rejects it, update the state only with committed removals and search from that state. The records support `part 0` as an early removal and `part 1` as a late removal; they do not provide a CODE-specific replay result.

## GRAPH_DFS application

Seed search with the appended path. Avoid spending checks on `part 1` early: its initial directions were broadly rejected in all conditions, while `+x` succeeded after parts `0`, `3`, and `4` were removed in every complete path. Direction labels are planner names; use the recorded world vectors below when interpreting them. The records do not provide a GRAPH_DFS-specific replay result.

## Evidence

All three first attempts succeeded, each removing 4 of 4 parts.

- Condition A: 24 checks, 539 seconds; path `0 +z`, `3 +x`, `4 +x`, `1 +x`. Part `1` rejected all six labels initially; part `0` rejected `+x` and `+y`.
- Condition B: 11 checks, 219 seconds; path `0 -y`, `3 -y`, `4 +x`, `1 +x`. Part `1` rejected `+x`, `+z`, `-x`, `-y`, `-z`; part `4` rejected `-y`.
- Condition C: 6 checks, 122 seconds; path `0 +z`, `3 -z`, `4 -z`, `1 +x`. Part `1` rejected `+z` and `-z`.

No direction label failed in every recorded attempt. The per-condition rejected labels and their world vectors are:

- `+x` → [1, 0, 0]: rejected for part `1` in A and B, but later succeeded for part `1` in all three paths; also rejected for part `0` in A.
- `-x` → [-1, 0, 0]: rejected for part `1` in A and B.
- `+y` → [0, 0, -1]: rejected for part `1` in A and B, and part `0` in A.
- `-y` → [0, 0, 1]: rejected for part `1` in A and B and part `4` in B; it succeeded for parts `0` and `3` in B.
- `+z` → [0, 1, 0]: rejected for part `1` in B and C; it succeeded for part `0` in A and C.
- `-z` → [0, -1, 0]: rejected for part `1` in A, B, and C; it succeeded for parts `3` and `4` in C.

The slowest attempt was A (539 seconds, 24 checks). B and C completed with fewer checks and less elapsed time. The records show check counts and total elapsed time, but no per-check durations or explicit sweep/loop trace, so they do not identify which individual checks consumed the wall time or prove that a particular search pattern caused it.

## Limits

These records cover only three first attempts and successful full paths. They do not establish that rejected directions remain blocked after other removals, or that any path is uniquely valid. The supplied vectors show the planner's direction-label mapping; notably, `+y` maps to world -z and `-y` maps to world +z, while world +z is up. No unsuccessful or partial attempt exists here, so there is no deeper partial state from which to recommend untested actions.

## Recorded sequence

Source: first-attempt condition C, complete success, 4 of 4 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `0` direction `+z` (world [0.0, 1.0, 0.0])
2. part `3` direction `-z` (world [0.0, -1.0, 0.0])
3. part `4` direction `-z` (world [0.0, -1.0, 0.0])
4. part `1` direction `+x` (world [1.0, 0.0, 0.0])

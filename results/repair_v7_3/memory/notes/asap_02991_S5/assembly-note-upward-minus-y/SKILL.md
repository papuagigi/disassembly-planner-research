---
name: "assembly-note-upward-minus-y"
description: "Assembly-specific guidance from three successful first-attempt records for this geometry fingerprint."
---
## Triggers

Use this note only when the planner reports the same assembly geometry fingerprint. The planner's direction label `-y` maps to world vector `[0.0, 0.0, 1.0]` (up).

## Procedure

1. Try the host-appended **Recorded sequence** in order, checking each proposed removal and committing accepted steps. It is a complete successful path from condition A.
2. If a step is rejected, stop replaying that path at the rejection. Re-evaluate the current state and try another currently valid `-y` removal among the remaining parts; conditions B and C show that a different order can also succeed. Do not infer that a part is impossible from a rejection in one state.
3. If replay ends early or the recorded path is partial, use the successful alternative order observed in B/C as a fallback: parts `0, 2, 3, 4, 5, 6, 7, 8`, each in direction `-y`. Check each against the current state; this order is evidence from separate runs, not a guaranteed continuation after an arbitrary prefix.
4. Prefer `-y` (world up) for these recorded removals. The records contain no rejected directions, so they do not identify any direction label that never worked.

## CODE application

For CODE, use the appended sequence as the first candidate plan, validating and committing one removal at a time. If an action is rejected, branch from the last committed state and test available `-y` removals rather than replaying the rejected suffix unchanged. The records establish successful orders, but contain no CODE-specific behavior or rejection evidence.

## GRAPH_DFS application

For GRAPH_DFS, seed search with the complete recorded path. If the path is unavailable or a step fails, explore alternate `-y` orders, including the B/C order listed above. Avoid spending checks on a broad six-direction sweep: all 24 recorded removals used `-y`, and no other direction was recorded as accepted or rejected. This is a prioritization suggestion, not proof that other directions are invalid.

## Evidence

- All three first attempts (A, B, C) succeeded: 8 of 8 parts removed, with 8 checks each.
- A's committed order is the host-appended Recorded sequence. B and C both used `0, 2, 3, 4, 5, 6, 7, 8`; all removals used `-y`.
- Across the records, every part ID `0, 2, 3, 4, 5, 6, 7, 8` was removable in direction `-y` at its recorded turn. The records do not show initial blocked directions or the full set of currently available actions at each state.
- Elapsed times were 14 seconds (A), 22 seconds (B), and 18 seconds (C). Each run used exactly eight checks; no slow checks, repeated loops, or rejected proposals are recorded.
- Direction mapping: `+x` = `[1,0,0]`, `-x` = `[-1,0,0]`, `+y` = `[0,0,-1]`, `-y` = `[0,0,1]`, `+z` = `[0,1,0]`, `-z` = `[0,-1,0]`.

## Limits

These are planner first-attempt records, not reference solutions. They show successful complete paths and no rejected directions. They do not establish which parts were blocked in many directions at the start, which directions never work, whether parts become removable because of a particular preceding removal, or a universal ordering constraint. The fallback order is a recorded successful ordering only; validate it against the live state.

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

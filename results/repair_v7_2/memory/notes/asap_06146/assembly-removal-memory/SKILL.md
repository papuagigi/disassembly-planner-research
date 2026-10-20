---
name: "assembly-removal-memory"
description: "Assembly-specific removal guidance derived from the three recorded first attempts."
---
## Triggers

Use this note only when the assembly geometry fingerprint matches this exact assembly. Direction labels refer to world axes: `+x`, `-x`, `+y`, `-y`, `+z`, and `-z`.

## Procedure

Best next attempt: follow condition B's successful sequence, which reached all 14 removals in 53 checks (121 seconds):

1. `12 +z`
2. `13 +z`
3. `11 +z`
4. `14 +z`
5. `10 +z`
6. `9 +z`
7. `5 +z`
8. `1 +z`
9. `3 +z`
10. `8 +x`
11. `2 -x`
12. `6 +x`
13. `7 +x`
14. `4 +z`

These are accepted removals in observed order, not a claim that each is the only valid move at its step. Other successful sequences were recorded: A removed `2 -x, 3 +x, 7 +y, 8 +y, 11 +z, 10 +z, 12 +z, 9 +z, 4 -y, 5 +z, 6 +x, 13 +z, 14 +z, 1 +y`; C removed `11 +z, 14 +z, 1 +z, 7 +y, 3 +x, 10 +z, 12 +x, 13 +z, 2 -x, 8 +y, 9 +z, 6 +x, 5 +z, 4 -y`.

At the start, condition B accepted `12 +z`, `13 +z`, `11 +z`, and `14 +z` immediately on checks 1–4. Prioritize these four before spending checks exploring directions for other parts.

## CODE application

- Try the recorded B sequence first. It is the lowest-check successful attempt in the records.
- At the initial state, check the four immediate `+z` removals in B order: `12`, `13`, `11`, `14`.
- Then continue with B's observed accepted order and directions. Avoid cycling through directions already rejected at the current state; a later state may change what is removable, so treat rejections as state-specific evidence rather than permanent impossibility.
- If following a different sequence, the records support `2 -x`, `3 +x`, `7 +y`, `8 +y`, `11 +z`, `10 +z`, `12 +z`, `9 +z`, `4 -y`, `5 +z`, `6 +x`, `13 +z`, `14 +z`, and `1 +y` as accepted moves in A, and the C sequence above as another complete route.

## GRAPH_DFS application

- Use the B order as the preferred path through the removal-state graph: it is the observed successful route with the fewest checks.
- Preserve the exact direction per observed edge. In particular, B uses `8 +x`, `2 -x`, `6 +x`, and `7 +x` late in the sequence; the successful runs also show that those parts can have other accepted directions under different states.
- If a candidate path stalls, use the alternate accepted sequences from A or C as evidence for alternative state transitions. Do not assume the final-removal sequences from separate conditions can be combined into a single valid path.

## Evidence

All three records reached the goal and removed 14 of 14 parts. Check counts and elapsed times were: A, 225 checks / 637 seconds; B, 53 / 121; C, 83 / 435. B is best on both recorded measures.

Parts with all six directions rejected at the initial state in at least one recorded condition:

- A: `1`, `4`, `5`, `6`, `9`, `10`.
- C: `1`, `4`, `5`, `6`.
- B: no part had all six directions listed as rejected.

Thus `1`, `4`, `5`, and `6` were each blocked in every direction at the start in both A and C, yet were later removed in all successful attempts. Their initial blockage is not permanent. Parts `9` and `10` were blocked in every direction at the start in A, but later removed there as well.

Directions never accepted for a given part across these three successful records (based on all accepted removals and listed rejections):

- `1`: `-x`, `-y`, `-z` (accepted `+y` in A, `+z` in B and C).
- `2`: `+y`, `-y`, `-z` (accepted `-x` in all runs; also `+x` in C).
- `3`: `-x`, `-y`, `-z` (accepted `+x` in A and C, `+z` in B).
- `4`: `-x` (accepted `-y` in A/C, `+z` in B).
- `5`: `-x`, `-y`, `-z` (accepted `+z` in all runs).
- `6`: `-x`, `-y`, `-z` (accepted `+x` in all runs).
- `7`: `-y`, `-z` (accepted `+y` in A/C, `+x` in B).
- `8`: `-x`, `-y`, `-z` (accepted `+y` in A/C, `+x` in B).
- `9`: `-x`, `-y` (accepted `+z` in all runs).
- `10`: `-x`, `-y`, `-z` (accepted `+z` in all runs).
- `11`: `-x`, `-y`, `-z` (accepted `+z` in all runs).
- `12`: `-y`, `-z` (accepted `+z` in A/B, `+x` in C).
- `13`: `-x`, `-y`, `-z` (accepted `+z` in all runs).
- `14`: `-x`, `-y`, `-z` (accepted `+z` in all runs).

There is no direction label that was never accepted for every part: across the assembly, each of the six labels appears in at least one accepted removal. For `4`, `-x` is the only direction never accepted in these records.

Checks are cumulative attempt check numbers. The accepted moves in A occurred as late as checks 101–225; C's final five accepted moves were at checks 59, 76, 79, 81, and 83. This indicates substantial search/check overhead relative to B, especially late in A and C. The records do not identify individual failed checks, so they cannot show exactly which rejected direction checks consumed the time. B also had gaps before accepted removals (`10` at 12, `9` at 20, `5` at 27, `1` at 34, `3` at 41), so even the best route involved some unsuccessful checks.

## Limits

These are observations from only three first-attempt records for this geometry fingerprint. Rejected-direction lists are reported per condition, and the records do not specify the state at each rejection; do not treat them as globally impossible directions. “Never accepted” means absent from all three accepted-removal sequences, not proven geometrically impossible. Check counts and elapsed time are observed outcomes; the cause and exact placement of failed checks are not recoverable from the supplied data.

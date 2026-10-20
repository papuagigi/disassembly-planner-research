---
name: "planner2d-same-assembly-memory"
description: "Checkable removal guidance from three first-attempt runs on this assembly geometry."
---
## Triggers

Apply only when the assembly geometry fingerprint matches this assembly. Direction labels use the planner's recorded world vectors: `+z` = `[0, 1, 0]`, `-z` = `[0, -1, 0]`, `+x` = `[1, 0, 0]`, and `+y` = `[0, 0, -1]`.

## Procedure

Use condition A's complete accepted sequence as the main starting order:

1. `11 -z`
2. `2 +z`
3. `8 +z`
4. `10 -z`
5. `9 -z`
6. `6 +z`
7. `7 -z`
8. `0 +z`
9. `1 -z`
10. `3 -z`
11. `5 -z`

This order reached all 11 required removals. Check the indicated direction first for each part; after every removal, re-check the next part against the current assembly state. If sequence conditions differ, use the accepted directions as candidate hints rather than assuming they are interchangeable across states. Condition C accepted an alternate early order (`2 +z`, `11 +z`, `7 +z`, `8 +z`, `0 +z`, `10 -z`, `9 -z`, `3 +z`, `6 +z`, `5 +x`) but stopped at 10/11 under the time limit; it provides candidates, not a complete procedure.

## CODE application

No CODE-specific records were supplied. Apply the sequence above as candidate checks, recording each result and stopping direction sweeps once the current state confirms a removal or rejects that direction. Do not infer a CODE-specific success from these runs.

## GRAPH_DFS application

No GRAPH_DFS-specific records were supplied. Seed its next search with condition A's complete order and the recorded accepted direction per part. Avoid spending the initial search on directions that were rejected for that part in condition A; re-evaluate only if the assembly state has changed enough to justify a new check.

## Evidence

- Condition A succeeded: 81 checks, 11/11 removed, 684 seconds. Accepted in time order: `11 -z` (check 3), `2 +z` (5), `8 +z` (7), `10 -z` (15), `9 -z` (17), `6 +z` (26), `3 -z` (41), `3 +z` (66), `7 -z` (71), `0 +z` (73), `1 -z` (76), `3 -z` (79), `5 -z` (81). The accepted-removal log contains repeated `3` entries, while the final sequence lists part 3 once; treat the final sequence as the run's removal order and the log as check history, not as proof that part 3 was removed multiple times.
- Condition B exhausted 900 seconds after 135 checks and 2 removals. Its final sequence was `1 +z`, `6 +z`; its accepted-check log also records `7 +z` and `7 -z`, and repeats checks for 1 and 6. This discrepancy means the accepted-check log is not a reliable final removal sequence for B.
- Condition C exhausted 900 seconds after 119 checks and 10 removals. Its final sequence is listed above. Its accepted checks occurred at 23, 29, 52, 67, 78, 90, 94, 101, 114, and 117 respectively. The run did not complete the required 11 removals.
- At the start of A, all six directions were rejected for parts `9`, `0`, `1`, `7`, and `5`. Parts `2`, `8`, `10`, and `11` each had only `-y` rejected; part `6` had `+x` and `-y` rejected; part `3` had `+x`, `+y`, `-x`, and `-y` rejected.
- Across all runs, repeated full-direction failures were common: A rejected all six for `9`, `0`, `1`, `7`, and `5`; B rejected all six for `2`, `0`, `5`, `8`, `3`, `9`, `10`, and `11`; C rejected all six for `1`, `0`, `9`, and `5`. These are run-specific observations, not universal geometric impossibility claims.
- Checks/time were spent on exhaustive direction sweeps for those all-six-rejected parts, and B repeated accepted candidates (`1 +z`, `6 +z`) in its accepted-check log. In A, part 3 had accepted checks at 41 and 66 before the final sequence's `3 -z` at 79; these checks did not correspond to its final-sequence position, so avoid treating that log as a simple sequential trace.
- No direction is shown to never work across the assembly: the runs accepted `+x` for `5` in C, `+z` and `-z` in accepted records, and `+z`/`-z` removals elsewhere. Within a specific recorded run, A rejected `+x` and `+y` for part 3 and all six directions for part 5; B and C have their own part-specific failures as detailed in the records. Treat rejections as state- and run-specific.

## Limits

These notes summarize only the three supplied first-attempt records. They do not establish that a rejected direction is impossible in every assembly state, explain why a direction was blocked, or identify behavior for any named planner beyond the available records. The A accepted-check history has repeated part 3 entries that do not match its final sequence; B's accepted-check history also conflicts with its final removal sequence. Prefer the explicit final sequence for removal order and use accepted-check entries only as evidence that a candidate was accepted at that check. The condition-specific removal orders differ, so the proposed order is a tested starting point, not a guarantee under different search conditions.

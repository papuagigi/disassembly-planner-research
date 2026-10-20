---
name: "assembly-removal-memory"
description: "Assembly-specific removal guidance derived only from the three first-attempt planner records."
---
## Triggers
Use this note only when the planner sees this same assembly geometry fingerprint. Direction labels are the planner's labels; in the recorded world vectors, `+y` points along world `+z`, and `+x` points along world `-x`.

## Procedure
Try the following successful sequence first, checking each removal in order:

1. Part `7` along `+y`
2. Part `10` along `+y`
3. Part `8` along `+y`
4. Part `9` along `+y`
5. Part `1` along `-x`
6. Part `5` along `+x`
7. Part `4` along `+y`
8. Part `6` along `+y`
9. Part `3` along `+x`
10. Part `0` along `+x`

This is the successful sequence from condition B. There is variation across successful runs: condition A removed `8, 10, 9, 3, 4, 6, 5, 7, 1, 0` (directions `+y` for all except `5` and `0`, which were `+x`); condition C removed `7, 1, 8, 9, 10, 4, 5, 6, 3, 0` (with `1` on `-x`, `4` on `+z`, `5` and `3` on `+x`, and the others on `+y`). Treat the B sequence as a tested starting plan, not a proven unique order.

At the start, avoid broad direction sweeps when a part was rejected in most or all six labels in a recorded run:

- Part `0`: all six labels rejected in B, then accepted on `+x` as the final removal in B and C.
- Part `5`: all six rejected in B and C; later accepted on `+x` in all three runs.
- Part `4`: all six rejected in B and C; accepted on `+y` in A and B, and `+z` in C.
- Part `6`: all six rejected in B and C; accepted on `+y` in all three runs.
- Part `1`: all six rejected in C; accepted on `+y` in A, and `-x` in B and C.

For parts `7`, `8`, `9`, and `10`, `+x` and `-x` were rejected in B and C, while `+y` succeeded in every run containing that part's accepted removal. Start with `+y` for these parts.

## CODE application
Apply the same ordered candidate list before launching a broad search. In particular, defer parts `0`, `5`, and `6` until the other accessible removals have changed the assembly: the records show their early six-direction sweeps failed, while later removals succeeded. For part `4`, use `+y` as the first candidate; keep `+z` as a fallback because it succeeded once. For part `1`, try `-x` first based on B and C, with `+y` as the alternative observed in A. Do not retry the directions listed as rejected for `7`–`10` (`+x`, `-x`) unless the assembly state differs materially from the recorded attempts.

## GRAPH_DFS application
Use the B sequence as a preferred depth-first branch: `7/+y → 10/+y → 8/+y → 9/+y → 1/-x → 5/+x → 4/+y → 6/+y → 3/+x → 0/+x`. If a step is blocked, backtrack to another recorded successful ordering rather than enumerating all six directions immediately. Useful order alternatives include moving `1/-x` just after `7/+y` (as in C), placing `4` after `10` with `+z` (C), and removing `8` and `10` before `7` (A). These are observed successful alternatives, but the records do not establish which branch is best under every search implementation.

## Evidence
All three conditions A, B, and C reached the goal and removed all 10 required parts. Accepted removals in time order:

- A: `8/+y` (check 2), `10/+y` (4), `9/+y` (6), `3/+y` (8), `4/+y` (10), `6/+y` (12), `5/+x` (13), `7/+y` (15), `1/+y` (17), `0/+x` (18). Total 18 checks, 104 seconds.
- B: `7/+y` (9), `10/+y` (36), `8/+y` (57), `9/+y` (72), `1/-x` (80), `5/+x` (87), `4/+y` (96), `6/+y` (105), `3/+x` (106), `0/+x` (107). Total 107 checks, 697 seconds.
- C: `7/+y` (27), `1/-x` (29), `8/+y` (35), `9/+y` (38), `10/+y` (41), `4/+z` (43), `5/+x` (44), `6/+y` (47), `3/+x` (48), `0/+x` (49). Total 49 checks, 221 seconds.

Repeated successes: `7/+y`, `8/+y`, `9/+y`, and `10/+y` each succeeded in all three runs; `5/+x`, `6/+y`, and `0/+x` also succeeded in all three. `1/-x` succeeded in B and C; `1/+y` succeeded in A. `4/+y` succeeded in A and B; `4/+z` in C. `3/+y` succeeded in A; `3/+x` in B and C.

The most evident wasted checking was condition B: it took 107 checks and 697 seconds, including 27 checks between the first acceptance (check 9) and second (36), and 21 between the second and third (57). A reached the goal in 18 checks and 104 seconds; C used 49 checks and 221 seconds.

## Limits
These are only three first-attempt traces, with no reference solution and no stated controlled comparison of planner settings. Rejected-direction lists show failures encountered during each run; they do not prove a direction can never work in every assembly state. The large-direction rejection records for parts `0`, `4`, `5`, `6`, and `1` are state- and run-specific, and part `4` demonstrably succeeded in more than one direction. The records support a practical order and candidate prioritization, but not a globally optimal order or a causal explanation for the check-count differences.

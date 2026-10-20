---
name: "assembly-removal-memory"
description: "Assembly-specific removal guidance derived from the three recorded first attempts."
---
## Triggers

Use this note only when the same assembly geometry fingerprint is encountered. Directions are world-axis labels: +x=[1,0,0], -x=[-1,0,0], +y=[0,1,0], -y=[0,-1,0], +z=[0,0,1], -z=[0,0,-1].

## Procedure

Try the successful 14-step sequence from condition B first; it reached the goal in 38 checks and 95 seconds:

1. 11 +z
2. 10 +z
3. 12 +z
4. 13 +z
5. 14 +z
6. 1 +z
7. 3 +z
8. 9 +z
9. 4 +z
10. 5 +z
11. 6 +x
12. 7 +x
13. 8 +x
14. 2 -x

The other successful attempts confirm a recurring pattern: remove the +z-accessible group before the +x group (6, 7, 8), and remove part 2 toward -x. If a planned step fails, re-check current geometry before changing direction: acceptance varies with assembly state. Condition C also succeeded with this order: 13, 14, 11, 12, 10, 9, 4, 5, 1, 3 all +z; then 6 +x, 2 -x, 7 +x, 8 +x.

## CODE application

Prioritize the condition B sequence as a compact candidate order. Its recorded accepted checks were 3, 5, 7, 9, 11, 12, 14, 21, 23, 25, 31, 33, 35, and 38. In condition C, the same late-stage direction choices worked, with parts 6 +x and 2 -x accepted at checks 47 and 52 before 7 +x and 8 +x. Avoid spending checks on directions that were rejected across repeated attempts (see Evidence).

## GRAPH_DFS application

Use successful removals to guide branch ordering, not as a proof that a branch is impossible: rejected directions were recorded at particular intermediate states. The repeated successful tail is 6 +x, 7 +x, 8 +x, with 2 -x also successful (condition B places it last; condition C places it between 6 and 7). Keep +z candidates early for parts 11, 10, 12, 13, 14, 9, 4, and 5; part 1 and part 3 also succeeded along +z in B and C. Re-evaluate candidates after each removal.

## Evidence

All three conditions reached the goal and removed 14 of 14 parts.

- Condition A: 225 checks, 637 seconds. Accepted sequence: 2 -x, 3 +x, 7 +y, 8 +y, 11 +z, 10 +z, 12 +z, 9 +z, 4 -y, 5 +z, 6 +x, 13 +z, 14 +z, 1 +y.
- Condition B: 38 checks, 95 seconds. Accepted sequence is the recommended sequence above.
- Condition C: 54 checks, 173 seconds. Accepted sequence is listed under Procedure.
- Parts 1, 4, 5, 6, 9, and 10 were each rejected in all six directions in condition A. This marks broad initial blockage in that attempt, though some later succeeded after the state changed.
- +z was rejected for parts 1, 4, 5, 6, and 10 in both B and C, yet each part was eventually accepted in +z in at least one of those conditions (parts 1, 4, 5 in B; 6 and 10 in C). Treat these as state-dependent failures, not permanently invalid directions.
- No accepted removal used -z in any condition. It was explicitly rejected for parts 1, 7, and 8 in C; no broader -z rejection record is available.
- Checks between accepted removals show the costly stretches: A had gaps of up to 37 checks (between 8 and 11); B had gaps up to 7 (between 3 and 9); C had gaps up to 10 (between 14 and 9). Records do not identify the specific rejected checks within those gaps.

## Limits

These are first-attempt planner records, not reference solutions. They provide no per-check trace beyond accepted check indices and the listed per-part rejected directions, so the exact wasted candidate checks and the conditions that caused each rejection cannot be reconstructed. Condition labels do not establish which search strategy produced each run. The recommended order is the fastest recorded successful sequence, not a guarantee of identical performance.

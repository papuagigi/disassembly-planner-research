# Physics feasibility control (v7, no LLM)

All runs use the unchanged evaluated simulator unless a row says `P1` (diagnostic rule, never used by planners).
Tools: `physics_audit.py` (sample-0 lock audit), `feasibility.py` (parallel full-expansion DFS reference search).
Raw: `analysis/physics/initial_lock_audit*.json`, `analysis/physics/reference_search/*.json`, `analysis/physics/v6_collision_breakdown.json`.

## 1. What blocks motion in the v6 traces (all arms, read-only)

| CAD | accepted | rejected at sample 0 | rejected within 2 mm | rejected after 2 mm | unstable |
|---|---:|---:|---:|---:|---:|
| 05954 | 68 | 60 | 259 | 42 | 5 |
| 06444 | 11 | 4 | 199 | 0 | 0 |
| 03114 | 3 | 430 | 8 | 1 | 0 |

Sample 0 is the part's current pose, so a sample-0 rejection is identical for all six labels. Its cause in `source_collision._material_check`: samples with operation-initial depth > penetration tolerance (0.2 mm) are permitted only the tolerance, so pre-existing CAD interference > 0.2 mm rejects every direction. Within-2 mm rejections are motion into contact/tight fits with 0.02 mm slack.

## 2. Sample-0 lock audit at the initial state

| CAD | evaluated poses (MuJoCo-settled) | CAD poses (pre-settling) |
|---|---|---|
| 05954 | mutual 0↔7 | 5 mutual pairs |
| 06444 | 18 locked by fixture 1 | 3 mutual pairs |
| 03114 | 0,1,2,3,4,5,12,14 locked by fixture 24; 10 mutual pairs | similar (14 mutual) |
| 6 earlier fully-disassembled dev CADs (02402, 03674, 02406, 05459, 01613, 07375) | none | none except 03674 (4 before settling) |

Interference is CAD-intrinsic (present before settling), not created by settling. A lock is a certificate **only while poses are unchanged**.

## 3. Reference search with the evaluated checker

| CAD | status | checks | max removed / required | lock persistence |
|---|---|---:|---|---|
| 01613 (positive control) | complete path found, 139 s | 330 | 10/10 | none |
| 05954 | reachable space exhausted (remaining-set pruning) | 378 | 3/12 | 0↔7 in every expanded state |
| 03114 | reachable space exhausted (pruning), only 4 states | 480 | 2/21 | identical lock set in every state |
| 06444 | wall cap 1800 s | 930 | 9/20 (v6 A reached 11) | 18↔1 lock **released after 5 removals** by residual settling |

Pending (running): 05954 without pruning; 06444 seeded with v6 A's verified 11-removal prefix; P1 diagnostic on all three.

## 4. Interpretation (verified vs. inferred)

- Verified: under the evaluated checker, 05954 and 03114 reach at most 3 and 2 removals in the explored reachable space; v6 A/B on 05954 (3) and every arm on 03114 (1) were at or near those limits. Full disassembly was not available to any planner there within the explored space.
- Not a proof: remaining-set pruning can skip a pose variant of an already explored part set; a no-pruning rerun is pending for 05954. 03114's reachable space is tiny and locks never change, so the conclusion there is strong but still empirical.
- 06444 is unresolved: its initial fixture lock is not permanent. v6 failures on 06444 (B, C: 0 removals) are therefore not explained by physics alone.
- Binding constraint candidates: for 03114/05954 the sample-0 interference rule (CAD overlap > 0.2 mm) dominates; motion direction set is irrelevant to sample-0 locks; the fixture matters only where the locked partner is the fixture (06444, 03114), and a mutual lock with a free part would block either way. The P1 diagnostic tests whether relaxing only the interference rule makes full paths exist. P1 is not adopted for evaluation.

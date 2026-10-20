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
| 06444 seeded with v6 A's verified 11-removal prefix | reachable space exhausted (pruning) | 492 | **19/20** | every branch ends at {fixture 1, part 18} |

P2 (adopted rule) reproduces the P0 reachable space exactly on 05954 (378 checks, max 3) and 03114 (480, max 2); see PHYSICS_DECISION.md.

### 06444 last part (`analysis/physics/06444_last_part_probe.json`)

At the 19-removal state {1, 18} (path rebuilt from the search and re-verified), part 18 fails in all six labels under **both P0 and P2**:
- ±x, +y, ±z: rejected at ~1 mm; penetration into fixture 1 grows to 1.14–1.18 mm (initial 0.15–0.19 mm) — the part sits inside the fixture body.
- −y: travels 6.97 mm, then one sample reaches 0.203 mm against a 0.200 mm permit (initial 0.176 mm). A **3 µm** margin decides the last removal.
So 06444's full sequence is blocked at its final step by a near-threshold tolerance case, not by an all-direction initial lock. P2 does not change it (initial depth < 0.2 mm). Whether a part-local axis (after settling tilt) clears it is measured by `offline/motion_probe.py`.

## 4. Interpretation (verified vs. inferred)

- Verified: under the evaluated checker, 05954 and 03114 reach at most 3 and 2 removals in the explored reachable space; v6 A/B on 05954 (3) and every arm on 03114 (1) were at or near those limits. Full disassembly was not available to any planner there within the explored space.
- Not a proof: remaining-set pruning can skip a pose variant of an already explored part set; a no-pruning rerun is pending for 05954. 03114's reachable space is tiny and locks never change, so the conclusion there is strong but still empirical.
- 06444: its initial fixture lock is not permanent; 19/20 removals are physically reachable from v6 A's prefix, and the final part fails by 3 µm along −y. v6 B/C (0 removals) and A (11) were far from that physical ceiling, so 06444's v6 shortfall is mostly planner/budget, with a final-step tolerance limit.
- Binding constraint candidates: for 03114/05954 the sample-0 interference rule (CAD overlap > 0.2 mm) dominates; motion direction set is irrelevant to sample-0 locks; the fixture matters only where the locked partner is the fixture (06444, 03114), and a mutual lock with a free part would block either way. The P1 diagnostic tests whether relaxing only the interference rule makes full paths exist. P1 is not adopted for evaluation.

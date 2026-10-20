# Physics condition decision (written BEFORE the P2 diagnostics were run)

Date: 2026-10-20 (UTC ~07:00). Authorized by the user: "물리 조건 결정을 먼저 … 네가 직접 판단 후 작업을 진행해".

## Problem (verified)

- v6 evaluated rule (`disassembly_real_v3/source_collision._material_check`): a material sample whose operation-initial depth exceeds `penetration_tolerance_m` = 0.2 mm is permitted only 0.2 mm, so it fails at path sample 0 in every direction.
- 494 / 1,003 v6 path collisions happened at sample 0. Locking depths at evaluated poses on the v6 CADs are 0.237–0.454 mm (03114 CAD poses repeat 0.245 mm), i.e. sub-millimetre CAD overlaps.
- The same physics model elsewhere treats initial penetration up to `stable_penetration_m` = 1 mm as acceptable: the initial screen admits static penetration ≤ 1 mm, the stability criterion allows ≤ 1 mm, and the MuJoCo-convex path checker (`disassembly_mujoco.simulator`) lets initial penetration ≤ 1 mm persist (+ slack) and caps only deeper initial penetration. The source-mesh rule is the only place using 0.2 mm as the hard initial cap.

## Candidate: P2 (`physics_variants.P2_persist_up_to_stable_penetration`)

Per material sample: if initial depth ≤ 1 mm, permitted = max(0.2 mm, initial + 0.02 mm) (persist, may not grow by more than the existing slack); if initial depth > 1 mm, permitted = 0.2 mm (unchanged hard collision). Everything else unchanged: six source-axis straight translations, 1 mm path sampling, containment / unresolved-intersection / floor checks, one permanent fixture, MuJoCo residual stability.

P2 is monotone: any action accepted by P0 is accepted by P2 (same stability step; path permits are ≥ P0 everywhere).

## Pre-specified adoption rule

Adopt P2 as the v7 pilot physics if all hold; success rate is NOT a criterion:
1. Monotonicity holds empirically: on recorded P0-accepted actions re-checked under P2, no change.
2. For P2-only accepted actions, recorded path diagnostics show no sample exceeding initial depth + slack (by construction) and no use of initial depth > 1 mm (by construction) — verified on a sample by re-running with details.
3. The six known-solvable development CADs stay lock-free (follows from 1).

Report regardless of outcome: P2 reference search on 05954 / 03114 / 06444 (development CADs only). Pilot candidates are not used to design or tune physics.

If adopted: v7 pilot is re-frozen as condition `v7.1-P2` with the same code, limits, model, arms, bank; the P0 freeze is kept as "superseded before any pilot episode". v6 results and v7 regressions remain P0 evidence. SKILL.md S3 was developed under P0; its use under P2 is a recorded limitation.

## Adoption result (2026-10-20 ~07:50 UTC, `analysis/physics/p2_adoption_checks.json`)

- Criterion 1 (monotonicity): PASS. 17 recorded P0-accepted removals (06444/A prefix, 05954/A and B prefixes) replay under P2 with identical validity and child state keys.
- Criterion 2 (plausibility of P2-only acceptances): PASS vacuously. Probing every sample-0-locked part in all six labels at the 05954 (12 probes) and 03114 (108 probes) initial states produced **0** new acceptances. All 120 probes now fail within the first 1–2 mm instead of at sample 0: 05954 parts 0/7 hit several surrounding parts (e.g. 0 +x: 10, 11, 2, 6, 7, 8, 9); 03114 parts mostly increase their pre-existing interference by ~0.96 mm within 1 mm of travel (embedded in fixture 24 / part 23).
- Criterion 3: PASS (follows from 1).
- P2 reference search on 05954 and 03114 reproduces the P0 reachable space exactly (378 / 480 checks, max 3/12 and 2/21).

Decision: **P2 is adopted as the v7.1 pilot physics** under the pre-specified rule. Recorded consequence: on these development CADs P2 changes where/why a rejection is reported (geometric blockers at ~1 mm instead of an all-direction sample-0 lock) but not which actions are feasible. The binding constraint there is straight six-label translation through tight/enclosing geometry. Wider motion primitives (diagonals, part-local axes, rotations) would change the planners' action space; they are NOT adopted here and are only measured as a diagnostic (PHYSICS_FEASIBILITY.md).

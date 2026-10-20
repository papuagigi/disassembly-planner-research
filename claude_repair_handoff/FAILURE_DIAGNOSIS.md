# Verified failure evidence for the next repair

Updated: 2026-10-20 KST. Read-only post-score analysis; **no new model or physical query** was used to create this handoff. The associated [evidence.json](evidence.json) records raw-result/source hashes and recomputes the key counts. Paths below are relative to the original workspace root. Public clones omit raw episode/provider files.

## B: frontier lost between generated programs

Source: `disassembly_final_v6/outputs/evaluation/trials/asap_05954/B/result.json`, `decisions` calls 1–8 and `recovery_state`.

- Call 1 reads the two documents. Call 2 performs checks 0→113, accepts three removals, then returns when no candidate remains.
- Calls 3–8 each record **113→113 checks**, no restores, and no new removal. These six calls consume **707,037 input+output tokens**. The episode stops at the eight-call cap, around 588 seconds.
- The final dead-end state has nine movable parts. All **54** declared part/direction actions were tested and rejected there (checks 60–113).
- Only the original checkpoint (zero removals) and a new checkpoint at this dead end (three removals) remain; no one-/two-removal parent checkpoints were created.
- Call 3 creates `stack=[]`, treats the *current* dead end as its root, filters the known failures, then reaches `if not candidates: if not stack: return`. Replacing the program again does not reconstruct the old search frontier.

`disassembly_final_v6/actors.py` passes physical/recovery state into each `runtime.execute_payload`, but does not pass the generated program's local variables/frontier. Physical restoration capability exists; having the API does not mean the program uses it correctly.

**Interpretation:** this is a search-state continuity/no-progress handling defect, not a provider error or Python exception. It does not prove that a different branch fully solves the CAD. Repair should preserve generated-code ownership of A/B search rather than secretly supplying a host DFS only to B.

## A: accepted dead branch repeatedly re-entered

Source: `disassembly_final_v6/outputs/evaluation/trials/asap_05954/A/result.json`, generated code and `trace`.

- Check 47 first accepts part `3/-y` into a later exhausted branch.
- Checks **102–160**, inclusive, accept that same action from the same physical parent into the same child **59 more times**.
- There are 62 accepted removals, 59 undone removals, and 118 restore operations. Final/best depth is only three.
- The program stores rejected pairs, but does not mark an accepted edge as exhausted after its child has been exhausted. Restoring the parent makes that accepted action look available again.

**Interpretation:** zero duplicate *rejected* queries did not mean useful exploration. Track successful-edge/child exhaustion as well. A's larger total progress in the final pilot is mainly the good initial order on 06444, not proof of reliable A backtracking or general A superiority.

## C: viable action delayed, model calls spent before deeper search

Sources: raw `asap_06444/{A,B,C}/result.json`, `analysis/root_action_coverage.json`, `analysis/search_priority_evidence.json`, and the effective-order reconstruction in this handoff's evidence file.

All arms started at the same exact state, including poses/velocities. A accepted **part `20/+y` at check 3**. B performed 98 and C 81 completed root-state checks without trying it. The action remained an unknown eligible candidate; it was not globally excluded by the graph.

For C on 06444, replaying only the saved candidate-order logic, without physics/model calls, produces:

|Logical call|Checks before call|Eligible actions|Effective position of `20/+y`|Completed checks using that order|
|---|---:|---:|---:|---:|
|2|0|120|95|6|
|3|6|114|94|6|
|4|12|108|76|6|
|5|18|102|99|6|
|6|24|96|76|6|
|7|30|90|11|6|
|8|36|84|55|45|

Each reconstructed order's executed prefix matches the raw action trace exactly. After six more checks the untested action moves from 11th to 55th; the deadline arrives after only 45 checks under the last order. `controller.DFS.set_order` replaces the current order. This is direct priority-delay evidence, not proof that `20/+y` is the unique correct move or that a complete path follows it.

On all three C episodes the eight-call allowance is used early. On 03114 the last call occurs after check 36; the first accepted removal is check 112. On 05954 the last call occurs after check 33; the third accepted removal is check 60. The host DFS continues after the call cap, but cannot obtain further LLM guidance. Reading documents also uses one call.

**Interpretation:** inspect stability of untested priorities and call allocation before switching to a stronger model. That model change has not been tested. C's DFS does perform two state-changing parent restores on 05954, so its final depth 1 versus best depth 3 is partly termination during rollback; do not call this a lost-removal bug by itself.

## Physical rejection dominates, complete feasibility is unresolved

Across all nine final episodes, **1,090 completed queries** contain 1,003 `path_collision`, five `unstable_remainder`, and 82 accepted results (including later undone removals). Thus 1,003/1,008 rejections are path collisions. These are recorded reasons, not an experiment disabling gravity or measuring false positives. Five charged unfinished queries remain unknown.

- `disassembly_real_v3/simulator.py`: six straight source-axis extractions at fixed orientation; source-mesh path checks precede MuJoCo stability.
- `disassembly_real_v3/source_collision.py`: triangle/material-point finite sampling and conservative handling of unresolved surface intersections. This is not an exact continuous solid-collision oracle.
- `disassembly_mujoco/simulator.py`: one permanent fixture has no free joint. Residual dynamics use prepared convex collision geometry; visual meshes are not the collision model. Inertia is approximated.
- `disassembly_final_v6/data_tools/convert_cad.py`: assumed mass/density/friction and anchor/orientation screening, not calibrated real-product material measurements.

Completed operation elapsed times on 06444/B total about **825 seconds of rejected path checks**, versus about 15 seconds in the model provider. Its zero progress cannot be explained just by document-reading latency. Query order and checker cost matter together.

Initial qualification certified geometry/initial stability criteria, not a complete local disassembly sequence. The final portable bundle has **no complete reference sequence**. Every final CAD has at least one accepted initial action across arms; a valid first move is not a full feasibility certificate. Some rejection detail is conservative; a false-collision rate has not been measured. Do not assert that all planner failures are caused by physics or that original ASAP/real-world disassembly is impossible.

All final worker logs are native-warning-free. Eight episodes stop at the wall cap and one at the call cap; recorded budget exceptions are intentional stops, not generated-code exceptions. Separately, development/validation native arena/contact warnings exist and must not be reclassified as learned physical failure. A 4 GiB process RSS guard and MuJoCo's internal contact arena are different limits.

## SKILL.md was delivered; whole-task benefit was not established

Sources: `disassembly_final_v6/memory/S3.json`, its two document/reference files, `analysis/memory_context_audit.json`, and `outputs/development/new_document/admission.json`.

B/C receive byte-identical document bodies and references. The delivery audit verifies these bytes in model input; it does not prove attention, correct application, or causal benefit. Current review is **mandatory initial loading of both documents**, not an autonomous selective-retrieval evaluation.

`physical-disassembly-failure-repair` and `physical-directional-clearance` describe physical action priorities after collision/instability. They do not supply a stored DFS implementation. The repair admission explicitly limits evidence to independent bounded physical repair; `strict_full_actor_integration_status` is **REJECTED**, and held-out efficacy is unknown. Do not interpret a local procedure gate as certification of full-search correctness.

The newly generated `physical-clearance-chain` candidate was rejected after a native-warning veto on one of three validation CADs. Two local passes do not override that veto. Final S3 therefore retains the two earlier bodies. There is no admitted new procedural update to which v6 success could be attributed.

The shared bank does not force B/C to pick the same priorities or recover correctly. Some advice (try alternative directions) overlaps A's existing behavior. B–A changes document context plus charged review; C–B changes search architecture and scheduling. A fixed-architecture memory ablation was not run in this final cohort. Neither "skills are useless" nor "skills improved new-product success" follows from these three failed products.

## Repair priority and evidence boundary

1. Keep v6 immutable and establish a new development namespace. Now-known CADs are regression inputs, not fresh test products.
2. Verify a full reference through the same local physics/action API before making broad planner-failure claims. Preserve counterexamples if no path is found; absence of a found path is not impossibility proof.
3. Reproduce the A/B search-continuity defects and C scheduling delay offline; implement bounded repairs without changing arm identities silently.
4. Validate any *new physical procedure* separately from software fixes. Freeze a common B/C bank before fresh testing.
5. Report a bounded new pilot honestly, including failures and actual costs. More calls, a stronger model, wider motion primitives, or relaxed collision tolerances are separate interventions, not established explanations.

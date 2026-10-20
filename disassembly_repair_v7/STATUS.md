# disassembly_repair_v7 — STATUS

Owner: Claude Code (user-assigned 2026-10-20 KST). Evaluated model stays **gpt-6-luna / low via CodexCLIProvider**; Claude only edits code.
This file is the Codex↔Claude handoff entry. Update it at every meaningful checkpoint.

## Rules carried from the handoff

- `disassembly_final_v6` is COMPLETE and frozen. v7 imports v6/legacy modules but never writes them. Run `python -B -m disassembly_repair_v7.protect` before/after work (162 protected hashes from `claude_repair_handoff/evidence.json`).
- 05954 / 06444 / 03114 are **development/regression only** in v7. Never report them as first encounters.
- A = generated code, no documents. B = generated code + S3 SKILL.md. C = conditional graph + LLM priority + fixed DFS + the same S3 documents. B/C documents are byte-identical and frozen.
- Default limits unchanged: 8 calls, 240 physics checks, 900 s, 4 GiB RSS guard, 10M instructions, 128 checkpoints, 256 restores, 512000 prompt bytes, 64000 response bytes. One planner at a time.
- No PPT. Do not iterate a held-out policy until a favored arm wins.

## Stage log

| Stage | State | Evidence |
|---|---|---|
| 0. Protection check / namespace | DONE: 162/162 hashes match; `disassembly_repair_v7` unused before 2026-10-20 | `outputs/protection_check_latest.json` |
| 1. Verify v6 diagnoses on raw logs | DONE (see below) | this file, `analysis/` |
| 2. Physics initial-lock audit | DONE: 6/6 known-solvable controls lock-free; 3/3 v6 CADs locked | `analysis/physics/initial_lock_audit*.json` |
| 3. Offline reproduction tests of A/B/C defects | DONE: synthetic 7/7 pass; A/05954 v6 trace reproduced exactly (160 queries, 59 re-entries); B call-3 code 0 checks | `tests/`, `outputs/regression/{a,b}_v6_repro/` |
| 4. v7 repairs R1–R6 | IMPLEMENTED + OFFLINE-TESTED + NATIVE regression; real-provider smoke on known CAD 01613 ran end-to-end (A/C goal, B 240 s cap) | `CHANGELOG.md`, `shared_api.py`, `runtime.py`, `actors.py`, `controller.py`, `contracts.py` |
| 5. Saved-code/response regression on v6 CADs | DONE: A 59→0 re-entries; B no_progress_stop at call 4; C calls paced 0/35/70; resume probe restores 2-removal state | `analysis/REGRESSION.md`, `outputs/regression/` |
| 6. Physics reference-path control on development CADs | PARTIAL: 01613 path found; 05954 max 3, 03114 max 2 (exhausted); 06444 unresolved (lock released after 5 removals); diagnostics running | `analysis/PHYSICS_FEASIBILITY.md` |
| 7. Pre-registered fresh-CAD pilot | P2 ADOPTED (`analysis/PHYSICS_DECISION.md`); `freeze_v7.1_P2.json` 07:49Z; P2 selection RUNNING (`outputs/pilot_inputs/select_P2.log`; primary 98 training + 23 test backup); `offline/run_remaining_pipeline.sh` → `outputs/pipeline_P2.log` auto-runs campaign+post_run after selection | `pilot_inputs.py`, `protocol.py`, `campaign.py`, `driver.py`, `outputs/provider_check/latest.json` |
| 8. Aggregate, replay, final handoff | PLANNED | |

## Stage 1 findings (verified on raw v6 result.json, read-only)

- **A/05954**: `3/-y` accepted at check 47 into child `d9a11272…`; checks 48–101 reject all 54 child actions; checks 102–160 re-enter the same edge 59 times. Generated code stores rejected pairs only; restoring the parent makes the accepted edge look untried again. Confirmed.
- **B/05954**: calls 3–8 each 113→113 checks, 0 restores. Agree with the handoff and add one point: call 2's program was greedy and **never created a checkpoint**, so no 1-/2-removal parent checkpoint existed; call 3's program starts `stack=[]`, filters the dead end, and `return`s. Two defects: (i) no parent checkpoints/frontier facts survive program replacement, (ii) no rule stops zero-progress calls.
- **C/06444**: independent reconstruction of the effective order from saved responses matches the handoff: `20/+y` positions 95, 94, 76, 99, 76, 11, 55; every executed prefix matches the trace. Re-rank every 6 failures spends all 8 calls by check 36. The LLM listed only 52 actions in call 2; `20/+y` was in the appended canonical tail.
- **Physics (new)**: of 1,003 path collisions, 494 occur at path sample 0 (no motion yet) and 466 within the first 2 mm. Material excess depth median 0.23 mm (tolerance 0.2 mm, slack 0.02 mm). Sample 0 is direction-independent, so a sample-0 blocker blocks all six labels. On 03114 parts 0,1,2,3,4,5,12,14 are sample-0 blocked by fixture 24 and several pairs are mutually blocked.

## Physics finding (stage 2, verified with the unchanged checker)

Sample-0 (no motion yet) rejection is direction-independent: a part blocked there cannot leave in any label while its blocker remains. Material samples whose initial depth exceeds the 0.2 mm tolerance are capped at tolerance (`source_collision._material_check`), so any pre-existing CAD interference > 0.2 mm is a permanent lock until poses change.

| CAD | evaluated poses (after settling) | CAD poses (before settling) |
|---|---|---|
| 05954 (v6) | mutual lock 0↔7 | 5 mutual pairs |
| 06444 (v6) | 18 locked by fixture 1 | 3 mutual pairs |
| 03114 (v6) | 8 parts locked by fixture 24; 10 mutual pairs | 8 fixture-locked; 14 mutual |
| 02402, 03674, 02406, 05459, 01613, 07375 (earlier development CADs fully disassembled before) | none | none except 03674 (4 fixture locks before settling, 0 after) |

Interpretation: interference is CAD-intrinsic. Locks are certificates only while poses stay unchanged: on 06444 the 18↔1 lock disappeared after 5 removals (residual settling). 05954 (max 3) and 03114 (max 2) reachable spaces were exhausted with locks persisting. Details: `analysis/PHYSICS_FEASIBILITY.md`.

## Pilot design (to be frozen after regression, before opening any pilot CAD)

- Pool: official training archive, never opened by this project, 11–20 parts (98 candidates). Official test split has only 23 unopened products, all ≤ 10 parts.
- Qualification: unchanged v6 conversion/initial physics; no duplicate geometry; sample-0 lock audit recorded (not an exclusion); non-LLM reference search must find a complete sequence within 2500 physical checks (never given to planners). First 3 in frozen order.
- 3 CADs × A7/B7/C7, arm order rotated (v6 rule), one planner at a time, no background heavy processes during episodes.

## Physics decision (v7.1) — DONE

- P2 adopted by the pre-specified rule (monotone; 0 implausible new acceptances). On development CADs P2 changes the reported cause/location of rejections but not feasibility: 05954 max 3/12 and 03114 max 2/21 under both P0 and P2.
- Binding constraint on those CADs: six-label straight translation through tight/enclosing geometry; rejections at ~1 mm. Hypothesis under test: settling tilt (e.g. 03114 part 0 ≈1.4°) × straight assembly-axis motion × 0.02 mm growth slack. `offline/motion_probe.py` (diagnostic only, P2, axes6 vs diag20 vs part-local axes) → `analysis/physics/motion_probe.json`.
- 06444 under P0 from v6 A prefix: 19/20, every branch ends with part 18 on fixture 1. `offline/probe_06444_last_part.py` tests part 18 under P0/P2 → `analysis/physics/06444_last_part_probe.json`.
- Motion-primitive changes would alter planners' action space; not adopted without a separate decision.

## Publication (user request 2026-10-20)

- Public repo: https://github.com/papuagigi/disassembly-planner-research, branch **`claude/repair-v7`** (repo AGENTS.md: additional work on branches; main untouched unless the user asks to merge).
- Rule from the user: commit detailed changes; **push at every core update** (e.g. physics decision, pilot selection complete, pilot results, final interpretation).
- Tool: `disassembly_repair_v7/offline/publish_snapshot.sh "<subject>" [push] [groups]` → `publish.py` allowlist (code, docs, evidence, pilot summaries), secret-pattern fail, `<workspace>` path redaction; no raw CAD, traces, provider logs or PPT.
- First push: 8 commits, head `1a5819a` (v7 code, tests, physics tools, pilot pipeline, docs, evidence, README/CLAUDE/AGENTS pointers).

## Next actions

1. Let `pipeline_P2.log` proceed (selection → protect → campaign → post_run → protect). Never rerun a started episode.
2. Fold motion_probe / 06444 results into `analysis/PHYSICS_FEASIBILITY.md` (not frozen).
3. After PIPELINE_DONE: interpret `analysis/PILOT_RESULTS.md`; keep software-repair, physics and memory claims separate.

# disassembly_repair_v7_4 — status

Reliability evaluation of the unchanged v7.3 planner on many easy NEW CADs with repeats (user request 2026-10-21, after the v7.3 presentation was finished and pushed). Design and metrics: [PLAN.md](PLAN.md) (Korean). v6–v7.3 records are untouched.

## Live state (2026-10-21)
- Package created as a copy of v7.3. The planner modules are byte-identical; only package paths differ (7 lines in `__init__`, `common`, `driver`, `procs`, `data_tools/convert_cad`, `offline/replay_all`, `offline/aggregate`). `campaign74.freeze` re-checks the identity.
- `selection74.py`: never-opened ASAP training products with 5/6/7 parts (pool 202/104/89 after excluding 866 opened IDs, v7.3's 92 included). Seeded order (20261021), strata interleaved, target 4 per stratum. Qualification and P2 reference search are unchanged from v7.3, and the conversion config is a byte-identical copy.
- `campaign74.py`: 12 CADs × (attempt 1: A, B(Sx), C(Sx) × 3 repeats; 조립체별 SKILL.md from repeat-1 records; attempt 2: B, C(Sx + 조립체별) × 3) = 180 episodes. Schedule dry run OK (36 per condition).
- **User decision (2026-10-21, before any v7.4 outcome): Sx = S5** (v7.3 `memory/S5.json`, latest 범용 SKILL.md; not admitted in v7.3 validation, which is disclosed). Run approved: freeze and start the 180 episodes as soon as the selection finishes. Cost estimate in PLAN.md (≈10M tokens upper estimate, ≈3 h of episodes plus selection).
- Candidate order frozen (`outputs/protocol/selection_candidates.json`, 395 candidates, seed 20261021); model-free selection started (`outputs/selection_run.log`, `outputs/selection_inputs/progress.json`).
- Hand-off to the run: `offline/run_after_selection.sh` (started under `caffeinate -i` so idle sleep is blocked; log `outputs/campaign_run.log`) waits for the selection to end, then runs `campaign74 freeze --bank S5` and `campaign74 evaluation --bank S5`. The freeze refuses (and the user is asked) if fewer than 9 CADs were found. The busy-process guard was checked: it does not count the waiting runner.
- Next: freeze candidates → model-free selection (no tokens) → user decision → freeze evaluation → campaign → replays → aggregate → write-up → push.

## 2026-10-21 — Amendment 1 (user-approved) and resume
- After the 9 attempt-1 episodes of asap_08203 the run stopped in `write_note` → `make_bank` (ValueError: base-bank SKILL.md under v7_3/memory is not relative to v7_4/memory). No attempt-2 episode had started.
- Fix: `campaign74.local_base()` passes byte-identical copies of the S5 bank (sha256 asserted) under `memory/` to the note writer. Planner, prompts, budgets, physics, bank contents and schedule unchanged. Record: `outputs/protocol/amendment1_note_base_path.json`; `verify()` accepts only the amended campaign74.py hash.
- The unused partial note (writer log + materialized note) moved to `outputs/recovery/aborted_note_writer_asap_08203/`; the note was rewritten by a fresh writer call.
- Resumed with `offline/resume_evaluation.sh` (log: `outputs/campaign_run.log`). At 31/180 episodes all succeeded; both note-writer reports show no problems.

## 2026-10-21 16:46Z — evaluation COMPLETE (180/180 episodes, all goal_reached)
- `outputs/evaluation/complete.json`; aggregation: `python -m disassembly_repair_v7_4.offline.aggregate74` → `analysis/RESULT_TABLES.md`, `summary_v74.json`, `evaluation_runs.csv`.
- Repeat determinism (op, part, direction, valid trace identical over 3 repeats): A 0/12, B(S5) 12/12, C(S5) 1/12, B(note) 11/12, C(note) 12/12.
- Remaining: independent replays (offline, no model call; safe to stop and rerun from scratch):
  `PYTHONDONTWRITEBYTECODE=1 disassembly_learning_v1/.venv/bin/python -B -m disassembly_repair_v7_4.offline.replay_all 6 evaluation` (from the workspace root), then rerun aggregate74 and write `analysis/EVALUATION_RESULTS.md`.
- 2026-10-21T16:48:37Z: the replay run was stopped at the user's request before it finished; no outputs/replay/evaluation.json was written. Replays are NOT yet verified.

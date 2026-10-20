# disassembly_repair_v7_2 — STATUS (Codex/Claude handoff entry)

Owner: Claude Code (user-assigned 2026-10-20). Evaluated model gpt-6-luna/low via CodexCLIProvider. v6, v7 and v7.1 records are unchanged; this package imports them read-only.

## User decisions (2026-10-20)
- Engine hardening first, then: development failure collection → SKILL.md S4 → repeated validation → same-assembly retry evaluation.
- Reduced scale; C included in validation and retry; everything within ~12 h (results by the next KST morning; the user will build a PPT afterwards — no PPT made here yet).
- Focus effort on improving B and C. Guardrails kept: development data only for improvement; validation/retry frozen before outcomes and run once; A keeps the same engine (not weakened); all outcomes reported.

## v7.2 changes (recorded protocol changes)
| ID | Change | Arms | Why |
|---|---|---|---|
| H1 | Episode deadline checked inside the common API before every check/remove | A/B/C | v7.1 05902/B ran 7 checks after its 900 s budget |
| H2 | Exact-state rejection cache: repeat of a recorded rejection at the same exact state answered without physics/charge | A/B/C | v7.1 06146/B repeated 51, 05902/B 24 rejected checks |
| H3 | RSS guard 4 → 8 GiB | A/B/C | v7.1 06146/C stopped by a transient 5.45 GiB physics peak; same decisions reach 14/14 without the cap |
| H4 | Process hygiene: searches in their own process group; timed episodes wait until no project python process (incl. spawn workers) is alive | infra | 19 orphaned workers found after v7.1 |
| C7.2 | C ranks when stuck (3 rejections on an inherited order) instead of on every first visit | C only | v7.1 C spent all 8 calls on early easy states |
| S4 | New SKILL.md bank written by gpt-6-luna/low from all-query failure statistics (mine.py) | B/C | S3 advice measured low-yield (same-part other direction accepted 4–23%) |

Tests: `tests/test_hardening.py` 8/8 pass; v7 synthetic 8/8 pass. Real-provider smoke on known CAD 01613 (reduced limits) ran A/B/C end-to-end; replays PASS (`outputs/smoke/replay_audit.json`).

## Datasets
- Collection (development, known CADs): 01613, 02406, 03674, 07375 × A(S0), B(S3), C(S3), 1 each, 2 concurrent (development only).
- Validation (development): 05459, 02402 × A(S0), B(S4), C(S4) × 2; sequential; admission rule in `campaign.py` docstring (frozen before outcomes).
- Retry evaluation: 05902, 06146 (v7.1 pilot CADs, never used for S4): attempt 1 A/B/C → assembly note → attempt 2 B+note×2, C+note×2, B, C, A.
- S4 evidence additionally uses the v6 final traces of 05954/06444/03114 (development CADs). Pilot traces are excluded by `mine.py`.

## Additional changes after validation (before the retry freeze; all arms)
| ID | Change | Why |
|---|---|---|
| H5 | `provider.py`: inherited Codex provider + `--config web_search="disabled"` (episodes and note writer) | validation 05459/B_r1: empty built-in web_search call → provider tool-use rejection, 0 checks |
| H6 | `shared_api.RepeatedRejectionLoop`: > max(64, 12×parts) consecutive cached answers end the code turn (not the episode); prompt note 7 | validation 02402/B_r2: 2,992 cached repeats of one rejection, 10M instructions, 2 checks |
| A2 | Retry: primary design unchanged (S3 by the rule) + exploratory S4b branch reported separately | S4b not admitted; both B failures were engine-level |
Validation-time code: `outputs/protocol/validation_code_snapshot/` (hashes equal `freeze_validation.json`). Tests 12/12 (`tests/test_hardening.py`), v7 tests 8/8. Offline: the 02402/B_r2 code under H6 stops in 3.6 s / 0.53M instructions. Note-writer smoke with H5 on 01613 collection records: `memory/notes/smoke_asap_01613/` (smoke only, not used by any episode).

## Live state (2026-10-20 ~15:00 UTC)
- Collection done (12): A 3/4, B(S3) 4/4 (mean 98 checks), C(S3) 4/4 (mean 27). Mining → `outputs/mining/bundle_b.json`; S4b in `memory/S4b/`; S4a superseded (`outputs/mining/S4a_superseded.json`).
- Validation done (12): A 4/4 (median 29 checks), B(S4b) 2/4, C(S4b) 4/4 (median 14) → **S4b not admitted** by the pre-registered rule. Write-up: `analysis/VALIDATION_RESULTS.md`.
- Retry running since ~14:38 UTC: frozen `outputs/protocol/freeze_retry.json`, log `outputs/retry/run.log`, rows `outputs/retry/progress.json`. 28 episodes + 4 notes (05902 then 06146). Do not start another timed process while it runs (`run_one` waits for a quiet machine and aborts after 30 min).
- Next: after `outputs/retry/complete.json` → replays (`offline/replay_many.py`, all validation + retry episodes) → `python -m disassembly_repair_v7_2.offline.aggregate` → `analysis/RETRY_RESULTS.md` → push (branch + main).

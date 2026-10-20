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

## Live state
- Collection running: `outputs/collection/collect_AB.log`, `collect_C.log`.
- Next: `python -m disassembly_repair_v7_2.mine <bundle> <results...>` → `skill_writer.write_bank` → `python -m disassembly_repair_v7_2.campaign validation` → `... campaign retry` → replays (`offline/replay_many.py`) → aggregate.

# disassembly_repair_v7_2 — STATUS (Codex/Claude handoff entry)

Owner: Claude Code (user-assigned 2026-10-20). Evaluated model gpt-6-luna/low via CodexCLIProvider. v6, v7 and v7.1 records are unchanged; this package imports them read-only.

## User decisions (2026-10-20)
- Engine hardening first, then: development failure collection → SKILL.md S4 → repeated validation → same-assembly retry evaluation.
- Reduced scale; C included in validation and retry; everything within ~12 h (results by the next KST morning; the user will build a PPT afterwards — no PPT made here yet).
- Focus effort on improving B and C. Guardrails kept: development data only for improvement; validation/retry frozen before outcomes and run once; A keeps the same engine (not weakened); all outcomes reported.
- 2026-10-21 (KST): performance takes priority over wall-clock schedule. Do not cut steps that could hurt performance to save time; the morning deliverable may be an interim report if a further development cycle is warranted. Frozen evaluations still run unchanged (budgets per episode stay the common protocol budgets).

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

## State: bounded cycle COMPLETE (2026-10-20 ~17:45 UTC). Do not start another experiment without the user; any new run needs a new version/freeze.
- Collection (12): A 3/4, B(S3) 4/4 (mean 98 checks), C(S3) 4/4 (mean 27). Mining → `outputs/mining/bundle_b.json`; S4b in `memory/S4b/`; S4a superseded (`outputs/mining/S4a_superseded.json`).
- Validation (12): A 4/4 (median 29 checks), B(S4b) 2/4, C(S4b) 4/4 (median 14) → **S4b not admitted** by the pre-registered rule. `analysis/VALIDATION_RESULTS.md`.
- Retry (28 episodes + 4 notes, 14:38–17:19 UTC, frozen `outputs/protocol/freeze_retry.json`, 19 frozen files unchanged afterwards). `analysis/RETRY_RESULTS.md`, tables `analysis/RESULT_TABLES.md`, `analysis/retry_runs.csv`.
  - Second attempt with the same-assembly note: B(S3+note) 4/4 at 11/11/14/14 checks; C(S3+note) 3/4 (11/11/14; one contract-rule stop); exploratory C(S4b+note) 2/2 (11/14), B(S4b+note) 1/2 (05902 code ignored the note). Controls without memory: A 2/2 (101, 48 checks), B(S3) 2/2 (108, 40), C(S3) 1/2 (42; one provider stop).
  - First attempt: 06146 all five conditions succeeded (B/C 38–83 checks vs A 225); 05902 only A succeeded (B/C ran out of 900 s; generic documents steered toward wrong directions).
- Independent replays: retry 28/28 PASS, validation 12/12 PASS (`outputs/replay/`).
- Performance candidate for the next version (not applied; would change no physics decision, only speed, for all arms): on 05902, model calls use 10–44 s of 900 s; path-collision rejections that stop at path sample 2 still take median 1.9–2.9 s (max 25 s), accepted removals 5–30 s, unstable 20–30 s (`trace[].elapsed_seconds`). Profile after the retry finishes (CPU-heavy); verify any speedup by exact replay equality.
- Document-application candidate (observed, not acted on): on 05902 the labels are remapped (`+z/-z` label = world ±y, `-y` label = world up). B(S4b) first attempt applied S4b's "up first" rule to the LABEL `+z` (first 10 checks all `+z`), not to `direction_vectors_world`. A future SKILL.md/prompt should state world-vector families explicitly. B first attempts (S3 and S4b) each hit one H6 loop stop (~30 s) and then the 900 s deadline.
- Note-priority candidate (observed): 05902 B(S3+note) followed the note's A sequence (11 checks, success), but B(S4b+note) declared all three documents applied while its code reused S4b's generic family-ranking loop and never encoded the note sequence (116 checks, 3/11, deadline). A future contract should state that an exact-fingerprint note's accepted sequence is tried first.
- Provider incident 2 (retry, scored failure, no rerun): 05902 `second_C_base_r1` ended after 6 s, 0 checks — in the document-read call the model invoked Codex's built-in MCP tool `list_mcp_resources` (empty result) despite the prompt forbidding it; the provider rejects any tool activity. H5 only disables web search. After the retry: look for a Codex setting that removes the MCP resource tools (or an equal-for-all retry rule for tool-use rejections) before any new freeze.
- Contract incident (retry, scored failure): 06146 `second_C_note_r1` ended after 9 s, 0 checks — the ranking response listed only the note in `applied_skill_ids` (omitting the two S3 documents), and the inherited v6 rule `required physical procedure review was omitted` raises ValueError → episode ends. This rule can only fire for arms with documents (B/C), and one violation ends the episode without a corrective re-ask. Candidate: make schema/contract violations recoverable within the call budget (same rule for all arms).
- Codex CLI 0.163 shows no user-facing switch for the built-in MCP resource tools (`list_mcp_resources`, `list_mcp_resource_templates`, `read_mcp_resource`); only an internal `add_mcp_resource_tools` string. A provider-level single re-ask on tool-use rejection (equal for all arms) is the practical candidate.
- Candidates for a next version (development-only learning, then a new frozen evaluation on unused CADs): world-vector axis discovery in general SKILL.md; exact-fingerprint note first; recoverable contract violations; tool-use re-ask; faster physics checks with replay-identical decisions. None applied.
- Reproduce tables: `python -m disassembly_repair_v7_2.offline.aggregate`; replays: `python -m disassembly_repair_v7_2.offline.replay_all 8 retry` (untimed; never during a timed episode).

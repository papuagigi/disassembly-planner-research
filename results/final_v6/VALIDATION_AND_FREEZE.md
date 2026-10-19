# Validation and fixed document bank

Observed UTC: 2026-10-19 16:15. This is a completed validation-stage record, not the final A/B/C result. Read `RESULTS.md` after the pipeline completes.

## Decision

The one proposed document `physical-clearance-chain` was **REJECTED**. Two of three independent CADs passed the bounded physical-repair gate, but the third recorded native MuJoCo arena/contact warnings. The predeclared native-health veto applies even when the numerical pass threshold is met. No second proposal or test-based repair is allowed in this final cycle.

B and C now share the same frozen S3 bank containing the two retained documents:

- `physical-disassembly-failure-repair`
- `physical-directional-clearance`

S3 content SHA256: `6235329cf469a5c770b7b21438849f8169cea5325d9f1c4b2ecea16de2bdcc91`.

The rejected candidate remains available as evidence under `memory/candidate/`; it is not loaded by final B/C. Document count or availability is not proof of performance improvement. Model weights do not change.

Byte comparison confirmed that S3's two document bodies and validation references are identical to S2. Thus this extra-learning cycle did **not** change the admitted procedural contents. The bank's `content_sha256` also hashes its manifest (including version and creation metadata), so a changed bank checksum alone must not be called a learned-memory update.

## Actual independent validation episodes

|CAD|Committed removals at end|Physical queries charged|Logical LLM calls|Complete disassembly|Independent event replay|Native warnings|Procedure gate|
|---|---:|---:|---:|---|---|---:|---|
|03756|12/16|240|2|No|PASS|0|Pass|
|08243|4/12|104|2|No|PASS_VERIFIED_PREFIX|0|Pass|
|05828|3/13|47|8|No|PASS_VERIFIED_PREFIX|40|Veto|

The gate observes later accepted removals after physical rejections; it does not prove that a new document caused those actions. It does not require complete disassembly. No validation arm without the candidate was run, so these rows do not estimate the candidate's causal benefit.

For 08243, the worker lifecycle ends with return code -9 around the wall deadline plus the driver's fixed cleanup grace. The retained record contains one unfinished charged removal query. Its result is unknown. Replay verifies completed events only; it does not manufacture a result for the unfinished query. The saved episode, cost, and failure stay unchanged and are not retried. The lifecycle timestamps and last recorded planner elapsed time are different measurements.

For 05828, the actual worker log contains 20 insufficient-constraint-arena warnings and 20 contact-arena-full warnings. MuJoCo arena capacity is a separate internal workspace from the actor's 4 GiB peak-RSS guard. Do not label these warnings as a learned collision/support failure or conclude that increasing the actor cap fixed them. Deterministic replay can reproduce an engine warning, so replay agreement alone is insufficient.

## Next stage and immutable conditions

`outputs/protocol/freeze.json` was written at `2026-10-19T16:15:16.905965+00:00`, before opening final test geometry. The final cohort is four previously unused official ASAP test CADs, each requiring at least ten removals. Each CAD receives one first budgeted episode per arm: A code/no documents; B code/frozen S3; C conditional graph + LLM order + fixed DFS/frozen S3.

All final arms retain gpt-6-luna/low, eight logical CLI calls, 240 charged physical queries, 900 seconds, 4 GiB peak RSS, the same checkpoint/restore API, and one planner worker at a time. Actual use is measured; caps do not imply identical consumed tokens or wall time. Input conversion and post-score replay are separate from the planner episode.

Do not rerun started final episodes, change actors or documents after the freeze, discard resource-limited outcomes, or call the four-CAD pilot a broad industrial success-rate estimate. Final reporting must include native-health-qualified outcomes, operational failures, token uncertainty, actual replays, preservation hashes, and the GitHub publication receipt. No PPT before user review.

Primary evidence: `outputs/development/new_document/admission.json`, the three `outputs/development/full_validation/*/{result,admission,engine_health,physical_audit,lifecycle_final}.json` records, `outputs/development/complete.json`, `memory/S3.json`, and `outputs/protocol/freeze.json`.

# v7 change log (v6 → v7)

Each entry: what changed, why (v6 evidence), effect on arms, verification state.
States: PLANNED / IMPLEMENTED / OFFLINE-TESTED / NATIVE-TESTED (real simulator) / EVALUATED (fresh pilot).

No v6 file is edited. v7 imports v6/legacy modules read-only and keeps adapted copies under `disassembly_repair_v7/`.

## Software repairs (search bookkeeping / scheduling). These are NOT learned physical skills.

### R1. Exact-state search ledger in every snapshot — all arms
- What: `snapshot['search_ledger']` summarizes per exact state: candidates, tested/untested counts, rejected, accepted edges → child, `known_dead_end`, checkpoint handles, `resumable_checkpoints`. Derived only from this episode's trace + public part data (`shared_api.py: SearchLedger`).
- Why: A/05954 lost track of an exhausted accepted edge; B/05954 programs could not see which saved states still had untested actions after program replacement.
- Effect: information only; chooses no action. Prompt text: `contracts.V7_COMMON` (appended, identical for A/B/C).
- State: OFFLINE-TESTED (`tests/test_synthetic.py`), NATIVE-TESTED in regression.

### R2. Dead-end re-entry guard — all arms
- What: check/remove of an action already accepted at this exact state into a known-dead-end child returns `valid=False, reason=known_dead_end_child`, no physics, not charged, logged in `recovery_state.guarded_requests`.
- Why: A/05954 re-entered `3/-y` 59 times (checks 102–160), each re-entry a charged check plus a restore. Physics is deterministic per exact state key (59 re-entries always produced child `d9a11272…`).
- Effect on budgets: the 240-check physics budget is unchanged; guarded responses are not physics checks. This changes v6's sentence "every check/remove consumes one check" for this single deterministic case; recorded here and in the prompt.
- Effect on C: none in practice (v6 C never re-enters an exhausted child).
- State: OFFLINE-TESTED (preserved A code loops under v6 runtime and finishes under v7 on the synthetic trap world), NATIVE-TESTED in `outputs/regression/a_v7`.

### R3. Host state checkpoints after committed removals; exact-state checkpoint reuse — all arms
- What: after each committed removal the host stores one checkpoint for the new exact state (same 128 cap; skipped and logged at cap). `checkpoint()` on a state that already has one returns the existing handle.
- Why: B/05954 call-2 program created no checkpoint, so after program replacement no 1-/2-removal parent state was restorable without re-executing physics.
- Effect: restore remains the planner's decision. This is a state-serialization primitive explicitly allowed by the handoff; it is not a host DFS. Recorded as a protocol change.
- State: OFFLINE-TESTED, NATIVE-TESTED in regression.

### R4. A/B turn lifecycle: progress facts + no-progress stop — A and B identically
- What: after each execute turn the host records checks/removals/restores/guarded requests/dead-end status; the next prompt gets `turn_progress_feedback`. Two consecutive execute turns without a new charged physics check end the episode (`no_progress_stop`).
- Why: B/05954 calls 3–8 each 113→113 checks, 707,037 tokens, no state change.
- Effect: bounded token use; A/B still own all search. A model response alone is not progress.
- State: OFFLINE-TESTED (synthetic), NATIVE-TESTED with preserved B responses (`outputs/regression/b_v7`).

### R5. C scheduler: per-state order memory + paced re-ranking — C only
- What: one order per exact state (a new state inherits its nearest ranked ancestor's order); ranking calls on first visit of a state, after the committed window W of that state's order is fully tried, or after a new instability there; W = max(6, ceil(remaining checks / (remaining calls after this call + 1))). Each call records `call_reason`, window, effective order, rank-change statistics.
- Why: C/06444 re-ranked every 6 failures (all 8 calls spent by check 36); `20/+y` moved 11th → 55th after six checks; v6 used a single global order for parent and child states.
- Effect: same LLM role (rank only), same DFS/graph, same call cap; calls are spread over the check budget. It does not force any action forward.
- State: OFFLINE-TESTED (synthetic), NATIVE-TESTED with preserved C responses replayed under the v7 scheduler (`outputs/regression/c_v7`; replayed responses are not conditioned on v7 prompts).

### R6. Compact prompt view of the observation — all arms identically (found during pre-freeze review)
- What: the observation copy placed in the model prompt omits repeated per-check `collision_policy` boilerplate (3.9 of 5.5 KB per check row), elapsed times, remaining lists, resolved vectors, before-state keys and sample coordinates; keeps at most two collision details (kind/other part/depths); checkpoint rows keep handle/state_key/removed_count/creation index; C graph edges keep from/to/direction. Runtime `api.snapshot()`/`api.checkpoints()` are unchanged and full.
- Why: v6 prompts grew ~6 KB per failed check at the current state (C/06444 call 8: 305,610 bytes at check 36). R5 moves C calls later (e.g. root re-rank at checks 70, 105…), and R3 adds checkpoints, which would hit the unchanged 512,000-byte cap and end episodes with `limit`.
- Effect: measured on preserved v6 prompts: C/06444 call 8 305,610→98,766 bytes; B/05954 call 8 322,753→131,600; growth ≈1.3 KB per additional check row. Cap unchanged.
- State: OFFLINE-TESTED (`tests/test_synthetic.PromptView`, measurements above), NATIVE-TESTED in the real-provider smoke run (`outputs/smoke/`).

## Physics condition decision (v7.1, 2026-10-20; user asked to decide physics first)
- P2 candidate (`physics_variants.P2_persist_up_to_stable_penetration`): initial interference <= 1 mm (`stable_penetration_m`, already used by the initial screen, stability and the MuJoCo-convex path rule) may persist along a path with growth <= 0.02 mm; deeper initial interference keeps the 0.2 mm cap. Rationale and pre-specified adoption rule: `analysis/PHYSICS_DECISION.md` (written before P2 diagnostics).
- The P0 freeze (`outputs/protocol/freeze.json`) is superseded before any pilot episode; the new freeze is `outputs/protocol/freeze_v7.1_P2.json` (created only if P2 passes its adoption checks).
- Prompt for all arms gets `PHYSICS_NOTES[P2]`; `observation.physics.initial_interference_rule` states the rule. Software repairs R1–R6 unchanged.
- Pilot amendment (user-approved, before outcomes): backup pool of never-opened official test products (5–10 parts, part count descending) after the primary training pool.

## Physics: evaluated checker in v6 and v7 regression (P0)
- The evaluated collision/stability rules, tolerances, fixture rule and six source-axis motions are unchanged in v7.
- New diagnostic tools only: `physics_audit.py` (sample-0 lock audit), `feasibility.py` (non-LLM reference search with the same simulator).

## Pilot design changes (pre-registered in `outputs/protocol/freeze.json`)
- P1. Candidate pool: official ASAP **training** archive products never opened by this project, 11–20 parts. Reason: official test split has 23 unopened products, all ≤ 10 parts.
- P2. Added physical feasibility qualification: a complete reference sequence found by the non-LLM search (cap 2500 physical checks) before evaluation. The sample-0 lock audit is recorded but NOT an exclusion: 06444's fixture lock (18↔1) disappeared after 5 removals because residual settling moved part 18. Reason: v6 failures could not separate planner ability from checker infeasibility. The reference is never given to planners.
- P3. Code/conversion copies: `data_tools/convert_cad.py` is a verbatim v6 copy except the CoACD dependency path.

## Not changed
- Model gpt-6-luna / low via CodexCLIProvider; limits (8 calls, 240 checks, 900 s, 4 GiB, 10M instructions, 128 checkpoints, 256 restores, 512000/64000 bytes); mandatory initial document read for B/C; S3 bank bytes (two documents, hash-checked equal to v6); one planner at a time.
- No new SKILL.md was proposed or admitted in v7.

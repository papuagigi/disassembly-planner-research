# v7 regression on known v6 CADs (development only, not first encounters)

Method: `offline/regression.py`. No model call. Providers replay preserved v6 responses in original call order (A: 1, B: 8, C: 8 responses); they were **not** conditioned on v7 prompts. Physics: answers for exact (state, part, direction) queries recorded in any v6 trace of the same CAD are replayed; unrecorded queries and accepted removals without a stored child pose run the unchanged real simulator. `recomputed_child_key_mismatches=0` everywhere: recomputed accepted removals reproduced the recorded child state keys (determinism check). Regression ran concurrently with a 10-worker reference search, so wall-time-limited rows are slower than an isolated run.

| scenario | termination | final | best | checks | first valid | accepted-edge re-entries | guarded | restores | auto ckpt | calls | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v6 05954/A (raw) | wall_time | 3 | 3 | 160 | 5 | 59 | – | 118 | – | 1 | 900 |
| a_v6_repro (v6 runtime, strict oracle) | BudgetLimit@160 | 2 | 3 | 160 | 5 | 59 | 0 | 120 | 0 | – | 60 |
| a_v7 (same A code, v7 API) | check_budget | 3 | 3 | 240 | 5 | **0** | 5 | 16 | 6 | 1 | 594 |
| v6 05954/B (raw) | call_budget | 3 | 3 | 113 | 7 | 0 | – | 0 | – | 8 | 588 |
| b_v6_repro (call-3 code at dead end) | returned | 3 | 3 | 113 (+0) | – | 0 | 0 | 0 | 0 | – | 1 |
| b_v7 (B responses 1–8, v7 actor) | **no_progress_stop** | 3 | 3 | 113 | 7 | 0 | 0 | 0 | 3 | **4** | 37 |
| b_resume_probe (fixed program, not LLM) | returned | 3 | 3 | 120 (+7) | – | 0 | 0 | 1 (state changed) | – | – | 81 |
| v6 06444/C (raw) | wall_time | 0 | 0 | 82 | none | 0 | – | 0 | – | 8 (all by check 36) | 900 |
| c_v7 (C responses replayed, v7 scheduler) | wall_time | 1 | 1 | 132 | 71 | 0 | 0 | 0 | 1 | 6 (2 unused) | 905 |

## What this shows

- **A**: the v6 trace is reproduced exactly offline (160 identical queries, 59 re-entries). With the v7 API the **same generated program** makes 0 re-entries; 5 guarded (uncharged) requests replace them, restores drop 118→16, and the freed budget tests 87 previously untested actions. Final/best stay 3/12, equal to the physically explored maximum on 05954 (see PHYSICS_FEASIBILITY.md), so no planner change could have exceeded it under the evaluated checker.
- **B**: the replayed v6 programs still make no progress after the dead end (they were written without the ledger), but the v7 rule stops after calls 3–4, so calls 5–8 (≈470k tokens in v6) are not spent. Host checkpoints made the 0/1/2-removal states restorable; `search_ledger.resumable_checkpoints` lists them with 65/65/9 untested actions. A fixed replacement program using only those facts restored the 2-removal state and ran 7 new checks (one accepted, a different 3-removal state). This verifies resumption is *possible* through the common API; whether gpt-6-luna uses it is a pilot question.
- **C**: ranking calls occur at checks 0/35/70 (window 35/35/34) at the root, then on the first visit of the child state and after an instability there; 2 calls remain at the wall deadline instead of all 8 being spent by check 36. With the replayed (stale) v6 orders the first accepted action came at check 71. This is a mechanics check; it is not evidence that v7 C performs better with fresh calls.

## Limits

- Replayed responses are not v7 behavior of the evaluated model. All pilot-relevant claims need fresh calls.
- 05954/06444 have sample-0 locks (PHYSICS_FEASIBILITY.md); full disassembly there is not expected under the evaluated checker regardless of planner.

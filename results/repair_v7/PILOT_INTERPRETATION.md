# v7.1 pilot interpretation (pre-registered first encounters, P2 physics)

Protocol: `outputs/protocol/freeze_v7.1_P2.json` (+ amendment A1). 3 never-opened official ASAP training CADs selected in frozen order, each with a non-LLM complete reference under P2 that planners never saw. gpt-6-luna/low, v6 limits (8 calls, 240 checks, 900 s, 4 GiB), one episode per arm, sequential, no reruns. B/C used the unchanged v6 S3 documents (2 SKILL.md). Raw: `outputs/pilot/trials/*/*/result.json`; table: `PILOT_RESULTS.md`, `pilot_results.json`, `pilot_trials.csv`.

## 1. Official outcomes (unchanged by any later diagnosis)

| CAD (parts) | A | B | C |
|---|---|---|---|
| 06146 (15) | **14/14**, 71 checks, 1 call, 197 s | **14/14**, 122 checks, 2 calls, 642 s | 8/14, `memory_guard` at 19 checks, 119 s |
| 03012 (13) | **12/12**, 82 checks, 2 calls, 284 s | **12/12**, 39 checks, 2 calls, 239 s | **12/12**, 61 checks, 8 calls, 350 s |
| 05902 (12) | **11/11**, 75 checks, 1 call, 489 s | 2/11 (best 3), 131 checks, hard timeout at 918 s | 9/11, time budget, 82 checks, 916 s |
| success | 3/3 | 2/3 | 1/3 |
| provider tokens (in+out) | 90,344 | 158,667 | 826,352 |

Unknown-usage calls: 0. MuJoCo native warnings in worker logs: none. Independent native replays (`replay/audit.json`): **PASS** — 8 episodes exact, 05902/B `PASS_VERIFIED_PREFIX` (130 completed queries, 3 guarded requests, 2 restores verified; the one check unfinished at the hard kill keeps its charge and has no invented result). Viewer: `python3 -m http.server 8770 --bind 127.0.0.1 --directory disassembly_repair_v7` → `http://127.0.0.1:8770/viewer/index.html` (pre-evaluation reference paths shown after evaluation only).

## 2. Infrastructure vs planner (separated)

- **06146/C — infrastructure.** The 4 GiB RSS guard stopped C at 8/14. Replaying the same 8 model responses with a 16 GiB guard reproduces the pilot trace exactly for its 19 checks and reaches 14/14 at check 46 (103 s). All 8 calls had been spent by check 14, so the rest is deterministic: this is an exact counterfactual. Memory spikes are transient and per-check (0.4→4.4 GiB within ~3 s; peak 5.45 GiB), i.e. physics computation on specific states, not a C-path leak (03012/C peaked at 0.62 GiB). (`outputs/diagnostics/memory_probe/memory_probe.json`)
- **05902/B — time budget with an enforcement anomaly.** No removal after 860 s; 7 checks still ran after 900 s and the driver hard-killed at 920 s. Offline reproductions stop correctly; cause unresolved. Outcome (2/11) unaffected.
- **05902/C — planner/budget.** Physics on 05902 is slow (median 4.6 s, max 60 s per check); C reached 9/11 at the wall cap with all calls spent by check 36.

## 3. Software repairs observed in fresh runs (v7 R1–R6)

- Accepted-edge re-entries (A/05954 had 59 in v6): **0** in all 9 episodes.
- The common `search_ledger` was used by **all 6** generated A/B programs (dead-end flags, untested counts, resumable checkpoints). 05902/B resumed saved states (2 state-changing restores) and triggered the dead-end guard 3 times (uncharged).
- No-progress rule: one A turn (03012) made no new check; the next turn succeeded. No episode was stopped by the rule.
- Remaining A/B inefficiency outside the repairs: 06146/B re-queried 6 already-rejected actions at the same state (up to 14 times; 51 repeated rejected checks). The v7 guard only blocks re-entry into known-dead-end children by design.
- C scheduling: same-state re-rank churn is gone, but "rank on every first visit" still spends all 8 calls early when descent is easy (06146 by check 14, 03012 by 53, 05902 by 36); later states inherit ancestor orders. On 03012 this was enough to finish.

## 4. What can and cannot be concluded

- Can: with the v7 repairs, under P2 physics, on three CADs that are physically solvable, the generated-code planner without documents (A) fully disassembled all three on first encounter within budget; failures elsewhere are attributable to a memory cap (06146/C), a wall budget (05902/B, 05902/C).
- Cannot: any SKILL.md benefit or harm. A−B differs by documents plus a mandatory read call; n = 3 CADs × 1 episode; LLM sampling is stochastic; B's only failure is a timed-out search on the slowest CAD. B−C differs in architecture and scheduling. No fixed-architecture memory ablation was run.
- Cannot: industrial validity. Selection required v6 initial stability and a non-LLM reference path; physics is P2 (a recorded change from v6); motion is six-label straight translation.
- v6 vs v7 is not a controlled comparison (different CADs, physics rule, software, prompt view).

## 5. Interpretation of the v6 failures in light of v7

05954 and 03114 are physically limited to 3 and 2 removals under the evaluated checker (straight motion, enclosing geometry; unchanged by P2 or 32 motion directions); 06444 reaches 19/20 and its last part fails by 3 µm. So v6's 0/9 mostly reflects test CADs that were not fully disassemblable in this physics model, plus search/scheduling defects (now repaired) on 06444.

## 6. Options that need a user decision (not started)

1. Repeat the pilot (same frozen protocol) on more never-opened CADs and/or several episodes per arm to estimate variance; a memory cap revision (e.g. 6–8 GiB) would be a recorded protocol change.
2. A fixed-architecture memory ablation (A vs B already share architecture; add C without documents) with enough episodes to detect a difference.
3. A new SKILL.md development cycle from development-CAD failure logs, independent validation, then a frozen S4 for B/C.
4. Engine hardening: deadline check inside the API, process-group cleanup, memory-spike mitigation in the source-mesh checker.

# disassembly_repair_v7_3 — STATUS (Codex/Claude handoff entry)

Owner: Claude Code (user-assigned 2026-10-21 KST: "이 계획대로 v7.3을 시작해줘. 성능을 우선하고, 진행 상황은 STATUS.md에 기록하고 핵심 업데이트는 push해줘."). Evaluated model gpt-6-luna/low. v6, v7, v7.1 and v7.2 code/records are unchanged; v7.3 reads them only.

## User decisions
- v7.3 improvement cycle on development data, then a frozen evaluation on NEW CADs. Performance outranks schedule.
- Improvement candidates: world-vector axis discovery, exact-assembly note first, recoverable violations, faster physics.
- Added: also improve SKILL.md itself (conditional procedures, tested reference implementation, model-free rule gate, structured notes incl. failure-only notes, note→general distillation, cost-aware rules, better admission gate).
- Guardrails: development data only for improvement; validation/evaluation frozen before outcomes and run once; A uses the same engine; every outcome reported.
- 2026-10-21 04:40 KST: the user agreed the main first-encounter bottleneck was the general SKILL.md (content, form, no pre-use testing) alongside engine/infra/time issues, and asked for the plan; **a PPT is now the final step** (after the v7.3 results are documented and pushed).

## v7.3 changes (all arms unless stated)
| ID | Change | Evidence / why | Verified |
|---|---|---|---|
| E1 | `fast_geometry.py`: the v3 generalized-winding inside test computed in cache-sized point blocks over 6 threads; same per-point arithmetic | 82 % of check time on 05902 was `_winding_inside` (profile of 12 recorded checks) | 2,220 captured calls / 150k points: values bitwise identical, decisions identical, 4.7x faster on that function. Acceptance: every v7.1/v7.2 episode must replay identically (`outputs/e1/equality.json`) |
| R7 | Contract/schema violations and tool-use rejections re-ask the same request (≤ 2 re-asks, each a counted call); timeouts stay terminal | v7.2: one contract violation (06146 C+note) and two tool-use rejections ended episodes at 0 checks | `tests/test_v73.py` |
| N8–10 | Prompt notes: re-ask rule; exact-assembly notes (`assembly-note-*`) first; directions are world vectors | v7.2: B(S4b+note) ignored the note; S4b "up first" applied to label names | contract test |
| NW2 | Note writer v2: `assembly-note-` prefix, host appends a verbatim "Recorded sequence" (fewest-check success, else longest partial path), failure-only guidance, host-only fallback note | v7.2 notes worked only when someone had succeeded | `tests/test_v73.py` |
| S5 | New general SKILL.md written by gpt-6-luna/low from world-vector evidence (`mine73.py`), must contain a restricted-runtime "Reference implementation"; model-free rule gate on the S5 input CADs (≥ 4/5 full disassemblies within 240 checks), ≤ 3 writer calls with gate feedback | S4b fixed priors failed on lateral assemblies | `outputs/skill_writer/S5_report.json` |
| SEL | New-CAD selection: never-opened ASAP training products, tier 1 = 11–20 parts (v7 order), tier 2 = 8–10 parts; target 4; frozen before extraction | only 21 never-opened 11–20-part products remain (v7 yield 3/75) | `outputs/protocol/selection_candidates.json` |

## Data split (fixed before S5 is written)
- S5 input (mining, notes, rule gate): 05902, 06146, 03012, 01613, 02402 (+ v6 final traces 05954/06444/03114).
- Development validation (held out from S5 writing): 05459, 02406, 07375, 03674 × A(S0)/B(S5)/C(S5) × 2.
- Final evaluation: 4 new CADs from `selection_selected.json` (first attempt A/B/C → note → second attempts). Rules: `campaign.py` docstring.

## Live state (2026-10-20 ~19:35 UTC)
- **E1 accepted**: all 61 recorded episodes (v7.1 pilot 9 + v7.2 52; 3,198 physical queries) replay identically with the threaded winding (`outputs/e1/equality.json`).
- S5 call 1 passed the model-free rule gate 4/5 (05902: the program returned after 79 checks / 2 removals; the other four: 36, 40, 31, 12 checks). Development-only refinement added after that result (≤ 2 more writer calls with gate feedback; adopt only if more gate successes, or equal with fewer total checks; `outputs/skill_writer/S5_refine_report.json`). Refinement calls 2 and 3: same 4/5 (05902 used 240 checks, 1 removal) → not adopted. **S5 = writer call 1** (`memory/S5.json`, one document `world-family-disassembly-search`). Smoke with S5 on 02402 (reduced limits): B and C both 12/12 checks.
- Selection: 13 candidates processed, 0 selected so far (mostly collision-preparation exclusions); 02260 passed qualification and its P2 reference search is running.
- Real-provider smoke on 02402 (reduced limits): A/B/C all succeeded (12/12/24 checks, 0 re-asks); note writer v2 produced `assembly-note-*` with the verbatim Recorded sequence (`outputs/smoke/`, `memory/notes/smoke_asap_02402/`).
- Tests: `tests/test_v73.py` + inherited `tests/test_hardening.py`: 19/19 pass.
- Next: E1 PASS → S5 chosen → freeze + `python -m disassembly_repair_v7_3.campaign validation` (after selection finishes; timed episodes need a quiet machine) → `... campaign evaluation` → replays → aggregate → write-up → push.

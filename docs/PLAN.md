# Final bounded long-horizon document-memory study

User-authorized on 2026-10-19. This is the last development → validation → freeze → test cycle. No performance-dependent repair loop. Preserve every earlier study and presentation. PPT authoring waits for the user to review the results.

## Question and scope

Do failure-derived, LLM-readable SKILL.md procedures help first-episode full disassembly on unseen official ASAP CADs? A=LLM-generated restricted Python/no library; B=same actor/frozen documents; C=conditional graph/LLM ordering/fixed DFS/the identical documents. Python generated for an episode is not a stored skill. No model-weight update. No desired winning arm.

## Roles fixed before new labels

- Retain all 90 discovery-CAD local-probe experience and the two admitted S2 documents from v3.
- Add full-search experience on exactly 10 training CADs with 11–20 parts: reuse the four qualifying v3 discovery inputs in their original order, plus the first six newly qualified training inputs. Reuse means additional experience, not additional unique CADs.
- Independent validation: the next 10 qualified training inputs, never in proposal evidence or prior discovery. No validation-driven rewrite.
- Final test: first 10 newly qualified official test inputs, prioritizing 11–20 parts, excluding prior opened geometry IDs and duplicate shape fingerprints. Before any new geometry/model calls,the reserve is extended with21–30part and then31+part backup CADs because only36unopened11–20part test CADs remain. This is a metadata-only source-yield safeguard,not outcome selection. Report actual size strata. Selection uses initial geometry/physics only, never actor success or a reference solution. Test geometry is opened only after bank/actor freeze.
- Source reserves are ordered by alternating 11–15 and 16–20 part bins, ascending source OBJ bytes/count/ID within each bin. Keep every exclusion. Finite reserve:150training candidates and75unopened official test candidates (36primary,24with21–30parts,15with31+parts). Backup bins retain ascending source bytes/count/ID. If fewer than required qualify, report incomplete; never shrink the denominator or relax physics.
- Earlier v3 evaluation continues under its frozen 180-second protocol. Wait for its model evaluations before new CPU-heavy preparation; wait for its completion before timed v4 learning. No overlapping final v4 timed episodes and other preparation/replays.
- After v3 is complete,offline full-search discovery on the four already-selected inputs may overlap preparation of the remaining training inputs. These are the same four planned jobs,protected by a shared collection lock and reused without rerun. Source/time budgets stay fixed;record offline contention as a learning-cost limitation. Proposal waits for all10discovery episodes;validation and final scored A/B/C remain after preparation is complete.

## Common budgets and physics

gpt-6-luna / low. Per full-search episode: 8 logical CLI model turns, 240 physical queries, 900 seconds, 10M metered opcodes, 128 checkpoints, 256 restores, 1 GiB RSS; same API and input state for final A/B/C. Required initial document review is charged. Unknown provider token usage stays unknown. No API-key fallback or paid-credit purchase.

Use unchanged v3 source-mesh extraction and MuJoCo residual stability: six fixed-orientation source-axis straight translations, one permanent original fixture, gravity/friction with assumed physical properties. Full success means n−1 committed stable removals. Virtual restore is search-state restoration, not physical reassembly. Conversion exclusions are not planner failures. 15 minutes is an operational ceiling, not a proof all inputs are solvable.

Prospective input-capacity amendment before any v4 model call:the earlier50part v3 input exceeded the common1GiB actor memory cap before any model call in all arms. Run a fresh actor initialization/shared-snapshot preflight with S0,max_calls=0,and zero physical queries. Require a32MiB margin below the unchanged1GiB episode cap. This hardware-compatibility gate uses no policy outcome or reference path. Preserve all exclusions and raw qualification receipts.

## One learning and admission attempt

1. Run C with prior S2 on all 10 development CADs for complete-tree exploration within the above caps, stopping on success. Record collisions, instability, accepted removals, exact checkpoints, actual restores and alternate-branch outcomes. Actual backtracking must be measured; do not manufacture or claim it if absent.
2. Independently replay the finished physical events. Summarize only actual development failures and subsequent actions. Generate at most one portable procedural SKILL.md. No exact CAD IDs, answer sequences, stored Python policy or unsupported physical claims. Preserve prior documents byte-for-byte.
3. Run the candidate with B on each of the 10 independent validation CADs under the same full-search caps. A validation is a bounded functional pass if full disassembly succeeds OR a previously rejected target is later stably committed in a measured valid alternative direction/changed geometry. An instability repair must commit a different part first and then the original target/direction. No unsafe fixed-part attempt or invalid restore; all finished events require independent replay. These checks establish bounded usability/repair evidence, not benefit over a no-document baseline.
4. Require at least 7/10 functional passes and all replay audits valid to admit the candidate. No repeated validation, no candidate rewrite. If rejected or generation fails, retain prior S2 only and report the failed learning attempt.
5. Freeze S3 (prior documents plus admitted candidate, or explicit prior-only fallback), actor sources, physics sources, input reserve, API and caps before opening final test geometry.

## Final comparison and stopping

One first episode per CAD/arm, rotating A/B/C order and running serially. No cross-test memory update, no silent retry of a started episode, no removal of failed outcomes. Report full success, final/best progress, failed/duplicate checks, actual backtracks/undone accepted removals, calls, token usage and wall time. B−A tests document availability plus charged review; C−B changes an architecture bundle. Changed learning and wall cap prevent attributing v3→v4 differences solely to memory.

Native MuJoCo replay verifies all retained episodes; any interrupted charged final check is marked unknown and not invented. Reference paths come only from successful actual episodes after scoring. Primary artifacts are agent MD/CSV/JSON and replay. No PPT until results are reviewed. Infrastructure defects may be repaired transparently, but no policy/skill retuning against final test outcomes. All 10 development, 10 validation and 30 final episodes are a finite single pass.

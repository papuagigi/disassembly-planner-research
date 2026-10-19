# Large-CAD physical-document first-episode comparison

All old results/PPT remain preserved. New official ASAP training sources develop/validate the document; final inputs are unseen-to-project official ASAP test CADs with11+components/10+required removals. They are anonymous engineering CAD,not verified factory provenance. Model=gpt-6-luna/low;8calls/240checks/180seconds;read costs included. One first episode per new CAD/arm. Initial physics only,no full-path or actor-success selection gate.

|Arm|Success|Mean final progress|Mean best progress|Mean checks|Mean calls|Mean tokens|Mean seconds|
|---|---:|---:|---:|---:|---:|---:|---:|
|A|4/12|0.500|0.586|96.8|1.42|56627|139.4|
|B|3/12|0.445|0.475|91.4|2.42|89250|139.7|
|C|3/12|0.483|0.483|57.2|7.00|300194|153.7|

## Evidence boundaries

Read outputs/development/complete.json and new_document/admission.json for actual new discovery/independent-validation counts and whether the new physical document passed its predeclared gate. S2 retains the previous narrowly admitted physical procedure; rejected new candidates are excluded from B/C. Downloaded CAD counts are not learned CAD counts. Model weights never update. Prior strict whole-actor rejection is preserved;bounded physical-repair admission is not full-planner robustness.
B-A changes frozen document availability plus required initial review. C-B changes graph/DFS/code-generation/call scheduling as a bundle; no isolated graph/DFS effect. No final C0 arm,so C memory efficacy is not identified separately.
Final progress is the accepted state at termination;best progress is the greatest accepted prefix observed during the search. A backtracking planner can have lower final than best progress after undoing a branch. Neither partial-progress metric substitutes for full goal success. Undone accepted removals measure branch-search work,not removal of nonrequired components.
Read body bytes,declaration,observable priority change and improved held-out outcomes are separate. See memory_context_audit.json,behavior_audit.json,raw code/ranks and actual event replays. Token calls include failed-provider usage. Cached input and reasoning are not double-counted. Missing usage is unknown.
LLM calls mean logical CodexCLIProvider.complete invocations/CLI planner turns,not independently observed backend HTTP requests. The CLI runs statelessly in an empty temporary working directory with user configuration,memories and major agent-tool features disabled;any recorded tool activity invalidates the response. Provider token totals include CLI context as well as supplied planner text.
time_budget_prefixes.csv is an observed timeline prefix at30/60/120/180seconds from one180-second policy,not separate per-budget retraining/reruns. A failed early run is not more efficient than successful full disassembly. Use common-success paired rows for cost-only interpretation.
Qualification exclusions and unresolved-within-budget planner outcomes are distinct. No first-episode outcome may be silently retried or removed. MuJoCo/material/scale/fixed-fixture/straight-path limitations remain. Virtual restore is not physical reassembly. No PPT was modified.

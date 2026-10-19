# Agent interpretation of the final three-CAD pilot

## Evidence and scope

This note interprets the nine completed, immutable first episodes in `outputs/evaluation/complete.json`. Independent native replay completion is recorded separately in `replay/audit.json`; the existence of this note does not establish that all replays or publication are complete. Read `outputs/pipeline_state.json` and `outputs/pipeline_complete.json` for current completion status.

The final question is whether failure-derived external procedural memory transfers to a previously unseen mechanical assembly. There is no model-weight training and no memory update from these three test products. A generates restricted Python without document memory. B generates code with readable SKILL.md. C uses a conditional graph, LLM priorities and fixed DFS with the same documents as B. All share the frozen state/checkpoint/restore and physical-check APIs.

The requested model was gpt-6-luna / low. Each final episode had the same 4GiB peak-RSS guard, eight logical CLI turns, 240 physical queries and 900-second limit. The cap is an upper bound, not a requirement to consume every resource. The serial-execution audit checks actual worker windows. Provider records do not independently identify the served backend beyond the recorded request.

All 75 preordered input candidates were processed. Three passed unchanged geometry and initial-physics criteria. The original four-CAD goal was not met. The three-CAD/nine-episode amendment and explicit user confirmation were recorded before any final result. Input exclusions are not planner failures, and no test policy outcome selected or removed a product.

## Actual outcome

|CAD|Required removals|A final / best|B final / best|C final / best|
|---|---:|---:|---:|---:|
|05954|12|3 / 3|3 / 3|1 / 3|
|06444|20|11 / 11|0 / 0|0 / 0|
|03114|21|1 / 1|1 / 1|1 / 1|

|Arm|Full success|Final removals across 53 required|Logical calls|Provider input + output tokens|
|---|---:|---:|---:|---:|
|A|0 / 3|15|3|70,112|
|B|0 / 3|4|12|893,286|
|C|0 / 3|2|24|1,364,693|

The evaluation token total is 2,328,091 across 39 logical calls; unknown-usage calls are zero. `analysis/token_usage.json` also separates development, inherited evidence and new work. Cache input and reasoning are subsets, not extra quantities to add to input + output. These are provider-reported CLI totals, not only the visible planner prompt and not a monetary invoice.

The final removal count is the surviving accepted state at termination. Best progress is the greatest accepted prefix reached earlier. On 05954 C reached three removals, then restored two and ended with one. Do not substitute best progress for the final state or full-task success. This comparison has no common successful subset for a cost-per-success comparison.

Eight episodes stopped at the wall limit; B on 05954 stopped at the logical-call limit. No final worker recorded native engine warnings, provider errors or nonbudget code-execution errors. Five caught wall-limit exceptions are classified as budget stops, not Python policy bugs; raw result hashes are unchanged. Read `analysis/reporting_classification_audit.json`.

## What the logs explain, and what they do not

On 06444 all three arms received the same initial state. A's third physical query accepted part20 in +y and committed it. B completed 98 initial-state queries and C completed 81, but neither tested that part-direction pair at that exact initial state before the deadline. The complete raw state key includes surviving poses and velocities. Inspect `outputs/evaluation/trials/asap_06444/{A,B,C}/result.json` and the post-score `analysis/root_action_coverage.json`.

This is direct evidence of different search coverage under the budget: at least one feasible initial action existed, and B/C missed an action observed to work in A. It is not evidence that the assembly had no feasible first move. A valid first move also does not prove a full disassembly sequence exists under the local action API.

The observation does not isolate a harmful sentence in SKILL.md. Generated code, ordering, graph/DFS machinery and call scheduling differ. B-A changes document availability plus its charged review; C-B changes several architectural choices together. There is no final C memory-off ablation, repeated random-seed comparison or backend-model ablation. Do not claim the library, graph, DFS or LLM alone caused this result.

On 05954 A made 118 restores, of which 59 changed physical state; 59 accepted removals were later undone. C made two restores that changed state. B made none. All arms recorded zero repeated rejected queries. Restore counts, undone accepted actions and useful exploration are distinct: a restore is not automatically evidence of productive backtracking, and repeating an accepted action after branch restoration is not automatically a defect.

## What actually changed in memory

The current-line development count is 94 unique CADs, including 90 prior local-probe inputs. These are not 94 completed full disassemblies. Long full-search evidence comprises ten episodes on eight unique CADs: eight preserved earlier 1GiB episodes and two extra 4GiB episodes on the already-used 05459/01613. The latter completed 16/16 and 10/10 removals, respectively, as development examples. Training budgets are mixed and are not a controlled 1GiB-versus-4GiB experiment.

One new physical-clearance-chain document was generated from development evidence. On three separate validation CADs, two met the bounded repair gate, but native arena/contact warnings on the third triggered the registered veto. The candidate was REJECTED. See `outputs/development/new_document/admission.json` and `analysis/VALIDATION_AND_FREEZE.md`.

B/C therefore used exactly the same two previously accepted document bodies. S3 records a freeze/version, not an accepted procedural improvement in this extra cycle. A changed manifest hash alone is not evidence of learning. The pipeline demonstrates candidate generation, validation, rejection and frozen retrieval; this final pilot does not demonstrate improved unseen-product success from a new memory update.

## Physical and statistical limits

Inputs are original engineering CAD/OBJ from ASAP, with no verified factory-product provenance. The local checker samples straight extraction in six source-axis directions with fixed orientation and tests the residual assembly using MuJoCo gravity/contact/friction. It assumes density, inertia, friction and one permanently world-fixed original part as external workholding. It does not simulate unscrewing, arbitrary rotation, a robot/gripper or real reassembly. The fixed part does not fall under gravity. Virtual restore rolls search state back; it is not a physical repair operation.

Initial stability screening did not certify a complete feasible sequence. Full extraction feasibility remains unresolved unless independently established by recorded evidence. Root-action coverage can only describe the declared finite local API; even complete rejection of all initial actions would not establish real-world or original-ASAP impossibility. Five charged queries have no completed outcome in the raw trace; preserve their cost and mark their results unknown instead of inventing a replay result.

With three products and one first episode per arm, the result is a descriptive pilot, not an industrial success-rate estimate. No full-task success occurred. Neither a general superiority claim for A nor a general impossibility claim for skill memory is justified. Preserve the negative result and stop this bounded improvement cycle. PPT waits for the user's result review.

## Continuation and review entry points

- Local contingency prompt: `CLAUDE_CONTINUATION_PROMPT.md`; recovery rules: `CLAUDE.md` and `AGENT_HANDOFF.md`.
- Raw score receipts: `outputs/evaluation/complete.json` and per-arm immutable `result.json` files.
- Derived tables: `analysis/trials.csv`, `analysis/aggregate.csv`, `analysis/results.json`.
- Conditions and provenance: `analysis/matched_conditions_audit.json`, `analysis/serial_execution_audit.json`, `analysis/source_hash_audit.json`.
- Document delivery versus semantics: `analysis/memory_context_audit.json` and `analysis/behavior_audit.json`; byte delivery does not prove adherence or benefit.
- Actual native trajectories: `replay/index.json`, `replay/audit.json`, `viewer/index.html` and `analysis/public_replay_bundle.json`.
- Public source/results/demo: https://github.com/papuagigi/disassembly-planner-research . Public snapshots omit full native environments, source CAD archives and raw provider logs; use the existing local workspace for an exact resume.

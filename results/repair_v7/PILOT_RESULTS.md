# v7 pilot results (pre-registered, first encounters)

Scope: never-opened official ASAP CADs (training split primary, test split backup) qualified by unchanged v6 conversion/initial physics and a non-LLM reference sequence under physics P2 (never given to planners). Episodes ran under P2. gpt-6-luna/low, v6 limits, one episode per arm, sequential. Local physics model; small pilot; not industrial validation. v6->v7 changed several mechanisms (CHANGELOG.md), so no single-cause attribution.

| case_id | condition | success | termination_class | native_engine_errors | final_removed | best_removed | required_removed | reference_length | checks | first_valid_action_check | accepted_edge_revisits | repeated_rejected_queries | guarded_requests | restores_with_state_change | restores_without_state_change | no_progress_calls | llm_calls | total_tokens | unknown_usage_calls | elapsed_seconds | native_engine_health |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| asap_06146 | A | True | success | 0 | 14 | 14 | 14 | 14 | 71 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 22765 | 0 | 197 | NO_NATIVE_WARNINGS_RECORDED |
| asap_06146 | B | True | success | 0 | 14 | 14 | 14 | 14 | 122 | 1 | 0 | 51 | 0 | 0 | 0 | 0 | 2 | 53688 | 0 | 642 | NO_NATIVE_WARNINGS_RECORDED |
| asap_06146 | C | False | memory_guard | 0 | 8 | 8 | 14 | 14 | 19 | 1 | 0 | 0 | 0 | 0 | 0 | None | 8 | 275055 | 0 | 119 | NO_NATIVE_WARNINGS_RECORDED |
| asap_03012 | A | True | success | 0 | 12 | 12 | 12 | 12 | 82 | 13 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 44610 | 0 | 284 | NO_NATIVE_WARNINGS_RECORDED |
| asap_03012 | B | True | success | 0 | 12 | 12 | 12 | 12 | 39 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 52308 | 0 | 239 | NO_NATIVE_WARNINGS_RECORDED |
| asap_03012 | C | True | success | 0 | 12 | 12 | 12 | 12 | 61 | 25 | 0 | 0 | 0 | 0 | 0 | None | 8 | 298141 | 0 | 350 | NO_NATIVE_WARNINGS_RECORDED |
| asap_05902 | A | True | success | 0 | 11 | 11 | 11 | 11 | 75 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 22969 | 0 | 489 | NO_NATIVE_WARNINGS_RECORDED |
| asap_05902 | B | False | worker_failure | 0 | 2 | 3 | 11 | 11 | 131 | 3 | 0 | 24 | 3 | 2 | 0 | 0 | 2 | 52671 | 0 | 918 | NO_NATIVE_WARNINGS_RECORDED |
| asap_05902 | C | False | time_budget | 0 | 9 | 9 | 11 | 11 | 82 | 9 | 0 | 0 | 0 | 0 | 0 | None | 8 | 253156 | 0 | 916 | NO_NATIVE_WARNINGS_RECORDED |

## Per arm

| arm | episodes | successes | final removed | best removed | required | checks | calls | tokens (in+out) | unknown-usage calls | termination classes |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 3 | 3 | [14, 12, 11] | [14, 12, 11] | [14, 12, 11] | [71, 82, 75] | [1, 2, 1] | 90344 | 0 | ['success', 'success', 'success'] |
| B | 3 | 2 | [14, 12, 2] | [14, 12, 3] | [14, 12, 11] | [122, 39, 131] | [2, 2, 2] | 158667 | 0 | ['success', 'success', 'worker_failure'] |
| C | 3 | 1 | [8, 12, 9] | [8, 12, 9] | [14, 12, 11] | [19, 61, 82] | [8, 8, 8] | 826352 | 0 | ['memory_guard', 'success', 'time_budget'] |

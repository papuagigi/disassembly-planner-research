# Final v4 agent handoff

Snapshot UTC: 2026-10-19T12:46:43.011408+00:00. Verify live processes and outputs before recovery.

Goal: measure whether development-failure-derived SKILL.md improves first-episode disassembly on unseen CADs. No desired winner. No model-weight training.

Controlling plan: PLAN.md. Exactly one final learning → independent validation → freeze → first-test cycle. Never tune against final tests. Do not rerun started episodes. Existing studies and presentations remain preserved. Claude is not assigned; this document supports recovery only.

State: {'utc': '2026-10-19T11:36:36.230669+00:00', 'pid': 29446, 'status': 'RUNNING', 'phase': 'prepare_development_inputs'}

Actual finished full-search discovery: 4/10. Independent full-search validation: 0/10. First test episodes: 0/30 across a target of10CADs. Earlier90CAD discovery means local physical probes,not90completed disassemblies. Four development CADs are reused for additional full-search experience,six are new;unique discovery after completion=96. Validation is10different newly qualified training CADs. Full-search discovery/validation have11–20parts. Test prioritizes11–20parts with a predeclared21+backup reserve;report actual sizes.

A=generated code/no docs;B=same generated code/frozen S3;C=conditional graph+LLM order+fixed DFS/same S3. Same API,initial state,gpt-6-luna/low,8logical model turns,240physical queries,900seconds. Document review is charged. A's failure-free memory resets between products;within-episode feedback is allowed for all.

Evidence: outputs/input_audit/selected_development.json;outputs/development/full_search/*/result.json;outputs/development/new_document/{proposal,admission}.json;memory/S3.json;outputs/protocol/freeze.json;outputs/evaluation/manifest.json;outputs/evaluation/trials/*/*/result.json;analysis/{RESULTS.md,trials.csv,aggregate.csv,token_usage.json};replay/{index,audit}.json. Missing files mean pending,not completed work.

No new PPT until user reviews results. Physically grounded backtracking must be evidenced by actual restore events and undone accepted removals. A failed uncommitted query alone is not backtracking. Candidate read/application declarations do not prove benefit. The final no-library comparison B−A includes review overhead;C−B changes an architecture bundle. Restricted local MuJoCo paths are not original ASAP certificates or robot execution.

Use the existing Python environment with PYTHONDONTWRITEBYTECODE=1. Supervisor: python -B -m disassembly_final_v4.pipeline. OS lock and heartbeat guard duplicate supervisors. Preserve already-started jobs and all negative outcomes. GitHub mirror contains a portable code snapshot;local raw CAD/large logs are not uploaded automatically. Read repository README and docs/STATUS.md for collaboration.

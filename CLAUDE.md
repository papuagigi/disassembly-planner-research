# Claude Code entry

Latest recorded evaluation: `disassembly_repair_v7_4/` (unchanged v7.3 planner, 12 new 5–7-part CADs, three repeats per condition; 180/180 goal-reached episodes). Read [its STATUS](disassembly_repair_v7_4/STATUS.md), [PLAN](disassembly_repair_v7_4/PLAN.md), [publication notes](results/repair_v7_4/README.md), and `results/repair_v7_4/EVALUATION_RESULTS.md` first. Independent replay verification of all 180 episodes ran on 2026-11-18 at the user's instruction: 180/180 PASS, 2,081 physical checks equal to the stored charged checks (`results/repair_v7_4/records/replay_audit/evaluation.json`). Replays re-execute recorded API events and do not regenerate LLM responses. Do not start experiments or replays without the user. The 2026-11-10 and 2026-11-18 publications only check and export existing records.

Submitted study: `disassembly_repair_v7_3/` (decision-identical engine speedup, recoverable re-asks, note-first contract, S5 SKILL.md with a model-free rule gate, frozen evaluation on 4 new CADs). Read [its STATUS](disassembly_repair_v7_3/STATUS.md) and `results/repair_v7_3/EVALUATION_RESULTS.md` for the independently replay-verified submitted results.

Previous: `disassembly_repair_v7_2/` (v7.2 engine hardening, development learning cycle, frozen validation and same-assembly retry); `results/repair_v7_2/RETRY_RESULTS.md`.

Previous work: `disassembly_repair_v7/` (user-assigned repair of v6 search bookkeeping/scheduling plus a physics feasibility control). Read [STATUS](disassembly_repair_v7/STATUS.md) and [CHANGELOG](disassembly_repair_v7/CHANGELOG.md), then `claude_repair_handoff/`.

`disassembly_final_v6` is COMPLETE and frozen; never restart or edit it. Its CADs (05954, 06444, 03114) are development/regression cases only. Keep A (generated code, no documents), B (generated code + S3 SKILL.md), C (conditional graph + LLM priorities + fixed DFS + the same S3 documents); evaluated model gpt-6-luna/low; v6 limits. The v7.1 pilot uses physics P2 (pre-registered in results/repair_v7/PHYSICS_DECISION.md). Never rerun a started episode; do not iterate until a favored arm wins. No PPT until user review.

This public snapshot omits raw CAD, native environments and provider logs; exact runs need the original workspace.

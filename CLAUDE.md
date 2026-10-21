# Claude Code entry

Latest completed work: `disassembly_repair_v7_3/` (decision-identical engine speedup, recoverable re-asks, note-first contract, S5 SKILL.md with a model-free rule gate, frozen evaluation on 4 new CADs). Read [its STATUS](disassembly_repair_v7_3/STATUS.md) and `results/repair_v7_3/EVALUATION_RESULTS.md` first. Do not start another experiment without the user.

Previous: `disassembly_repair_v7_2/` (v7.2 engine hardening, development learning cycle, frozen validation and same-assembly retry); `results/repair_v7_2/RETRY_RESULTS.md`.

Previous work: `disassembly_repair_v7/` (user-assigned repair of v6 search bookkeeping/scheduling plus a physics feasibility control). Read [STATUS](disassembly_repair_v7/STATUS.md) and [CHANGELOG](disassembly_repair_v7/CHANGELOG.md), then `claude_repair_handoff/`.

`disassembly_final_v6` is COMPLETE and frozen; never restart or edit it. Its CADs (05954, 06444, 03114) are development/regression cases only. Keep A (generated code, no documents), B (generated code + S3 SKILL.md), C (conditional graph + LLM priorities + fixed DFS + the same S3 documents); evaluated model gpt-6-luna/low; v6 limits. The v7.1 pilot uses physics P2 (pre-registered in results/repair_v7/PHYSICS_DECISION.md). Never rerun a started episode; do not iterate until a favored arm wins. No PPT until user review.

This public snapshot omits raw CAD, native environments and provider logs; exact runs need the original workspace.

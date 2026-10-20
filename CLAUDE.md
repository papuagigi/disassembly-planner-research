# Claude Code repair entry

Read [the current task](claude_repair_handoff/TASK_PROMPT.md), [handoff](claude_repair_handoff/README.md), [failure diagnosis](claude_repair_handoff/FAILURE_DIAGNOSIS.md), and `claude_repair_handoff/evidence.json` first. The user is preparing to assign a new problem-solving task; this file itself does not start Claude or another agent.

The v6 three-CAD/nine-episode experiment is COMPLETE. Preserve it as the baseline. Do not restart its supervisor or change its frozen code, dependencies, documents or scores. User-authorized fixes belong in a separate version; suggested disassembly_repair_v7 is not implemented yet. The old docs/CLAUDE_CONTINUATION_PROMPT.md and recovery stop rules describe the completed experiment, not this new repair task. Now-known v6 CADs are development/regression cases in the next version, never fresh first encounters.

Keep arm identities, equal model/API/budget conditions and a common B/C SKILL.md bank. Claude is the coding coordinator; the evaluated model remains gpt-6-luna/low unless a separately authorized, matched protocol changes it. Verify physical feasibility and search defects separately. Do not force B/C to win. No PPT yet.

The public snapshot omits full native environments, raw source CAD and provider episodes. Read the handoff's public/local path mapping. Use the original workspace to inspect those raw files; do not imply that a fresh clone contains them. Portable replay is separate from running native physics or the planner.

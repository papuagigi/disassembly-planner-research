# Completed v6 recovery instructions

**2026-10-20 follow-up:** v6 is COMPLETE. The user is preparing a separate Claude Code repair assignment. Read [the new handoff](../claude_repair_handoff/README.md) and [the new task prompt](../claude_repair_handoff/TASK_PROMPT.md) for that task. The instructions below preserve the v6 recovery contract. Their stop/no-retuning rules protect this completed study; they do not prohibit user-authorized repairs in a new version. This file does not launch Claude or restart a supervisor. The dated "not assigned" labels below describe the earlier contingency arrangement.

Claude is not currently assigned. These instructions activate only when the user explicitly asks Claude Code to continue. A later direct user continuation request overrides an older `Claude_assigned=false` status snapshot. Do not launch or message another agent yourself.

## Local project and current scope

Use the existing local workspace containing `disassembly_final_v6/` and `disassembly_learning_v1/.venv/`. The public GitHub repository is a source/report/demo snapshot; it omits native environments, raw CAD archives, full local assets and provider logs. A fresh clone alone cannot resume these exact episodes.

First read `AGENT_HANDOFF.md`, `OPERATIONS.md`, `TIME_BUDGET.md`, `analysis/VALIDATION_AND_FREEZE.md`, `analysis/INPUT_COHORT_EXHAUSTION.md`, and the latest JSON state. Read current evidence rather than assuming this snapshot is still current.

Current final scope: **three CADs, nine first episodes**, explicitly confirmed by the user in `outputs/protocol/cohort_amendment_confirmation.json`. CADs: `asap_05954` (13parts/12removals), `asap_06444` (21/20), `asap_03114` (22/21). All75fixed test candidates were processed;only three passed unchanged input criteria. The original four-CAD registration remains preserved and unmet. Read `outputs/protocol/cohort_amendment.json`;do not silently claim four were evaluated.

Extra learning is complete: eight inherited1GiBepisodes plus two additional4GiBepisodes on05459/01613,ten episodes on eight unique long training CADs. Prior90local-probe inputs are not90complete disassemblies;unique current-line development count94. Independent validation is complete on three CADs. The one new `physical-clearance-chain` candidate was rejected because of native arena/contact warnings. B/C retain the same two earlier procedural documents;the admitted bodies did not improve in this extra cycle. No retraining or new skill proposal is needed.

## Determine whether anything needs recovery

Inspect `outputs/pipeline_state.json`, `outputs/heartbeat.json`, `outputs/progress.json`, `outputs/supervisor_resume_3cad.json`, actual live process commands, and `outputs/evaluation/trials/*/*/result.json` before starting any process. At handoff creation the active supervisor was PID51259/session98488, log `outputs/pipeline_resumed_3cad.log`;this is a dated pointer,not proof of liveness. Old supervisor41025ended after input reserve exhaustion. Never restartv5/v4 or the completed early-training helpers.

- If the existing supervisor or a planner worker is alive, monitor it. Do not duplicate it or run physical replay/capture alongside a timed planner.
- If status is COMPLETE, verify deliverables and report;do not run another experiment.
- If the supervisor is dead or has a recorded error, preserve the state/log/error,check worker PIDs and `outputs/pipeline.lock`,then resume only unfinished orchestration after diagnosing the error.
- A started first episode is immutable. `driver.run` reuses completed results and finalizes an interrupted started job without rerunning it. Never delete job/result/progress files to force a fresh attempt. Never manually fabricate a success,query result or token total.

Normal supervisor entry point,from the parent workspace,only after liveness checks:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 disassembly_learning_v1/.venv/bin/python -B -m disassembly_final_v6.pipeline
```

Cached learning/validation/manifest records are reused. Save a distinct resume log/receipt. Do not call `post_resume_input_cohort` again;it already created the amendment and bound manifest.

## Frozen experiment

- A: LLM-generated restricted Python,no procedural document library.
- B: same code actor,readable frozen SKILL.md library.
- C: conditional directed graph,LLM priorities,fixed DFS,same frozen library.
- Model remains **gpt-6-luna / low via the existing CodexCLIProvider**. Claude is the coordinating coding agent,not a replacement evaluation model. Do not substitute Claude when Codex inference is unavailable. Preserve provider errors/unknown usage;keep unstarted jobs unstarted if same-model access cannot continue.
- Each final arm: **4GiB peak-RSS guard,8logical CLI turns,240physical queries,900seconds,10M instructions,128checkpoints,256restores,512000prompt bytes,64000response bytes**. Reading documents is charged. Exactly one planner at a time.
- B/C use identical S3 document/reference bytes and the same physical/checkpoint/restore API as A. No weight update,no learning from final CAD failures,no new candidate,no favored winner. No final episode retry.
- `outputs/protocol/freeze.json` and its listed source/bank/physics hashes remain unchanged. Sample-count amendment affects orchestration/reporting only. Previous postprocessor sources are preserved under `outputs/recovery/cohort_exhaustion/post_sources_before_amendment/`.

The4GiBactor guard,MuJoCo's internal arena/contact workspace,provider failures,physics rejection and time/query exhaustion are different mechanisms. Preserve raw outcomes;native warnings invalidate stronger physical claims. An unfinished charged query has unknown output;`PASS_VERIFIED_PREFIX` verifies only completed events. Virtual restoration is search rollback,not physical reassembly.

## Finish the bounded pass

Complete remaining first episodes,aggregate actual outcomes/tokens,independently replay every episode including failures,make the portable replay bundle,and publish safe source/agentMD/results/demo using `collaboration_tools/publish_snapshot.py`. Do not push credentials,raw CLI logs,archives,venv or unrelated user files. No force push. Repository: https://github.com/papuagigi/disassembly-planner-research .

Required evidence:

- `outputs/evaluation/complete.json`: nine preserved first episodes.
- `analysis/{results.json,trials.csv,aggregate.csv,token_usage.json,matched_conditions_audit.json,serial_execution_audit.json}`: actual usage,unknowns and conditions. Expected new planner windows:2development+3validation+9test=14,not17.
- `replay/{index,audit}.json`: all nine actual event replays,including unfinished-prefix qualifications where applicable.
- `analysis/{source_hash_audit.json,public_replay_bundle.json,RESULTS.md}` and actual GitHub push receipt.
- `outputs/pipeline_complete.json`: only after all required work is complete. Do not use the existence of a replay page alone as proof of completion.

Local replay server uses port8785. Development preview is `/viewer/development.html`;final results use `/viewer/index.html` after actual export. Verify the existing server before launching another. Replay shows native MuJoCo-calculated states through a Three.js viewer;it is not live browser physics. Reference paths are post-score revalidations,not unique optimal answers.

Preserve every earlier study/result/PPT. Do **not** make a new PPT or human report. Agent MD/JSON/CSV and a concise Korean final explanation are sufficient. Explain actual results and limitations without requiring B/C to win. Stop improvement loops after this final pass. Target2026-10-20 13:40:49KST is a goal,not a verified ETA.

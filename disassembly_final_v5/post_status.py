"""Small truthful handoff snapshots for humans and other agents."""
from .common import ROOT,WORKSPACE,read,write,utc
from .scope import study_scope

def optional(path,default=None):
    p=ROOT/path
    return read(p) if p.exists() else default

def main():
    scope=study_scope()
    state=optional('outputs/pipeline_state.json',{})
    selected=optional('outputs/input_audit/selected_development.json',{})
    discovery=list((ROOT/'outputs/development/full_search').glob('*/result.json'))
    validation=list((ROOT/'outputs/development/full_validation').glob('*/result.json'))
    scored=list((ROOT/'outputs/evaluation/trials').glob('*/*/result.json'))
    completed_discovery=[]
    for p in sorted(discovery):
        result=read(p)
        health=optional(str(p.parent.relative_to(ROOT)/'engine_health.json'),{})
        completed_discovery.append(dict(case_id=result['case_id'],raw_goal_reached=bool(result['success']),
            completed_removals=result.get('completed_removals'),required_removals=result.get('required_removals'),
            checks=result.get('checker_calls'),llm_calls=result.get('llm_calls'),seconds=result.get('elapsed_seconds'),
            native_engine_health=health.get('status','NOT_YET_AUDITED'),
            replay_status=optional(str(p.parent.relative_to(ROOT)/'physical_audit.json'),{}).get('status','PENDING')))
    value=dict(utc=utc(),state=state,selected_discovery=len(selected.get('discovery_cases',[])),
        live_progress=optional('outputs/progress.json',{}),
        early_discovery=optional('outputs/early_discovery_state.json'),
        completed_discovery_outcomes=completed_discovery,
        selected_validation=len(selected.get('validation_cases',[])),completed_full_discovery=len(discovery),
        completed_independent_validation=len(validation),completed_first_test_episodes=len(scored),
        targets=dict(full_discovery=scope['full_discovery_CADs'],validation=scope['validation_CADs'],test_CADs=scope['evaluation_CADs'],test_episodes=3*scope['evaluation_CADs']),
        prospective_scope=scope,
        prior_local_probe_discovery=90,new_development=optional('outputs/development/complete.json'),
        model='gpt-6-luna',reasoning_effort='low',wall_seconds=900,no_PPT_created=True,Claude_assigned=False)
    write(ROOT/'outputs/status_snapshot.json',value)
    text=f'''# Final v5 agent handoff

Snapshot UTC: {value['utc']}. Verify live processes and outputs before recovery.

Goal: measure whether development-failure-derived SKILL.md improves first-episode disassembly on unseen CADs. No desired winner. No model-weight training.

Controlling plan: PLAN.md. Exactly one final learning → independent validation → freeze → first-test cycle. Never tune against final tests. Do not rerun started episodes. Existing studies and presentations remain preserved. Claude is not assigned; this document supports recovery only.

State: {state}

Actual full-search discovery evidence: {len(discovery)}/{scope['full_discovery_CADs']} (five imported byte-exact v4episodes plus three newly authorized long training episodes). New independent validation: {len(validation)}/{scope['validation_CADs']}. First test episodes: {len(scored)}/{3*scope['evaluation_CADs']} on{scope['evaluation_CADs']}new official test CADs. Retain90prior local-probe discovery CADs,not90full solutions. After this extension,the target unique discovery corpus is94(90+one v4new CAD+three v5new CADs). Old validation CADs07375/04243/04060and their feedback are excluded from the new proposal and retired from v5validation;three fresh validation CADs are used. All new learning/validation inputs have11–20parts. Final test needs10+removals and uses the same predeclared size-priority source reserve. User approved three additional training CADs;target deadline is2026-10-20 13:40:49KST,total16hours from the original request. Read PLAN.md,config/study_scope.json and protocol/training_extension_amendment.json. This is a target,not a runtime guarantee;missing results remain pending.

Current input-only preparation: {value['live_progress']}. Fixed-order selection is not complete until selected_development.json exists;selected_discovery=0 above does not mean no reused episode has started. Completed development episodes: {completed_discovery}. Do not treat these as held-out A/B/C comparison outcomes.

Native engine health clarification:07722 emitted contact/constraint arena overflow. A deterministic replay may reproduce invalid resource-limited contact handling. Keep raw outcomes/costs;new skill evidence excludes warning-bearing episodes. Candidate validation warnings veto admission. Final analysis separately reports raw and warning-free goal attainment,retaining every CAD in the denominator. Missing logs are unknown. Do not alter physics or rerun episodes to remove warnings.

A=generated code/no docs;B=same generated code/frozen S3;C=conditional graph+LLM order+fixed DFS/same S3. Final A/B/C: same API,initial state,gpt-6-luna/low,8logical model turns,240physical queries,900seconds. Three added development episodes use600queries/900seconds to collect deeper training experience;five inherited episodes retain their actual240query caps. Do not present these mixed development budgets as a controlled score improvement. Document review is charged. A's failure-free memory resets between products;within-episode feedback is allowed for all.

Evidence: outputs/input_audit/selected_development.json;outputs/development/full_search/*/result.json;outputs/development/new_document/{{proposal,admission}}.json;memory/S3.json;outputs/protocol/freeze.json;outputs/evaluation/manifest.json;outputs/evaluation/trials/*/*/result.json;analysis/{{RESULTS.md,trials.csv,aggregate.csv,token_usage.json}};replay/{{index,audit}}.json. Missing files mean pending,not completed work.

No new PPT until user reviews results. Physically grounded backtracking must be evidenced by actual restore events and undone accepted removals. A failed uncommitted query alone is not backtracking. Candidate read/application declarations do not prove benefit. The final no-library comparison B−A includes review overhead;C−B changes an architecture bundle. Restricted local MuJoCo paths are not original ASAP certificates or robot execution.

Use the existing Python environment with PYTHONDONTWRITEBYTECODE=1. Supervisor: python -B -m disassembly_final_v5.pipeline. OS lock and heartbeat guard duplicate supervisors. Preserve already-started jobs and all negative outcomes. GitHub mirror contains a portable code snapshot;local raw CAD/large logs are not uploaded automatically. Read repository README,docs/status.json and docs/AGENT_HANDOFF.md for collaboration.
'''
    (ROOT/'AGENT_HANDOFF.md').write_text(text)
    (ROOT/'CLAUDE.md').write_text('# Recovery instructions only\n\nClaude is not assigned. Read PLAN.md and AGENT_HANDOFF.md. Never rerun started episodes or edit frozen actor/bank/physics files. No test-data learning or PPT before result review.\n')
    return value

def checkpoint():
    """Publish only between completed episodes, outside every scored wall cap."""
    main()
    script=WORKSPACE/'collaboration_tools/publish_snapshot.py'
    if script.exists():
        import subprocess,sys
        p=subprocess.run([sys.executable,'-B',str(script)],capture_output=True,text=True)
        write(ROOT/'outputs/github_publish_latest.json',dict(utc=utc(),returncode=p.returncode,stdout=p.stdout[-1000:],stderr=p.stderr[-1000:]))

if __name__=='__main__':main()

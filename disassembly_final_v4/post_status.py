"""Small truthful handoff snapshots for humans and other agents."""
from .common import ROOT,read,write,utc

def optional(path,default=None):
    p=ROOT/path
    return read(p) if p.exists() else default

def main():
    state=optional('outputs/pipeline_state.json',{})
    selected=optional('outputs/input_audit/selected_development.json',{})
    discovery=list((ROOT/'outputs/development/full_search').glob('*/result.json'))
    validation=list((ROOT/'outputs/development/full_validation').glob('*/result.json'))
    scored=list((ROOT/'outputs/evaluation/trials').glob('*/*/result.json'))
    value=dict(utc=utc(),state=state,selected_discovery=len(selected.get('discovery_cases',[])),
        selected_validation=len(selected.get('validation_cases',[])),completed_full_discovery=len(discovery),
        completed_independent_validation=len(validation),completed_first_test_episodes=len(scored),
        targets=dict(full_discovery=10,validation=10,test_CADs=10,test_episodes=30),
        prior_local_probe_discovery=90,new_development=optional('outputs/development/complete.json'),
        model='gpt-6-luna',reasoning_effort='low',wall_seconds=900,no_PPT_created=True,Claude_assigned=False)
    write(ROOT/'outputs/status_snapshot.json',value)
    text=f'''# Final v4 agent handoff

Snapshot UTC: {value['utc']}. Verify live processes and outputs before recovery.

Goal: measure whether development-failure-derived SKILL.md improves first-episode disassembly on unseen CADs. No desired winner. No model-weight training.

Controlling plan: PLAN.md. Exactly one final learning → independent validation → freeze → first-test cycle. Never tune against final tests. Do not rerun started episodes. Existing studies and presentations remain preserved. Claude is not assigned; this document supports recovery only.

State: {state}

Actual finished full-search discovery: {len(discovery)}/10. Independent full-search validation: {len(validation)}/10. First test episodes: {len(scored)}/30 across a target of10CADs. Earlier90CAD discovery means local physical probes,not90completed disassemblies. Four development CADs are reused for additional full-search experience,six are new;unique discovery after completion=96. Validation is10different newly qualified training CADs. All new full-search/validation/test inputs have11–20parts.

A=generated code/no docs;B=same generated code/frozen S3;C=conditional graph+LLM order+fixed DFS/same S3. Same API,initial state,gpt-6-luna/low,8logical model turns,240physical queries,900seconds. Document review is charged. A's failure-free memory resets between products;within-episode feedback is allowed for all.

Evidence: outputs/input_audit/selected_development.json;outputs/development/full_search/*/result.json;outputs/development/new_document/{{proposal,admission}}.json;memory/S3.json;outputs/protocol/freeze.json;outputs/evaluation/manifest.json;outputs/evaluation/trials/*/*/result.json;analysis/{{RESULTS.md,trials.csv,aggregate.csv,token_usage.json}};replay/{{index,audit}}.json. Missing files mean pending,not completed work.

No new PPT until user reviews results. Physically grounded backtracking must be evidenced by actual restore events and undone accepted removals. A failed uncommitted query alone is not backtracking. Candidate read/application declarations do not prove benefit. The final no-library comparison B−A includes review overhead;C−B changes an architecture bundle. Restricted local MuJoCo paths are not original ASAP certificates or robot execution.

Use the existing Python environment with PYTHONDONTWRITEBYTECODE=1. Supervisor: python -B -m disassembly_final_v4.pipeline. OS lock and heartbeat guard duplicate supervisors. Preserve already-started jobs and all negative outcomes. GitHub mirror contains a portable code snapshot;local raw CAD/large logs are not uploaded automatically. Read repository README and docs/STATUS.md for collaboration.
'''
    (ROOT/'AGENT_HANDOFF.md').write_text(text)
    (ROOT/'CLAUDE.md').write_text('# Recovery instructions only\n\nClaude is not assigned. Read PLAN.md and AGENT_HANDOFF.md. Never rerun started episodes or edit frozen actor/bank/physics files. No test-data learning or PPT before result review.\n')
    return value

if __name__=='__main__':main()

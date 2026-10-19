"""Truthful agent-oriented snapshots;never substitute a plan for a result."""
from .common import ROOT,WORKSPACE,read,write,utc
from .scope import study_scope


def optional(name,default=None):
    p=ROOT/name
    return read(p) if p.exists() else default


def main():
    scope=study_scope();state=optional('outputs/pipeline_state.json',{})
    selected=optional('outputs/input_audit/selected_development.json',{})
    paths=list((ROOT/'outputs/development/full_search').glob('*/result.json'))
    extra=list((ROOT/'outputs/development/memory_extension').glob('*/result.json'))
    rows=[]
    for p in sorted(paths+extra):
        r=read(p);h=p.parent/'engine_health.json'
        rows.append(dict(case_id=r['case_id'],source='4GiBadditional' if p in extra else 'inherited1GiB',
            success=bool(r['success']),removed=r.get('completed_removals'),required=r.get('required_removals'),
            checks=r.get('checker_calls'),calls=r.get('llm_calls'),seconds=r.get('elapsed_seconds'),
            limits=r['limits'],error=r.get('error'),peak_rss_bytes=r.get('max_rss_bytes_observed'),
            native_health=read(h)['status'] if h.exists() else 'PENDING',result_path=str(p.relative_to(ROOT))))
    validation=list((ROOT/'outputs/development/full_validation').glob('*/result.json'))
    final=list((ROOT/'outputs/evaluation/trials').glob('*/*/result.json'))
    value=dict(utc=utc(),study='disassembly_final_v6',state=state,scope=scope,
        input_progress=optional('outputs/progress.json',{}),
        memory_extension_state=optional('outputs/memory_extension_state.json'),
        inherited_full_search_episodes=len(paths),completed_additional4GiBepisodes=len(extra),
        unique_long_training_CADs=len({r['case_id'] for r in rows}),long_training_episode_outcomes=rows,
        selected_validation=len(selected.get('validation_cases',[])),completed_validation=len(validation),
        completed_first_test_episodes=len(final),targets=dict(unique_long_training_CADs=8,total_long_training_episodes=10,
            additional4GiBepisodes=2,validation_CADs=3,new_test_CADs=4,first_test_episodes=12),
        model='gpt-6-luna',reasoning_effort='low',peak_RSS_cap_GiB=4,planner_concurrency=1,
        prior_local_probe_CADs=90,current_line_unique_development_CADs=94,
        no_model_weight_update=True,Claude_assigned=False,PPT_created=False,
        skill_admission=optional('outputs/development/new_document/admission.json'),
        freeze_exists=(ROOT/'outputs/protocol/freeze.json').exists())
    write(ROOT/'outputs/status_snapshot.json',value)
    (ROOT/'AGENT_HANDOFF.md').write_text(f'''# Common4GiB recovery handoff

UTC:{value['utc']}. Read PLAN.md,OPERATIONS.md,TIME_BUDGET.md first. Claude is not assigned. Verify live PID/heartbeat before recovery.

Current state:{state}

Preserved1GiBepisodes:{len(paths)}/8. Additional4GiBdevelopment episodes:{len(extra)}/2,on05459and01613only. Combined10episodes are8unique long CADs;current-line unique development corpus94includes90local-probe inputs,not94complete solutions. Independent validation:{len(validation)}/3. New final first episodes:{len(final)}/12,on4unseen official test products. Missing outputs are pending.

Current input/episode progress:{value['input_progress']}

Optional early_memory_extension and main collection share outputs/development/discovery_collection.lock. They must never run planners concurrently. Main reuses saved additional results. No oldv5/v4supervisor should be restarted. Their complete results/sources are hash-protected. New4GiBepisodes have distinct outputs/development/memory_extension folders;never overwrite with retry.

A=LLMcode,no documents;B=same code,frozenS3;C=conditionalGraph+LLMorder+fixedDFS,sameS3. New validation/final:gpt-6-luna/low,8logical CLIturns,240physical queries,900s,4GiBpeakRSS,10Msteps,128checkpoints,256restores. Additional training alone retains600checks/900s/8turnswith4GiB. Imported training budgets stay exactly as originally executed. Reading documents costs calls/time. PeakRSSguard is not an OS-enforced cap. Resource failures and native warnings are not physical failures to learn.

One new failure-derivedSKILL.mdproposal only. Completed verified warning-free physical rejection may supply evidence;accepted-only/resource-only stops cannot.3freshvalidationCADs use the existing2/3functional admission threshold and safety/native/replay vetoes. Rejecting the new candidate keepsS2. Freeze actor,bank,physics,APIandreserves before final test geometry. Do not learn from or rerun final first episodes. Report all failures and unknown token usage. Do not requireB/Cto win.

Evidence:outputs/development/{{discovery_complete.json,new_document/admission.json,complete.json}};memory/S3.json;outputs/protocol/freeze.json;outputs/evaluation/{{manifest,complete}}.json;analysis/{{RESULTS.md,trials.csv,aggregate.csv,token_usage.json,matched_conditions_audit.json}};replay/{{index,audit}}.json. Missing files are pending. Verify actual versus planned counts. Development repeats are not independent product samples. Physics is restricted localMuJoCo,not originalASAPorrobotexecution. Replays use actual recorded events;post-score references are not unique optimal answers.

Target2026-10-20 13:40:49KST,not guaranteed. Finish this bounded pass regardless of winner. Publish safe source/agentMD/results/portable replay bundle toGitHub. No credentials/rawCLIlogs/CADarchives/venv/PPT. No PPT before user review.
''')
    return value


def checkpoint():
    main()
    import subprocess,sys
    script=WORKSPACE/'collaboration_tools/publish_snapshot.py'
    if script.exists():
        p=subprocess.run([sys.executable,'-B',str(script)],capture_output=True,text=True)
        write(ROOT/'outputs/github_publish_latest.json',dict(utc=utc(),returncode=p.returncode,stdout=p.stdout[-1000:],stderr=p.stderr[-1000:]))


if __name__=='__main__':main()

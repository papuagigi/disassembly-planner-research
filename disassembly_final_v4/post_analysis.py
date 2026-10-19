"""All outcomes, token accounting, document context and behavioral proxies."""
from __future__ import annotations
import csv
from collections import Counter,defaultdict
import json
import math
from pathlib import Path
import statistics as st
from .common import ROOT,read,write,sha,utc,progress
from .metrics import summarize
from .documents import DocumentBank
from .native_health import audit as audit_native_health

def csv_write(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for row in rows for k in row))
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for row in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})

def tokens():
    rows=[]
    for p in sorted((ROOT/'outputs').glob('**/metadata.json')):
        m=read(p)
        if m.get('provider')!='codex_cli_live':continue
        parts=p.relative_to(ROOT/'outputs').parts
        phase='evaluation' if parts[0]=='evaluation' else 'development'
        arm=parts[3] if phase=='evaluation' else None
        case=parts[2] if phase=='evaluation' else None
        u=m.get('usage',{});known=all(isinstance(u.get(k),(int,float)) for k in ['input_tokens','output_tokens'])
        rows.append(dict(phase=phase,case_id=case,arm=arm,metadata_path=str(p.relative_to(ROOT)),
            requested_model=m.get('requested_model'),effort=m.get('requested_reasoning_effort'),
            input_tokens=u.get('input_tokens'),output_tokens=u.get('output_tokens'),cached_input_tokens=u.get('cached_input_tokens'),
            reasoning_output_tokens=u.get('reasoning_output_tokens'),total_tokens=u['input_tokens']+u['output_tokens'] if known else None,
            uncached_input_tokens=u['input_tokens']-u['cached_input_tokens'] if known and isinstance(u.get('cached_input_tokens'),(int,float)) else None,
            usage_known=known,provider_seconds=m.get('elapsed_seconds'),provider_error=m.get('error'),tool_activity_count=m.get('tool_activity_count',0)))
    for p in sorted((ROOT/'outputs').glob('**/call_*/prompt.txt')):
        if (p.parent/'metadata.json').exists():continue
        parts=p.relative_to(ROOT/'outputs').parts;phase='evaluation' if parts[0]=='evaluation' else 'development'
        rows.append(dict(phase=phase,case_id=parts[2] if phase=='evaluation' else None,arm=parts[3] if phase=='evaluation' else None,
            metadata_path=str(p.parent.relative_to(ROOT)),requested_model='gpt-6-luna',effort='low',input_tokens=None,output_tokens=None,
            cached_input_tokens=None,reasoning_output_tokens=None,total_tokens=None,uncached_input_tokens=None,usage_known=False,
            provider_seconds=None,provider_error='Started call without finalized provider metadata;usage unknown',tool_activity_count=None))
    groups={}
    for key,subset in [('all',rows),('development',[r for r in rows if r['phase']=='development']),('evaluation',[r for r in rows if r['phase']=='evaluation'])]:
        groups[key]=dict(calls=len(subset),unknown_usage_calls=sum(not r['usage_known'] for r in subset),
            unknown_cached_input_calls=sum(r['cached_input_tokens'] is None for r in subset),
            unknown_reasoning_output_calls=sum(r['reasoning_output_tokens'] is None for r in subset),
            unknown_uncached_input_calls=sum(r['uncached_input_tokens'] is None for r in subset),
            **{k:sum(r[k] or 0 for r in subset) for k in ['input_tokens','output_tokens','cached_input_tokens','reasoning_output_tokens','total_tokens','uncached_input_tokens','provider_seconds']})
    csv_write(ROOT/'analysis/token_calls.csv',rows)
    write(ROOT/'analysis/token_usage.json',dict(created_utc=utc(),groups=groups,calls=rows,
        accounting='Provider-reported CLI turn totals,including CLI context;not a local prompt-token estimate. total=input+output;cached input and reasoning are subsets and are not added twice. Unknown usage is not zero. Includes provider-rejected calls. No dollar estimates.',
        model_call_unit='One CodexCLIProvider.complete invocation/CLI planner turn. Internal HTTP inference-request count is not exposed;tool activity invalidates a response.'))
    return rows,groups

def context_audit(result,folder):
    bank=DocumentBank(ROOT/'memory'/('S0.json' if result['condition']=='A' else 'S3.json'))
    rows=[]
    for d in result.get('decisions',[]):
        p=folder/'llm_calls'/('call_%02d'%d['call'])/'prompt.txt'
        if not p.exists():continue
        text=p.read_text();payload=json.loads(text.split('\nPUBLIC INPUT:\n',1)[1])
        loaded=payload['loaded_skill_documents'];references=payload['loaded_skill_validation_references']
        for sid,body in loaded.items():
            assert body==bank.documents[sid],('Document bytes changed/lost',sid)
            if sid in bank.validation_references:assert references[sid]==bank.validation_references[sid]
        assert set(d.get('claimed_application_ids',[]))<=set(loaded)
        rows.append(dict(call=d['call'],prompt_bytes=len(text.encode()),loaded=list(loaded),
            declared=d.get('claimed_application_ids',[]),document_plan=d.get('document_plan',[]),exact_bytes=True))
    return dict(case_id=result['case_id'],arm=result['condition'],calls=rows,
        explicit_reads=len(result.get('document_reads',[])),context_verified=True,
        scope='Exact provision and declarations only,not proof of internal attention/compliance/benefit')

def behavior(result):
    trace=result.get('trace',[]);opportunities=[]
    for i,t in enumerate(trace):
        if t.get('valid'):continue
        if t.get('reason')=='unstable_remainder':related=set((t.get('stability') or {}).get('unstable_parts',[]))
        elif t.get('reason')=='path_collision':related=set(t.get('blockers',[]))
        else:continue
        remaining=set(t.get('remaining_before',[]));fixed=set(result.get('fixed_part_ids',[]))
        related=(related&remaining)-fixed
        if not related:continue
        future=trace[i+1:];next_same=next((r for r in future if r.get('physical_state_key_before')==t.get('physical_state_key_before')),None)
        next_commit=next((r for r in future if r.get('committed')),None)
        opportunities.append(dict(check=t['checker_call'],reason=t['reason'],failed_part=t['part_id'],related_remaining_ids=sorted(related),
            next_same_state_part=next_same.get('part_id') if next_same else None,
            directly_tested_related_part_next=bool(next_same and next_same['part_id'] in related),
            next_committed_part=next_commit.get('part_id') if next_commit else None,
            next_commit_removed_related_part=bool(next_commit and next_commit['part_id'] in related)))
    return dict(case_id=result['case_id'],arm=result['condition'],opportunities=opportunities,
        direct_next_related=sum(o['directly_tested_related_part_next'] for o in opportunities),
        opportunities_count=len(opportunities),scope='Observable local proxies,not complete semantic compliance or a causal effect. A related part may itself be blocked.')

def wilson(k,n):
    if not n:return None
    z=1.96;p=k/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-radius),min(1,center+radius)]

def main():
    manifest=read(ROOT/'outputs/evaluation/manifest.json');calls,token_groups=tokens()
    trials=[];contexts=[];behaviors=[];timecuts=[]
    for case in manifest['cases']:
        for arm in ['A','B','C']:
            folder=ROOT/'outputs/evaluation/trials'/case['case_id']/arm;result=read(folder/'result.json');m=summarize(result)
            health=audit_native_health(folder)
            usage=[c for c in calls if c['phase']=='evaluation' and c['case_id']==case['case_id'] and c['arm']==arm]
            execution_errors=[d['execution_error'] for d in result.get('decisions',[]) if d.get('execution_error')]
            row=dict(case_id=case['case_id'],arm=arm,part_count=case['part_count'],**m,
                raw_goal_reached=bool(m['success']),native_engine_health=health['status'],
                native_warning_count=health['warning_count'],
                warning_free_goal_reached=bool(m['success'] and health['warning_free_observed']),
                best_progress=m['best_removed']/max(1,m['required_removed']),
                known_total_tokens=sum(c['total_tokens'] or 0 for c in usage),input_tokens=sum(c['input_tokens'] or 0 for c in usage),
                output_tokens=sum(c['output_tokens'] or 0 for c in usage),cached_input_tokens=sum(c['cached_input_tokens'] or 0 for c in usage),
                unknown_usage_calls=sum(not c['usage_known'] for c in usage),
                generated_code_error_count=len(execution_errors),generated_code_error_types=dict(Counter(e['type'] for e in execution_errors)),
                provider_error_calls=sum(bool(c['provider_error']) for c in usage),final_error=result.get('error'),
                bank_version=result.get('bank_version'),bank_content_sha256=result.get('bank_content_sha256'),
                result_path=str(folder/'result.json'),result_sha256=sha(folder/'result.json'),first_budgeted_episode=True)
            trials.append(row);contexts.append(context_audit(result,folder));behaviors.append(behavior(result))
            for cut in [180,600,900]:
                points=[p for p in result.get('timeline',[]) if p['elapsed_seconds']<=cut]
                point=points[-1] if points else dict(removed=0,checks=0,success=False)
                timecuts.append(dict(case_id=case['case_id'],arm=arm,seconds=cut,
                    success=bool(point['success']),removed=point['removed'],checks=point['checks'],progress=point['removed']/case['required_removals'],
                    interpretation='Observed prefix under one900-second run;not a newly generated policy for each separate time budget'))
    aggregate=[]
    for arm in ['A','B','C']:
        subset=[r for r in trials if r['arm']==arm];successful=[r for r in subset if r['success']]
        def mean(key,rows=subset):return st.mean(r[key] for r in rows) if rows else None
        aggregate.append(dict(arm=arm,n=len(subset),successes=len(successful),success_rate=len(successful)/len(subset) if subset else None,
            warning_free_goal_reached=sum(r['warning_free_goal_reached'] for r in subset),
            native_warning_episodes=sum(r['native_engine_health']=='NATIVE_ENGINE_WARNINGS_RECORDED' for r in subset),
            native_health_unknown_episodes=sum(r['native_engine_health']=='UNKNOWN_MISSING_WORKER_LOG' for r in subset),
            success_rate_wilson95=wilson(len(successful),len(subset)),final_progress_mean=mean('final_progress'),
            best_progress_mean=mean('best_progress'),undone_accepted_removals_mean=mean('undone_accepted_removals'),
            checks_mean=mean('checks'),failed_checks_mean=mean('failed_checks'),restores_mean=mean('restores'),
            duplicate_rejected_queries_mean=mean('duplicate_rejected_queries'),llm_calls_mean=mean('llm_calls'),elapsed_seconds_mean=mean('elapsed_seconds'),
            input_tokens_mean=mean('input_tokens'),output_tokens_mean=mean('output_tokens'),cached_input_tokens_mean=mean('cached_input_tokens'),total_tokens_mean=mean('known_total_tokens'),
            unknown_usage_calls=sum(r['unknown_usage_calls'] for r in subset),total_tokens_sum=sum(r['known_total_tokens'] for r in subset),document_reads=sum(r['document_reads'] for r in subset),
            generated_code_error_count=sum(r['generated_code_error_count'] for r in subset),provider_error_calls=sum(r['provider_error_calls'] for r in subset),
            successful_only_checks_mean=mean('checks',successful),successful_only_tokens_mean=mean('known_total_tokens',successful),
            failures_by_termination=dict(Counter(r['termination'] for r in subset if not r['success']))))
    pairs=[]
    for case in manifest['cases']:
        by={r['arm']:r for r in trials if r['case_id']==case['case_id']}
        for a,b in [('B','A'),('C','A'),('C','B')]:
            x,y=by[a],by[b];pairs.append(dict(case_id=case['case_id'],comparison=a+'-'+b,both_success=x['success'] and y['success'],
                success_delta=int(x['success'])-int(y['success']),progress_delta=x['final_progress']-y['final_progress'],
                checks_delta=x['checks']-y['checks'],tokens_delta=x['known_total_tokens']-y['known_total_tokens'],seconds_delta=x['elapsed_seconds']-y['elapsed_seconds']))
    csv_write(ROOT/'analysis/trials.csv',trials);csv_write(ROOT/'analysis/aggregate.csv',aggregate)
    csv_write(ROOT/'analysis/paired_deltas.csv',pairs);csv_write(ROOT/'analysis/time_budget_prefixes.csv',timecuts)
    write(ROOT/'analysis/memory_context_audit.json',dict(status='PASS',trials=contexts,semantic_application_proven=False))
    write(ROOT/'analysis/behavior_audit.json',dict(trials=behaviors,scope='behavioral evidence proxies only'))
    qualification_path=ROOT/'outputs/input_audit/selected_evaluation.json'
    qualification=read(qualification_path)
    qualification_summary=dict(source_path=str(qualification_path),source_sha256=sha(qualification_path),
        initially_qualified_CADs=len(qualification['cases']),attempted_CADs=qualification['attempted'],
        status_counts=dict(Counter(r['status'] for r in qualification['statuses'])),
        full_geometry_QA_and_exclusions_preserved_in_source=True)
    write(ROOT/'analysis/results.json',dict(created_utc=utc(),trials=trials,aggregate=aggregate,paired=pairs,token_groups=token_groups,
        qualification=qualification_summary,
        development=read(ROOT/'outputs/development/complete.json'),no_test_memory_updates=True))
    lines=['# Large-CAD physical-document first-episode comparison','',
        'All old results/PPT remain preserved. Full-search development and independent validation use11-20part training CADs; final inputs are unseen-to-project official ASAP test CADs with11+components/10+required removals,using the predeclared size-priority reserve. They are anonymous engineering CAD,not verified factory provenance. Model=gpt-6-luna/low;8calls/240checks/900seconds;read costs included. One first episode per new CAD/arm. Initial physics only,no full-path or actor-success selection gate.','',
        '|Arm|Success|Mean final progress|Mean best progress|Mean checks|Mean calls|Mean tokens|Mean seconds|','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in aggregate:
        if not r['n']:lines.append(f"|{r['arm']}|not executed:0 qualified CADs|—|—|—|—|—|—|")
        else:lines.append(f"|{r['arm']}|{r['successes']}/{r['n']}|{r['final_progress_mean']:.3f}|{r['best_progress_mean']:.3f}|{r['checks_mean']:.1f}|{r['llm_calls_mean']:.2f}|{r['total_tokens_mean']:.0f}|{r['elapsed_seconds_mean']:.1f}|")
    lines += ['', '## Evidence boundaries','',
        'Read outputs/development/complete.json and new_document/admission.json for actual new discovery/independent-validation counts and whether the new physical document passed its predeclared gate. S2 retains the previous narrowly admitted physical procedure; rejected new candidates are excluded from B/C. Downloaded CAD counts are not learned CAD counts. Model weights never update. Prior strict whole-actor rejection is preserved;bounded physical-repair admission is not full-planner robustness.',
        'B-A changes frozen document availability plus required initial review. C-B changes graph/DFS/code-generation/call scheduling as a bundle; no isolated graph/DFS effect. No final C0 arm,so C memory efficacy is not identified separately.',
        'Final progress is the accepted state at termination;best progress is the greatest accepted prefix observed during the search. A backtracking planner can have lower final than best progress after undoing a branch. Neither partial-progress metric substitutes for full goal success. Undone accepted removals measure branch-search work,not removal of nonrequired components.',
        'Read body bytes,declaration,observable priority change and improved held-out outcomes are separate. See memory_context_audit.json,behavior_audit.json,raw code/ranks and actual event replays. Token calls include failed-provider usage. Cached input and reasoning are not double-counted. Missing usage is unknown.',
        'LLM calls mean logical CodexCLIProvider.complete invocations/CLI planner turns,not independently observed backend HTTP requests. The CLI runs statelessly in an empty temporary working directory with user configuration,memories and major agent-tool features disabled;any recorded tool activity invalidates the response. Provider token totals include CLI context as well as supplied planner text.',
        'time_budget_prefixes.csv is an observed timeline prefix at180/600/900seconds from one900-second policy,not separate per-budget retraining/reruns. A failed early run is not more efficient than successful full disassembly. Use common-success paired rows for cost-only interpretation.',
        'Native engine health is separate from deterministic event replay. Raw success/costs remain unchanged;warning_free_goal_reached additionally requires no native runtime warning in the actual worker log. Missing logs are unknown. All cases remain in the denominator. Inspect native_warning_episodes before interpreting raw success as physically trustworthy. Solver-contact/constraint overflow is infrastructure failure,not a learned physical disassembly rule.',
        'Qualification exclusions and unresolved-within-budget planner outcomes are distinct. No first-episode outcome may be silently retried or removed. MuJoCo/material/scale/fixed-fixture/straight-path limitations remain. Virtual restore is not physical reassembly. No PPT was modified.']
    (ROOT/'analysis/RESULTS.md').write_text('\n'.join(lines)+'\n')
    progress('analysis_complete',cases=len(manifest['cases']),episodes=len(trials),evaluation_tokens=token_groups['evaluation']['total_tokens'])
    print(json.dumps(aggregate,ensure_ascii=False),flush=True)

if __name__=='__main__':main()

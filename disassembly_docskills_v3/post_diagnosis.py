"""Audit matching conditions and describe observed failure mechanisms only."""
from collections import Counter,defaultdict
from .common import ROOT,read,write,sha,utc
from .documents import DocumentBank
from .contracts import LIMITS,ARMS,MODEL,EFFORT

def input_physics_diagnosis():
    stages={}
    for stage in ['development','evaluation']:
        rows=[]
        for path in sorted((ROOT/'outputs/input_audit').glob('physics_'+stage+'_asap_*.json')):
            report=read(path);trials=report.get('trials',[])
            errors=[t.get('error_tail','') for t in trials if t.get('error_tail')]
            excerpt=''
            if errors:
                lines=errors[0].splitlines()
                excerpt=next((line for line in lines if line.startswith(('ValueError:','RuntimeError:','MemoryError:'))),lines[-1] if lines else '')[:350]
            rows.append(dict(case_id=report['id'],setup_status=report['status'],setup_trials=len(trials),
                trial_status_counts=dict(Counter(t['status'] for t in trials)),
                mesh_volume_compiler_error_observed=any('mesh volume is too small' in e for e in errors),
                first_recorded_worker_error_excerpt=excerpt,source_path=str(path),source_sha256=sha(path)))
        stages[stage]=dict(initialization_report_CADs=len(rows),
            finalized_initialization_receipt_CADs=sum(r['setup_status']!='screening' for r in rows),
            unfinished_or_operator_stopped_receipt_CADs=sum(r['setup_status']=='screening' for r in rows),
            setup_status_counts=dict(Counter(r['setup_status'] for r in rows)),
            CADs_with_observed_small_mesh_compiler_errors=sum(r['mesh_volume_compiler_error_observed'] for r in rows),cases=rows)
    write(ROOT/'analysis/input_physics_diagnosis.json',dict(utc=utc(),stages=stages,
        scope='Input-model initialization,not scored planner failures. Includes unused prefetch and operator-stopped partial inputs;only the bound campaign supplies the evaluation denominator. Repeated pose/fixture trials are not additional CADs. A compiler error does not show that the source product is physically impossible. Frozen geometry/physics and all input exclusions remain unchanged.'))

def main():
    input_physics_diagnosis()
    manifest=read(ROOT/'outputs/evaluation/manifest.json');bank=DocumentBank(ROOT/'memory/S2.json')
    matched=[];outcomes=[];tokens=read(ROOT/'analysis/token_usage.json')['calls']
    for case in manifest['cases']:
        results={a:read(ROOT/'outputs/evaluation/trials'/case['case_id']/a/'result.json') for a in ARMS}
        observations={r.get('initial_observation_sha256') for r in results.values() if r.get('initial_observation_sha256')}
        checks=dict(case_id=case['case_id'],same_case=all(r.get('case_sha256',case['case_sha256'])==case['case_sha256'] for r in results.values()),
            same_recorded_initial_observation=len(observations)==1 if all(r.get('initial_observation_sha256') for r in results.values()) else None,
            shared_input_sha256=case['shared_sha256'],
            same_limits=all(r['limits']==LIMITS for r in results.values()),
            B_C_same_frozen_bank=all(results[a].get('bank_content_sha256',bank.content_sha256)==bank.content_sha256 for a in ['B','C']),
            no_test_learning=all(r.get('learning_updates',0)==0 for r in results.values()),
            within_calls_and_checks=all(r['llm_calls']<=LIMITS['max_calls'] and r['checker_calls']<=LIMITS['max_checks'] for r in results.values()),
            one_episode_per_arm=all(r.get('first_encounter',False) for r in results.values()))
        assert all(checks[k] for k in ['same_case','same_limits','B_C_same_frozen_bank','no_test_learning','within_calls_and_checks','one_episode_per_arm']),checks
        assert checks['same_recorded_initial_observation'] is not False,checks
        matched.append(checks)
        for arm,result in results.items():
            trace=result.get('trace',[]);failures=[t for t in trace if not t.get('valid')]
            causes=Counter(t.get('reason') for t in failures)
            errors=Counter(d['execution_error']['type'] for d in result.get('decisions',[]) if d.get('execution_error'))
            by_state=defaultdict(set)
            for t in failures:
                by_state[(t.get('physical_state_key_before'),t.get('part_id'))].add(t['direction'])
            usage=[r for r in tokens if r['phase']=='evaluation' and r['case_id']==case['case_id'] and r['arm']==arm]
            outcomes.append(dict(case_id=case['case_id'],arm=arm,success=result['success'],termination=result['termination'],
                final_removed=result.get('completed_removals',0),required=case['required_removals'],
                completed_query_results=len(trace),charged_queries=result['checker_calls'],
                final_error=result.get('error'),
                charged_queries_without_finished_trace=result['checker_calls']-len(trace),
                observed_rejection_causes=dict(causes),generated_code_errors=dict(errors),
                provider_errors=sum(bool(r['provider_error']) for r in usage),
                model_seconds=sum(r['provider_seconds'] or 0 for r in usage),
                same_state_part_pairs_with_six_observed_failed_directions=sum(len(ds)==6 for ds in by_state.values()),
                interpretation='Six observed failed directions in one state do not prove global impossibility;rotation,other removals or different physical assumptions may change feasibility.'))
    write(ROOT/'analysis/matched_conditions_audit.json',dict(status='PASS',utc=utc(),cases=matched,
        requested_model=MODEL,requested_reasoning_effort=EFFORT,shared_API=True,
        model_call_unit='Logical CLI planner turns;underlying HTTP request count not exposed',
        actual_served_model_identity='Requested model recorded by CLI metadata;not independently identified beyond provider records'))
    write(ROOT/'analysis/failure_diagnosis.json',dict(utc=utc(),outcomes=outcomes,no_unobserved_cause_claim=True))
    development=read(ROOT/'outputs/input_audit/selected_development.json')
    collected=read(ROOT/'outputs/development/collection_index.json')['cases']
    physical_evidence={}
    for role in ['discovery','validation']:
        rows=[r for r in collected if r['role']==role]
        raw=[read(r['result_path']) for r in rows]
        physical_evidence[role]=dict(CADs=len(rows),
            CADs_with_completed_physical_queries=sum(bool(r['trace']) for r in raw),
            CADs_with_observed_rejections=sum(bool(r['failures']) for r in raw),
            CADs_with_measured_repair_pairs=sum(bool(r['repair_pairs']) for r in raw),
            completed_physical_queries=sum(len(r['trace']) for r in raw),
            charged_physical_queries=sum(r['checker_calls'] for r in raw),
            rejection_reasons=dict(Counter(t['reason'] for r in raw for t in r['failures'])),
            measured_pair_kinds=dict(Counter(t['kind'] for r in raw for t in r['repair_pairs'])),
            collection_errors=[dict(case_id=r['case_id'],error=r['error']) for r in raw if r.get('error')],
            source_results=[dict(case_id=r['case']['case_id'],sha256=r['sha256']) for r in rows])
    write(ROOT/'analysis/development_evidence.json',dict(utc=utc(),roles=physical_evidence,
        admission=read(ROOT/'outputs/development/new_document/admission.json'),
        scope='Generic physical-query collection,not trained-policy scores. Discovery supplies induction evidence;validation repair witnesses are withheld from the verifying model. No model weights update.'))
    write(ROOT/'analysis/cohort_scope.json',dict(utc=utc(),
        discovery_component_count_distribution=dict(Counter(c['part_count'] for c in development['discovery_cases'])),
        validation_component_count_distribution=dict(Counter(c['part_count'] for c in development['validation_cases'])),
        test_component_count_distribution=dict(Counter(c['part_count'] for c in manifest['cases'])),
        development_preparation_status_counts=dict(Counter(r['status'] for r in development['statuses'])),
        evaluation_preparation_status_counts=dict(Counter(r['status'] for r in read(ROOT/'outputs/input_audit/selected_evaluation.json')['statuses'])),
        paired_CADs=True,one_stochastic_model_episode_per_CAD_and_arm=True,model_sampling_seed_not_exposed=True,
        same_resource_ceiling_not_identical_realized_token_spend=True,
        full_disassembly_goal='n-1 removals with one permanent original fixture',
        pre_score_test_count_amendment=read(ROOT/'outputs/protocol/evaluation_cohort_amendment.json') if (ROOT/'outputs/protocol/evaluation_cohort_amendment.json').exists() else None,
        random_sample_of_entire_ASAP=False))
    lines=['# Agent interpretation and observed failure mechanisms','',
        'The question is first-episode performance on new products after prior physical experience.No preferred winner is declared.Model weights never update.',
        '', '|Arm|Unsuccessful episodes|Rejected checks|No-removal episodes|Code errors|Provider errors|','|---|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        rows=[r for r in outcomes if r['arm']==arm]
        lines.append(f"|{arm}|{sum(not r['success'] for r in rows)}|{sum(sum(r['observed_rejection_causes'].values()) for r in rows)}|{sum(r['final_removed']==0 for r in rows)}|{sum(sum(r['generated_code_errors'].values()) for r in rows)}|{sum(r['provider_errors'] for r in rows)}|")
    lines += ['', '## What the logs can establish','',
        '- Inspect per-product rows in failure_diagnosis.json and raw call folders before attributing a loss. Provider failure/no completed physical query,generated-code exception,physical rejection,search exhaustion and a cumulative resource cap are distinct mechanisms.',
        '- A library read and declared document_plan establish supplied bytes and model declarations. The trace and observable behavioral proxies are additional evidence. B-A is document availability plus guided-review cost;it cannot isolate one individual document if S2 contains multiple skills. C-B is an architecture bundle. No C-without-memory held-out arm is present.',
        '- A full-disassembly task requires all n-1movable parts. Therefore accepted removals later undone measure wasted branch work;they are not proof that an otherwise nonrequired component was removed. Virtual restoration is not physical reassembly.',
        '- Initial physics validity does not establish a full path under six fixed-orientation straight source-axis actions. A fixed original fixture does not fall under gravity. Every other remaining body is simulated;there is no dynamic gripper/holding/unscrewing/rotation planner. If many directions are physically rejected,the current action/fixture/material model is a candidate limitation,not automatically a weak LLM or a bad skill.',
        '- Case selection is a deterministic source-complexity/input-feasibility sample.No full-path or actor-success selection was used. Wilson intervals in aggregate.csv describe finite binomial uncertainty and do not turn this convenience sample into a representative estimate for all ASAP/factory products.',
        '- The operational test target was amended from15maximum to12fixed CADs for input-preparation cost,before any scored job or test model call. The user required at least10. The source order and first-qualified prefix,model,bank,actor bytes,physics,API and episode caps were unchanged. Read outputs/protocol/evaluation_cohort_amendment.json;do not confuse this source-count amendment with stopping after observing a winner.',
        '- Each CAD/arm has one model episode;the provider exposes no fixed sampling seed here. Resource ceilings match;actual input/output tokens,calls and time can differ. The comparison is ceiling-matched,not equal realized token spending. See cohort_scope.json for development/test size distributions and the possible complexity shift.',
        '- Report development preparation yield,failure-source CAD count,independent admission outcomes and held-out comparison separately. A rejected new document stays rejected even if another condition happens to score better. Token totals include unsuccessful provider calls when usage exists;unknown is not zero.',
        '- This is an ASPIRE-inspired batch update:physical failure traces -> model-written document -> independent repair verification -> append/freeze -> unseen-product evaluation.It does not reproduce ASPIRE evolutionary program search,robot hardware or multimodal execution engine.One batch update is not evidence of indefinite autonomous improvement.Preserving old document bytes does not establish that combined-library behavior has no regressions.',
        '', '## Evidence files','',
        '`input_physics_diagnosis.json` separates setup/engine errors,including observed very-small-mesh MuJoCo compiler failures,from planning outcomes. `development_evidence.json` separates actually observed discovery/validation queries,rejection types,measured repair opportunities and document admission. `matched_conditions_audit.json` verifies matched contracts;`failure_diagnosis.json` retains all observed mechanisms;`trials.csv`/`paired_deltas.csv` locate product-level differences;`memory_context_audit.json` and `behavior_audit.json` separate document presence from behavior. `replay/audit.json` verifies actual MuJoCo events after scoring. No performance result is proof of industrial deployment or reproduction of ASAP numerical results.']
    (ROOT/'analysis/INTERPRETATION.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':main()

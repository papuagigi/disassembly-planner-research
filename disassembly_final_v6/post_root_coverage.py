"""Post-score finite root-action evidence; no new physics, model call or score."""
from collections import Counter
from .common import ROOT,read,write,utc

DIRECTIONS=('+x','-x','+y','-y','+z','-z')
PHYSICAL_REJECTIONS={'path_collision','unstable_remainder'}


def coverage(observation,traces,*,replay_ok,health_ok):
    key=observation['state_key']
    expected={(p['id'],d) for p in observation['remaining_parts'] if not p.get('fixed',False)
              for d in p.get('allowed_directions',DIRECTIONS)}
    outcomes={};reasons=Counter()
    for t in traces:
        pair=(t.get('part_id'),t.get('direction'))
        if t.get('physical_state_key_before')!=key or pair not in expected:continue
        if t.get('valid') is True:outcomes.setdefault(pair,set()).add('valid')
        elif t.get('reason') in PHYSICAL_REJECTIONS:
            outcomes.setdefault(pair,set()).add('rejected');reasons[t['reason']]+=1
    valid={p for p,v in outcomes.items() if 'valid' in v}
    rejected={p for p,v in outcomes.items() if v=={'rejected'}}
    conflicts={p for p,v in outcomes.items() if len(v)>1}
    missing=expected-set(outcomes)
    no_action=bool(expected and not missing and not valid and not conflicts and replay_ok and health_ok)
    return dict(root_state_key=key,expected_pairs=len(expected),observed_physical_pairs=len(outcomes),
        rejected_pairs=len(rejected),valid_pairs=[list(p) for p in sorted(valid)],
        missing_pairs=[list(p) for p in sorted(missing)],conflicting_pairs=[list(p) for p in sorted(conflicts)],
        root_rejection_observations=dict(reasons),all_arm_replays_verified=replay_ok,
        all_arm_native_logs_warning_free=health_ok,no_admissible_first_action_in_local_finite_API=no_action,
        scope='Exact initial surviving poses and velocities;declared directions only;verified checker evidence. No claim about original ASAP,rotations,holding or real-world impossibility.')


def main():
    manifest=read(ROOT/'outputs/evaluation/manifest.json')
    audit=read(ROOT/'replay/audit.json');assert audit['status']=='PASS'
    rows=[]
    for case in manifest['cases']:
        traces=[];by_arm={};health_ok=True;replay_ok=True
        shared=read(case['shared_path'])
        for arm in ['A','B','C']:
            folder=ROOT/'outputs/evaluation/trials'/case['case_id']/arm
            r=read(folder/'result.json');by_arm[arm]=r.get('trace',[]);traces+=r.get('trace',[])
            health_ok=health_ok and read(folder/'engine_health.json')['warning_free_observed']
            records=[a for a in audit['episodes'] if a['case_id']==case['case_id'] and a['arm']==arm]
            replay_ok=replay_ok and len(records)==1 and records[0]['status'] in ('PASS','PASS_VERIFIED_PREFIX')
        row=dict(case_id=case['case_id'],**coverage(shared['observation'],traces,replay_ok=replay_ok,health_ok=health_ok))
        known_valid={tuple(p) for p in row['valid_pairs']};root=row['root_state_key'];profiles={}
        for arm,arm_trace in by_arm.items():
            initial=[t for t in arm_trace if t.get('physical_state_key_before')==root]
            tested={(t['part_id'],t['direction']) for t in initial}
            profiles[arm]=dict(completed_initial_state_queries=len(initial),
                known_valid_root_actions_not_tested=[list(p) for p in sorted(known_valid-tested)],
                first_valid_initial_action=next(({k:t.get(k) for k in ['checker_call','part_id','direction','valid','committed']} for t in initial if t.get('valid')),None))
        row['per_arm_initial_search']=profiles
        rows.append(row)
    write(ROOT/'analysis/root_action_coverage.json',dict(utc=utc(),mode='post_score_evidence_only',cases=rows,
        no_new_physics_queries=True,no_model_calls=True,original_scores_unchanged=True,
        incomplete_charged_queries_have_no_invented_outcomes=True))
    lines=['# Initial-state action coverage after scoring','',
        'This diagnostic merges only actual completed physical queries at the exact initial state,after independent replay. It neither searches a new path nor changes a policy,score,cohort or document. Missing directions remain unknown. A verified prefix does not invent the unfinished query outcome.','',
        '|CAD|Declared initial actions|Observed physical outcomes|Observed valid actions|Unobserved actions|All initial actions rejected under local API|',
        '|---|---:|---:|---:|---:|---|']
    for r in rows:lines.append(f"|{r['case_id']}|{r['expected_pairs']}|{r['observed_physical_pairs']}|{len(r['valid_pairs'])}|{len(r['missing_pairs'])}|{r['no_admissible_first_action_in_local_finite_API']}|")
    lines += ['', 'Only full coverage,zero observed valid actions,zero conflicting outcomes,verified replay and warning-free native logs support the finite-API no-first-action conclusion. Otherwise complete disassembly feasibility remains unresolved. A valid first action does not establish a full sequence. Initial stability alone does not establish disassembly feasibility. This is a conditional checker result,not an original ASAP or real-world impossibility certificate. Do not interpret universal policy failure as proof that a skill library cannot help.',
        '', 'The JSON also identifies valid initial actions observed in another arm that a given arm never tried at the exact initial state. This describes budgeted search coverage,not a causal effect of document text. Generated policies and scheduling also differ;one first episode per arm cannot isolate a particular heuristic. These post-score facts are never supplied back to a planner or skill bank.']
    (ROOT/'analysis/ROOT_ACTION_COVERAGE.md').write_text('\n'.join(lines)+'\n')
    return rows

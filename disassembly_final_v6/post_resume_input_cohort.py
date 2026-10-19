"""Bind all qualifying inputs under a documented pre-outcome count amendment."""
from pathlib import Path
from .common import ROOT,WORKSPACE,read,write,sha,utc
from .protocol import verify
from .post_cohort_scope import effective_target


def main():
    frozen=verify()
    assert not list((ROOT/'outputs/evaluation/trials').glob('*/*/job.json'))
    assert not (ROOT/'outputs/evaluation/manifest.json').exists()
    assert not (ROOT/'outputs/input_audit/selected_evaluation.json').exists()
    state=read(ROOT/'outputs/pipeline_state.json')
    assert state['status']=='STOPPED_WITH_RECORDED_ERROR' and 'Finite evaluation reserve exhausted: 3/4' in state['error']
    progress=read(ROOT/'outputs/input_audit/progress_evaluation.json')
    cases=progress['cases']
    assert len(progress['statuses'])==75 and len(cases)==3
    assert frozen['minimum_CAD_requirements']['evaluation']==4
    assert frozen['limits']['max_rss_bytes']==4*1024**3
    evidence=ROOT/'analysis/input_cohort_exhaustion.json'
    assert read(evidence)['actual_final_episodes_started']==0
    amendment=dict(utc=utc(),scope_of_change='final_CAD_count_only',original_target=4,effective_target=3,
        original_freeze_sha256=sha(ROOT/'outputs/protocol/freeze.json'),
        exhaustion_evidence_path=str(evidence.relative_to(ROOT)),exhaustion_evidence_sha256=sha(evidence),
        case_ids=[c['case_id'] for c in cases],decision_before_policy_outcomes=True,
        frozen_actor_bank_physics_unchanged=True,source_order_fixed=True,
        decision_basis='User requested uninterrupted completion within the time target and explicitly allowed reducing the test allocation. Agent uses all three passing inputs after all75fixed candidates were exhausted;no policy outcome is available.',
        explicit_user_selection_of_three=False,agent_stated_assumption=True,
        limitation='Original four-CAD target unmet. Three-CAD/nine-episode descriptive pilot only;not an industrial success-rate estimate.')
    ap=ROOT/'outputs/protocol/cohort_amendment.json'
    write(ap,amendment,exclusive=True)
    assert effective_target()==3
    selected=dict(status='FINITE_COHORT_COMPLETE',effective_target=3,original_target=4,
        original_target_met=False,cohort_amendment_sha256=sha(ap),cases=cases,statuses=progress['statuses'],
        attempted=75,source_order_fixed=True,no_policy_result_gate=True,prepared_but_unused=[],
        selection=read(ROOT/'outputs/input_audit/pools.json')['selection'])
    write(ROOT/'outputs/input_audit/selected_evaluation.json',selected,exclusive=True)
    prior=read(ROOT/'outputs/input_audit/previous_geometry_fingerprints.json')
    known={r['fingerprint'] for r in prior['records']}
    known.update(c['geometry_fingerprint'] for c in read(ROOT/'outputs/input_audit/selected_development.json')['cases'])
    known.update(r['fingerprint'] for r in read(ROOT/'outputs/input_audit/current_opened_training_fingerprints.json')['records'])
    assets={}
    for case in cases:
        assert case['geometry_fingerprint'] not in known
        assert case['source_split']=='test_assembly' and case['required_removals']>=10
        cp=Path(case['case_path']);assert sha(cp)==case['case_sha256']
        assert sha(case['shared_path'])==case['shared_sha256']
        paths=[cp,Path(case['shared_path'])]
        for part in read(cp)['parts']:
            paths.append((cp.parent/part['visual_mesh']).resolve())
            paths.extend((cp.parent/p).resolve() for p in part['collision_meshes'])
        assets.update({str(p):sha(p) for p in paths})
    manifest=dict(created_utc=utc(),status='FINAL_INPUTS_BOUND',protocol_sha256=sha(ROOT/'outputs/protocol/freeze.json'),
        cohort_amendment_sha256=sha(ap),original_target_met=False,effective_target=3,
        cases=cases,excluded_prior_exact_geometry_duplicates=[],initial_physics_qualified_before_prior_shape_screen=3,
        prior_geometry_ledger_sha256=sha(ROOT/'outputs/input_audit/previous_geometry_fingerprints.json'),
        asset_sha256=assets,limits=frozen['limits'],arms=frozen['arms'],planned_episodes=9,
        model=frozen['model'],reasoning_effort=frozen['reasoning_effort'],library_updated_on_final_products=False,
        reference_search_used_for_selection=False,initial_observation_equal_per_case=True,
        source_split='official ASAP test_assembly',fresh_to_project=True)
    write(ROOT/'outputs/evaluation/manifest.json',manifest,exclusive=True)
    verify()
    return dict(status='READY_TO_RESUME_WITHOUT_RETRAINING',cases=3,first_episodes=9,
        protocol_unchanged=True,amendment_sha256=sha(ap),asset_files_verified=len(assets))


if __name__=='__main__':print(main())

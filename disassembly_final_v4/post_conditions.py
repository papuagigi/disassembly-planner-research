"""Audit actual first-episode contracts instead of trusting manifest flags."""
from .common import ROOT, read, write, sha, digest, utc
from .contracts import ARMS, LIMITS, MODEL, EFFORT
from .documents import DocumentBank
from .protocol import verify


def main():
    frozen=verify()
    manifest=read(ROOT/'outputs/evaluation/manifest.json')
    completion=read(ROOT/'outputs/evaluation/complete.json')
    assert len(manifest['cases'])>=10
    assert len(completion['episodes'])==3*len(manifest['cases'])
    prior=read(ROOT/'outputs/input_audit/previous_geometry_fingerprints.json')
    known={r['fingerprint'] for r in prior['records']}
    development=read(ROOT/'outputs/input_audit/selected_development.json')
    known.update(c['geometry_fingerprint'] for c in development['cases'])
    banks={a:DocumentBank(ROOT/'memory'/(conf['bank']+'.json')) for a,conf in ARMS.items()}
    assert not banks['A'].documents
    assert banks['B'].content_sha256==banks['C'].content_sha256
    rows=[];total=0
    for case in manifest['cases']:
        assert case['geometry_fingerprint'] not in known
        assert case['source_split']=='test_assembly' and case['required_removals']>=10
        assert sha(case['case_path'])==case['case_sha256']
        assert sha(case['shared_path'])==case['shared_sha256']
        observations={};missing=[];bank_observed={};calls=0
        for arm,conf in ARMS.items():
            folder=ROOT/'outputs/evaluation/trials'/case['case_id']/arm
            job=read(folder/'job.json');result=read(folder/'result.json')
            assert job['architecture']==conf['architecture']==result['architecture']
            assert job['limits']==result['limits']==LIMITS==frozen['limits']
            assert job['case_path']==case['case_path'] and job['shared_path']==case['shared_path']
            assert job['bank_path']==str(banks[arm].path)
            assert job['phase']=='evaluation' and job['arm']==result['condition']==arm
            assert result['phase']=='evaluation' and result['first_encounter']
            assert result['learning_updates']==0
            assert result.get('repeat',1)==1  # Worker failure may lack final-only decoration.
            assert result['model']==MODEL and result['reasoning_effort']==EFFORT
            assert 0<=result['llm_calls']<=LIMITS['max_calls']
            assert 0<=result['checker_calls']<=LIMITS['max_checks']
            h=result.get('initial_observation_sha256')
            if h:
                assert digest(result['initial_observation'])==h
                observations[arm]=h
            else:missing.append(arm)
            if result.get('bank_content_sha256'):
                assert result['bank_content_sha256']==banks[arm].content_sha256
                bank_observed[arm]=result['bank_content_sha256']
            for p in (folder/'llm_calls').glob('call_*/metadata.json'):
                m=read(p)
                assert m['requested_model']==MODEL and m['requested_reasoning_effort']==EFFORT
                calls+=1
            total+=1
        assert len(set(observations.values()))<=1,('Initial observation mismatch',case['case_id'])
        rows.append(dict(case_id=case['case_id'],same_case_and_shared_bytes=True,
            same_limits=True,same_requested_model_and_effort=True,bank_contract_equal_B_C=True,
            runtime_bank_hashes_observed=bank_observed,
            same_recorded_initial_observation=len(observations)==3,
            missing_runtime_initial_hash_arms=missing,available_initial_hashes=observations,
            provider_metadata_records_verified=calls,one_first_episode_per_arm=True,no_test_learning=True))
    assert total==manifest['planned_episodes']==len(completion['episodes'])
    receipt=dict(status='PASS_CONTRACTS',utc=utc(),cases=rows,episodes=total,
        requested_model=MODEL,requested_reasoning_effort=EFFORT,
        actual_served_model='Not independently identified beyond provider records',
        unavailable_runtime_fields_remain_unknown=True,
        shared_API_verified_by_frozen_source_hashes=True)
    write(ROOT/'analysis/matched_conditions_audit.json',receipt)
    return receipt

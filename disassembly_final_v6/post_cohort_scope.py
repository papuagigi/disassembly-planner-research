"""Explicit pre-outcome sample-count amendment; frozen planners stay unchanged."""
from datetime import datetime
from .common import ROOT,read,sha


def effective_target():
    frozen=read(ROOT/'outputs/protocol/freeze.json')
    original=frozen['minimum_CAD_requirements']['evaluation']
    path=ROOT/'outputs/protocol/cohort_amendment.json'
    if not path.exists():return original
    a=read(path)
    assert a['original_target']==original
    assert a['original_freeze_sha256']==sha(ROOT/'outputs/protocol/freeze.json')
    evidence=ROOT/a['exhaustion_evidence_path']
    assert sha(evidence)==a['exhaustion_evidence_sha256']
    e=read(evidence)
    assert e['actual_final_episodes_started']==0
    assert e['source_candidates_consumed']==75
    assert a['effective_target']==e['qualified_CADs']==len(a['case_ids'])
    assert a['case_ids']==[c['case_id'] for c in e['cases']]
    assert a['decision_before_policy_outcomes'] and a['frozen_actor_bank_physics_unchanged']
    assert a['scope_of_change']=='final_CAD_count_only'
    moment=datetime.fromisoformat(a['utc'])
    for p in (ROOT/'outputs/evaluation/trials').glob('*/*/lifecycle_started.json'):
        assert datetime.fromisoformat(read(p)['utc'])>moment
    return a['effective_target']


def summary():
    path=ROOT/'outputs/protocol/cohort_amendment.json'
    if not path.exists():return None
    value=read(path)
    confirmation=ROOT/'outputs/protocol/cohort_amendment_confirmation.json'
    if confirmation.exists():
        receipt=read(confirmation)
        assert receipt['original_amendment_sha256']==sha(path)
        assert receipt['effective_CADs']==value['effective_target']
        value={**value,'subsequent_explicit_user_confirmation':receipt}
    return value

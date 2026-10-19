"""A single final-study freeze before unseen test geometry is opened."""
from .common import ROOT,WORKSPACE,read,write,sha,utc
from .contracts import LIMITS,MODEL,EFFORT,ARMS
from .documents import DocumentBank
from .scope import study_scope

def source_paths():
    paths=[p for p in ROOT.glob('*.py') if not p.name.startswith('post_')]+list((ROOT/'data_tools').glob('*.py'))+[ROOT/'PLAN.md',ROOT/'protocol/prior_sources.json']
    paths += [p for p in [ROOT/'protocol/prior_preparation.json',ROOT/'protocol/memory_budget_amendment.json'] if p.exists()]
    paths+=[ROOT/'outputs/input_audit/pools.json',ROOT/'outputs/input_audit/selected_development.json',ROOT/'memory/S0.json',ROOT/'memory/S3.json']
    paths+=[ROOT/'outputs/protocol/conversion_development.json',ROOT/'outputs/protocol/conversion_evaluation.json']
    if (ROOT/'outputs/input_audit/current_opened_training_fingerprints.json').exists():paths.append(ROOT/'outputs/input_audit/current_opened_training_fingerprints.json')
    if (ROOT/'config/study_scope.json').exists():paths.append(ROOT/'config/study_scope.json')
    for name in ['coacd/__init__.py','coacd/lib_coacd.dylib']:
        p=ROOT/'.deps'/name
        if p.exists():paths.append(p)
    for folder in ['disassembly_real_v3','disassembly_real_v2','disassembly_real_v1','disassembly_mujoco','disassembly_learning_v3','disassembly_learning_v2','disassembly_recovery','disassembly_hybrid']:
        paths+=list((WORKSPACE/folder).glob('*.py'))
    paths+=list((WORKSPACE/'disassembly_planner_2d/planner2d').glob('*.py'))
    return sorted(set(paths))

def freeze():
    freeze_path=ROOT/'outputs/protocol/freeze.json'
    if freeze_path.exists():return verify()
    cohort=read(ROOT/'outputs/input_audit/selected_development.json')
    scope=study_scope()
    ledger=ROOT/'outputs/input_audit/current_opened_training_fingerprints.json'
    if not ledger.exists():
        records=[dict(id=p.parent.name,fingerprint=read(p)['assembly_geometry_fingerprint'],source_sha256=sha(p))
            for p in sorted((ROOT/'outputs/input_audit/development').glob('*/source_inventory.json'))]
        prior=WORKSPACE/'disassembly_final_v5/outputs/input_audit/development'
        records += [dict(id=p.parent.name,fingerprint=read(p)['assembly_geometry_fingerprint'],source_sha256=sha(p),prior_study='v5')
            for p in sorted(prior.glob('*/source_inventory.json'))]
        write(ledger,dict(utc=utc(),records=records,includes_unused_and_excluded_inputs=True),exclusive=True)
    assert len(cohort['discovery_cases'])==scope['full_discovery_CADs'] and len(cohort['validation_cases'])==scope['validation_CADs']
    collected=read(ROOT/'outputs/development/discovery_complete.json')['cases']
    assert len(collected)==scope['full_discovery_CADs']+scope.get('memory_extension_episodes',0)
    if all('case' in r for r in collected):
        assert len({r['case']['case_id'] for r in collected})==scope['full_discovery_CADs']
    observed_discovery=sum(bool(read(r['result_path']).get('trace')) for r in collected)
    observed_unique=(len({r['case']['case_id'] for r in collected if read(r['result_path']).get('trace')})
                     if all('case' in r for r in collected) else observed_discovery)
    validated=[]
    for c in cohort['validation_cases']:
        p=ROOT/'outputs/development/full_validation'/c['case_id']/'result.json'
        assert p.exists(),'Every independent validation CAD must retain its actual attempted episode,including negative infrastructure outcomes'
        validated.append(p)
    assert 'OK' in (ROOT/'outputs/regressions.log').read_text()
    assert not any((ROOT/'data/source/asap_test').glob('*/'))
    bank=DocumentBank(ROOT/'memory/S3.json')
    paths=source_paths()
    for row in bank.manifest['skills']:
        q=ROOT/'memory'/row['path'];paths.append(q)
        ref=q.parent/'references/admission.json'
        if ref.exists():paths.append(ref)
    value=dict(status='FROZEN_BEFORE_FINAL_TEST_GEOMETRY',utc=utc(),model=MODEL,reasoning_effort=EFFORT,
        limits=LIMITS,arms=ARMS,bank_sha256=bank.sha256,bank_content_sha256=bank.content_sha256,
        sha256={str(q.resolve()):sha(q) for q in paths},minimum_CAD_requirements=dict(discovery=scope['full_discovery_CADs'],validation=scope['validation_CADs'],evaluation=scope['evaluation_CADs']),
        cohort_scope=scope,
        no_test_updates=True,time_cuts_seconds=[180,600,900])
    value.update(actual_attempted_full_discovery_CADs=scope['full_discovery_CADs'],actual_full_discovery_episodes=len(collected),actual_physically_observed_full_discovery_CADs=observed_unique,
        actual_physically_observed_full_discovery_episodes=observed_discovery,
        actual_attempted_validation_CADs=len(validated),actual_physically_observed_validation_CADs=sum(bool(read(p).get('trace')) for p in validated))
    write(freeze_path,value,exclusive=True);return value

def verify():
    value=read(ROOT/'outputs/protocol/freeze.json')
    for name,expected in value['sha256'].items():assert sha(name)==expected,('Frozen source changed',name)
    return value

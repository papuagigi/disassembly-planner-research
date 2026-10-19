"""A single final-study freeze before unseen test geometry is opened."""
from .common import ROOT,WORKSPACE,read,write,sha,utc
from .contracts import LIMITS,MODEL,EFFORT,ARMS
from .documents import DocumentBank

def source_paths():
    paths=[p for p in ROOT.glob('*.py') if not p.name.startswith('post_')]+list((ROOT/'data_tools').glob('*.py'))+[ROOT/'PLAN.md',ROOT/'protocol/prior_sources.json']
    paths+=[ROOT/'outputs/input_audit/pools.json',ROOT/'outputs/input_audit/selected_development.json',ROOT/'memory/S0.json',ROOT/'memory/S3.json']
    paths+=[ROOT/'outputs/protocol/conversion_development.json',ROOT/'outputs/protocol/conversion_evaluation.json']
    for name in ['coacd/__init__.py','coacd/lib_coacd.dylib']:
        p=ROOT/'.deps'/name
        if p.exists():paths.append(p)
    for folder in ['disassembly_real_v3','disassembly_real_v2','disassembly_real_v1','disassembly_mujoco','disassembly_learning_v3','disassembly_learning_v2','disassembly_recovery','disassembly_hybrid']:
        paths+=list((WORKSPACE/folder).glob('*.py'))
    paths+=list((WORKSPACE/'disassembly_planner_2d/planner2d').glob('*.py'))
    return sorted(set(paths))

def freeze():
    p=ROOT/'outputs/protocol/freeze.json'
    if p.exists():return verify()
    cohort=read(ROOT/'outputs/input_audit/selected_development.json')
    assert len(cohort['discovery_cases'])==10 and len(cohort['validation_cases'])>=10
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
        sha256={str(q.resolve()):sha(q) for q in paths},minimum_CAD_requirements=dict(discovery=10,validation=10,evaluation=10),
        no_test_updates=True,time_cuts_seconds=[180,600,900])
    write(p,value,exclusive=True);return value

def verify():
    value=read(ROOT/'outputs/protocol/freeze.json')
    for name,expected in value['sha256'].items():assert sha(name)==expected,('Frozen source changed',name)
    return value

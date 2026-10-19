"""Freeze actors and learned documents before any new held-out OBJ is opened."""
import argparse
import importlib.metadata
from .common import ROOT,WORKSPACE,read,write,sha,utc
from .contracts import LIMITS,MODEL,EFFORT,ARMS

def freeze():
    path=ROOT/'outputs/protocol/freeze.json'
    if path.exists():return verify()
    complete=read(ROOT/'outputs/development/complete.json')
    from .documents import DocumentBank
    bank=DocumentBank(ROOT/'memory/S2.json');assert bank.sha256==complete['bank_sha256']
    pools=read(ROOT/'outputs/input_audit/pools.json')
    new_ids={r['id'] for r in pools['evaluation_candidates']}
    opened={p.name for p in (ROOT/'data/source/asap_test').glob('*') if p.is_dir()}
    assert not new_ids&opened,'A held-out product was opened before freeze'
    assert 'OK' in (ROOT/'outputs/regressions_final.log').read_text()
    count=complete['actual_new_discovery_CADs']
    assert count>=pools['minimum_discovery_CADs'],'Minimum discovery CAD count not reached'
    assert complete['actual_new_validation_CADs']>=pools['minimum_validation_CADs'],'Minimum independent validation CAD count not reached'
    assert complete['actual_new_discovery_CADs_with_physical_observations']>=pools['minimum_discovery_CADs'],'Minimum physically observed discovery CAD count not reached'
    assert complete['actual_new_validation_CADs_with_physical_observations']>=pools['minimum_validation_CADs'],'Minimum physically observed validation CAD count not reached'
    target=max(0,min(pools['evaluation_target'],count-1))
    paths=[p for p in ROOT.glob('*.py') if not p.name.startswith('post_')]
    paths+=list((ROOT/'data_tools').glob('*.py'))+list((ROOT/'tests').glob('*.py'))
    paths += [ROOT/'PLAN.md',ROOT/'outputs/input_audit/pools.json',ROOT/'outputs/input_audit/selected_development.json',
        ROOT/'outputs/input_audit/previous_geometry_fingerprints.json',
        ROOT/'outputs/protocol/conversion_development.json',ROOT/'outputs/protocol/conversion_evaluation.json',
        ROOT/'memory/S0.json',ROOT/'memory/S1.json',ROOT/'memory/S2.json',ROOT/'outputs/development/complete.json']
    for row in bank.manifest['skills']:
        p=ROOT/'memory'/row['path'];paths.append(p)
        if (p.parent/'references/admission.json').exists():paths.append(p.parent/'references/admission.json')
    for folder in ['disassembly_real_v3','disassembly_real_v2','disassembly_real_v1','disassembly_mujoco',
            'disassembly_learning_v3','disassembly_learning_v2','disassembly_abc_v3','disassembly_recovery','disassembly_hybrid']:
        paths.extend((WORKSPACE/folder).glob('*.py'))
    paths.append(WORKSPACE/'disassembly_docskills_v1/data_tools/inventory_sources.py')
    paths.extend((WORKSPACE/'disassembly_planner_2d/planner2d').glob('*.py'))
    packages={}
    for name in ['mujoco','numpy','scipy','trimesh','coacd','python-fcl']:
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]='not installed as package; see pinned collision preparation config'
    for distribution in importlib.metadata.distributions(path=[str(ROOT/'.deps')]):
        if distribution.metadata['Name'].lower()=='coacd':packages['coacd']=distribution.version
    for filename in ['coacd/__init__.py','coacd/lib_coacd.dylib']:
        p=ROOT/'.deps'/filename
        if p.exists():paths.append(p)
    result=dict(status='FROZEN_BEFORE_NEW_EVALUATION_OBJ',created_utc=utc(),model=MODEL,reasoning_effort=EFFORT,
        limits=LIMITS,arms=ARMS,packages=packages,sha256={str(p.resolve()):sha(p) for p in sorted(set(paths))},
        new_evaluation_geometry_not_opened=True,one_first_episode_per_arm=True,no_test_updates=True,
        actual_new_discovery_CADs=count,actual_new_validation_CADs=complete['actual_new_validation_CADs'],
        minimum_CAD_requirements={k:pools['minimum_'+k+'_CADs'] for k in ['discovery','validation','evaluation']},
        evaluation_target=target,evaluation_target_rule='min(configured_evaluation_target,actual_new_discovery_CADs-1)',
        final_source_candidate_count=len(pools['evaluation_candidates']),qualification='initial physics only; no full-path gate',
        bank_sha256=bank.sha256,bank_content_sha256=bank.content_sha256,time_cuts_seconds=[30,60,120,180],
        retrieval='required initial model-requested document review;read calls and time charged',
        final_episodes_serial_and_no_concurrent_CAD_preparation=True)
    write(path,result,exclusive=True);print('FROZEN',len(result['sha256']),target,flush=True);return result

def verify():
    result=read(ROOT/'outputs/protocol/freeze.json')
    for name,expected in result['sha256'].items():assert sha(name)==expected,('Frozen source changed',name)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','verify']);a=p.parse_args();globals()[a.command]()

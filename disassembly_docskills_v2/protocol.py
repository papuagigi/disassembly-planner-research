"""Pre-geometry actor/document freeze for the new finite cohort."""
import argparse
import importlib.metadata
from .common import ROOT,WORKSPACE,read,write,sha,utc
from .contracts import LIMITS,MODEL,EFFORT,ARMS

def freeze():
    path=ROOT/'outputs/protocol/freeze.json'
    if path.exists():return verify()
    assert not (ROOT/'data/source/asap_training').exists(),'Final source OBJ bytes opened before freeze'
    assert read(ROOT/'outputs/development/selected_admission.json')['status'] in ('ADMITTED','ADMITTED_PHYSICAL_PROCEDURE')
    assert read(ROOT/'outputs/development/normal_controller_checks/complete.json')['status']=='PASS'
    assert 'OK' in (ROOT/'outputs/development/regressions.log').read_text()
    paths=[p for p in ROOT.glob('*.py') if not p.name.startswith('post_')]+list((ROOT/'data_tools').glob('*.py'))+list((ROOT/'tests').glob('*.py'))
    paths += [ROOT/'PLAN.md',ROOT/'outputs/input_audit/reserve.json',ROOT/'outputs/protocol/conversion_config.json',ROOT/'memory/S0.json',ROOT/'memory/S1.json']
    manifest=read(ROOT/'memory/S1.json')
    for row in manifest['skills']:
        p=ROOT/'memory'/row['path'];paths.extend([p,p.parent/'references/admission.json'])
    # Preserve the exact shared underlying physics/runtime/API code, not only
    # the new orchestration files. Native dependency versions are recorded too.
    for folder in ['disassembly_real_v3','disassembly_real_v2','disassembly_real_v1','disassembly_mujoco',
                   'disassembly_learning_v3','disassembly_learning_v2','disassembly_abc_v3','disassembly_recovery','disassembly_hybrid']:
        paths.extend((WORKSPACE/folder).glob('*.py'))
    paths.append(WORKSPACE/'disassembly_docskills_v1/data_tools/inventory_sources.py')
    paths.extend((WORKSPACE/'disassembly_planner_2d/planner2d').glob('*.py'))
    hashes={str(p.resolve()):sha(p) for p in sorted(set(paths))}
    packages={}
    for name in ['mujoco','numpy','scipy','trimesh','coacd','python-fcl']:
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]='not installed as package'
    result=dict(status='FROZEN_BEFORE_NEW_OBJ',created_utc=utc(),model=MODEL,reasoning_effort=EFFORT,limits=LIMITS,arms=ARMS,
        packages=packages,sha256=hashes,source_reserve_sha256=sha(ROOT/'outputs/input_audit/reserve.json'),
        no_new_evaluation_geometry=True,no_test_updates=True,one_first_episode_per_arm=True,
        qualification='initial physics only; no full-path search gate',max_source_ids=64,max_qualified_cases=24,
        time_cuts_seconds=[30,60,120,180],retrieval='required initial model-requested physical-document review,read cost included')
    write(path,result,exclusive=True);print('FROZEN',len(hashes),flush=True);return result

def verify():
    value=read(ROOT/'outputs/protocol/freeze.json')
    for name,expected in value['sha256'].items():
        assert sha(name)==expected,('Frozen source changed',name)
    return value

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','verify']);a=p.parse_args();globals()[a.command]()

"""Immutable pre-geometry protocol and code/document hash receipts."""
from __future__ import annotations
import argparse
import importlib.metadata
from pathlib import Path
import shutil
import subprocess
import sys
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress
from .contracts import MODEL,EFFORT,LIMITS,ARMS

PATH=ROOT/'outputs/protocol/freeze.json'

def prepare():
    folder=ROOT/'outputs/protocol';folder.mkdir(parents=True,exist_ok=True)
    config=read(WORKSPACE/'disassembly_real_v3/outputs/protocol/conversion_config.json')
    config.update(asset_namespace='final_01',case_namespace='final_01',receipt_namespace='final_01',
        selection='First three locally stable and independently full-path-verified sources in the predeclared twenty-ID reserve; official source certificate reported separately',
        development_calibration='outputs/development/physics + unchanged real_v3 geometry regression tests',
        source_geometry_tuning='No post-freeze changes; original geometry/relative placement preserved')
    write(folder/'conversion_config.json',config,exclusive=True)
    source=WORKSPACE/'disassembly_real_v3/research/upstream_witness/certify_local_sequence.py'
    text=source.read_text().replace('ROOT=Path(__file__).resolve().parents[2]','ROOT=Path(__file__).resolve().parents[1]').replace("VENDOR=ROOT/'vendor/ASAP'","VENDOR=ROOT.parent/'disassembly_real_v3/vendor/ASAP'").replace('save_sdf=True','save_sdf=False')
    target=ROOT/'research/certify_source.py';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
    write(ROOT/'references/official_certificate_adaptation.json',dict(source=str(source),source_sha256=sha(source),
        destination=str(target),changes=['new output/source root','read-only official code path','disable SDF cache writes'],
        official_algorithm_unchanged=True),exclusive=True)

def check_regressions():
    cmd=[sys.executable,'-B','-m','unittest','discover','-s','disassembly_docskills_v1/tests','-v']
    ours=subprocess.run(cmd,capture_output=True,text=True)
    old=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','disassembly_real_v3/tests','-v'],capture_output=True,text=True)
    folder=ROOT/'outputs/development';folder.mkdir(exist_ok=True)
    (folder/'regressions.log').write_text(ours.stdout+ours.stderr+old.stdout+old.stderr)
    receipt=dict(status='PASS' if not ours.returncode and not old.returncode else 'FAIL',created_utc=utc(),
        own_returncode=ours.returncode,unchanged_geometry_returncode=old.returncode,log_sha256=sha(folder/'regressions.log'))
    write(folder/'regressions.json',receipt);assert receipt['status']=='PASS'
    return receipt

def freeze():
    assert not PATH.exists(),'Never replace pre-geometry freeze'
    assert not (ROOT/'data/source/asap_training').exists(),'Final source geometry must be unopened'
    selected_path=ROOT/'outputs/development/selected_admission.json'
    admission_path=Path(read(selected_path)['receipt']) if selected_path.exists() else ROOT/'outputs/development/admission.json'
    admission=read(admission_path);assert admission['status']=='ADMITTED'
    regressions=check_regressions()
    old=read(WORKSPACE/'disassembly_real_v3/outputs/protocol/before_fresh_source_freeze.json')
    sources=dict(old['source_sha256'])
    sources.update({str(p.resolve()):sha(p) for p in ROOT.rglob('*.py') if not any(s in p.parts for s in ['.deps','.collision_deps','.conversion_deps','outputs'])})
    docs={str(p.resolve()):sha(p) for p in (ROOT/'memory').rglob('*') if p.is_file()}
    physical={str(p.resolve()):sha(p) for p in (ROOT/'outputs/development/physics').glob('*.json')}
    dependencies={}
    for package in ['mujoco','numpy','scipy','trimesh','coacd']:
        try:dependencies[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:dependencies[package]='read-only supplemental directory; see conversion receipt'
    value=dict(status='FROZEN_BEFORE_FINAL_GEOMETRY',created_utc=utc(),model=MODEL,reasoning_effort=EFFORT,
        limits=LIMITS,arms=ARMS,episode_policy='one first budgeted normal episode per product and arm; no evaluation library update',
        physical_task='n-1 committed stable removals; permanent original fixture remains; local model only',
        code_sha256=sources,document_sha256=docs,development_physics_sha256=physical,
        conversion_config_sha256=sha(ROOT/'outputs/protocol/conversion_config.json'),reserve_sha256=sha(ROOT/'outputs/input_audit/reserve.json'),
        reserve_ids=read(ROOT/'outputs/input_audit/reserve.json')['ids'],requested_cases=3,reserve_size=20,
        independent_reference_budget=dict(max_checks=2400,max_seconds=180),
        admission_criteria_sha256=admission['criteria_sha256'],
        admission_path=str(admission_path),admission_sha256=sha(admission_path),regressions=regressions,dependencies=dependencies,
        metrics_sha256=sha(ROOT/'metrics.py'),actual_provider_tokens_reported=True,
        limitations=['small conditional cohort; no factory provenance','bounded DFS reference selection favors representable paths and may favor DFS',
            'no weight updates; one document update only','call/check/wall ceilings equal; actual tokens and code/ranking response costs differ',
            'code instruction count vs controller instruction count is an accounting cap, not equivalent cognitive work',
            'output byte guard is checked after provider generation; does not bound internal reasoning tokens before generation',
            'fixed source-axis translations and finite geometric samples; uncalibrated scale/materials/workholding; not full manufacturing disassembly'])
    write(PATH,value,exclusive=True);progress('pre_geometry_frozen',code_files=len(sources),documents=len(docs),reserve=20)
    print('PRE_GEOMETRY_FROZEN',sha(PATH),flush=True)

def verify():
    value=read(PATH)
    for table in ['code_sha256','document_sha256','development_physics_sha256']:
        for p,expected in value[table].items():assert sha(p)==expected,('Frozen evidence changed',p)
    assert sha(ROOT/'outputs/protocol/conversion_config.json')==value['conversion_config_sha256']
    assert sha(ROOT/'outputs/input_audit/reserve.json')==value['reserve_sha256']
    return value

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','freeze','verify','test']);a=p.parse_args()
    {'prepare':prepare,'freeze':freeze,'verify':verify,'test':check_regressions}[a.command]()

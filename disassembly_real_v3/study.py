"""Frozen first-encounter A/B/C study after upstream-path calibration."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from .common import ROOT, WORKSPACE, MODEL, EFFORT, LIMITS, CONDITIONS, read, write, digest, prepare, solve, neutral_observation_hash
from .memory import SkillBank

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def progress(phase, **details):
    row = dict(phase=phase, updated_utc=now(), owner='Codex', claude_assigned=False, **details)
    write(ROOT/'outputs/progress.json', row)
    with (ROOT/'outputs/journal.jsonl').open('a') as f:
        f.write(json.dumps(row, ensure_ascii=False)+'\n')

def sources():
    previous=read(WORKSPACE/'disassembly_real_v2/outputs/protocol/before_fresh_source_freeze.json')['source_sha256']
    current=set(ROOT.glob('*.py')) | set((ROOT/'data_tools').glob('*.py'))
    current.update((ROOT/'research/upstream_witness').glob('*.py'))
    current.update((ROOT/'vendor/ASAP').rglob('*.py'))
    for directory in [ROOT/'.upstream_build/redmax',ROOT/'.collision_deps/fcl',ROOT/'.collision_deps/rtree']:
        current.update(p for p in directory.rglob('*') if p.is_file() and p.suffix in {'.py','.so','.dylib'})
    current.update(p for p in (ROOT/'.collision_deps').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return sorted(set(map(Path,previous)) | current, key=str)

def verify_pre():
    value=read(ROOT/'outputs/protocol/before_fresh_source_freeze.json')
    for path, expected in value['source_sha256'].items():
        assert sha(path)==expected, ('Frozen code changed',path)
    for bank in value['banks'].values():
        assert sha(bank['path'])==bank['file_sha256'], 'Frozen skill bank changed'
    assert sha(value['conversion_config_path'])==value['conversion_config_sha256']
    assert sha(value['development_validation_path'])==value['development_validation_sha256']
    return value

def freeze():
    target=ROOT/'outputs/protocol/before_fresh_source_freeze.json'
    assert not target.exists(), 'Do not overwrite an existing freeze'
    validation=read(ROOT/'outputs/development/validation_summary.json')
    assert validation['status']=='PASS', 'Numerical upstream and local path validation required first'
    parent=read(WORKSPACE/'disassembly_real_v2/outputs/protocol/before_fresh_source_freeze.json')
    forbidden=set(parent['forbidden_source_ids'])
    forbidden.update(p.name for study in ['disassembly_real_v1','disassembly_real_v2']
                     for p in (WORKSPACE/study/'data/source/asap_training').iterdir() if p.is_dir())
    forbidden.update(validation.get('development_source_ids', []))
    bank=ROOT/'memory/S6.json'
    assert sha(bank)==sha(WORKSPACE/'disassembly_real_v2/memory/S6.json'), 'S6 must stay identical'
    config=ROOT/'outputs/protocol/conversion_config.json'
    from .data_tools.inventory_sources import assembly_fingerprint, load_mesh
    development_signatures=[]
    for manifest_path in (ROOT/'data/assemblies/development').glob('*/manifest.json'):
        development_manifest=read(manifest_path)
        meshes=[load_mesh((ROOT/p['mesh']).read_bytes()) for p in development_manifest['parts']]
        development_signatures.append(dict(source_id=development_manifest['source_assembly_id'],
            representation='assembled normalized source',signature=assembly_fingerprint(meshes)))
    for folder in (ROOT/'data/source').iterdir():
        meshes=sorted(folder.glob('*.obj')) if folder.is_dir() else []
        if meshes:
            development_signatures.append(dict(source_id=folder.name,representation='raw source group',
                signature=assembly_fingerprint([load_mesh(p.read_bytes()) for p in meshes])))
    value=dict(status='FROZEN_BEFORE_FRESH_GEOMETRY', created_utc=now(), model=MODEL,
        reasoning_effort=EFFORT, limits=LIMITS, conditions=list(CONDITIONS), tracks=['normal'],
        track_repetitions={'normal':1}, task='full_disassembly',
        require_source_certified_and_local_verified=True,reference_supplied_to_planners=False,
        source_sha256={str(p.resolve()):sha(p) for p in sources()},
        banks={'S6':dict(path=str(bank.resolve()),file_sha256=sha(bank),bank_sha256=SkillBank(bank).sha256)},
        bank_origin=dict(path=str((WORKSPACE/'disassembly_real_v2/memory/S6.json').resolve()),file_sha256=sha(bank)),
        forbidden_source_ids=sorted(forbidden),
        development_assembly_signatures=development_signatures,
        development_validation_path=str((ROOT/'outputs/development/validation_summary.json').resolve()),
        development_validation_sha256=sha(ROOT/'outputs/development/validation_summary.json'),
        conversion_config_path=str(config.resolve()),conversion_config_sha256=sha(config),
        fresh_rule=dict(after_id='00670',min_parts=5,max_parts=8,min_obj_bytes=100000,
                        max_obj_bytes=1000000,source_count=12,requested_cases=3,order='ascending original ID'),
        eligibility='Source numerical full path plus independently verified local full sequence under frozen generic geometry/action/fixture rule; evaluator-only qualification, no actor outcome gating.',
        interpretation='One first budgeted episode per case and condition; no test memory update, no reference leakage; equal ceilings, actual consumption reported.')
    write(target,value)
    for p in sources():
        dst=ROOT/'outputs/protocol/source_snapshot'/p.relative_to(WORKSPACE)
        dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(p.read_bytes())
    progress('frozen_before_fresh_source',source_files=len(value['source_sha256']))
    print(json.dumps({'status':value['status'],'source_files':len(value['source_sha256'])}),flush=True)

def bind_inputs():
    frozen=verify_pre();target=ROOT/'outputs/evaluation/manifest.json'
    assert not target.exists()
    selection=read(ROOT/'outputs/input_audit/selected_cases.json');assert selection['cases']
    cases=[];assets={};evidence={}
    for row in selection['cases']:
        assert row['reference']['source_certified'] and row['reference']['local_verified']
        cp=Path(row['case_path']);case=read(cp);paths={cp}
        for part in case['parts']:
            paths.add((cp.parent/part['visual_mesh']).resolve())
            paths.update((cp.parent/s).resolve() for s in part['collision_meshes'])
        assets.update({str(p.resolve()):sha(p) for p in paths})
        for label in ['source_certificate_path','local_validation_path']:
            witness=Path(row['reference'][label]);evidence[str(witness.resolve())]=sha(witness)
        for witness in Path(row['reference']['source_certificate_path']).parent.glob('*.npz'):
            evidence[str(witness.resolve())]=sha(witness)
        raw=ROOT/'data/source/asap_training'/row['source_assembly_id']
        for original in raw.iterdir():
            if original.suffix in {'.obj','.json'}:evidence[str(original.resolve())]=sha(original)
        qualification_shared=Path(row['reference']['local_validation_path']).parent/'qualification_shared_state.json'
        shared=read(qualification_shared)
        from .simulator import FullDisassemblySim
        from disassembly_recovery.shared_api import physical_state_key
        assert physical_state_key(FullDisassemblySim(cp,max_checks=LIMITS['max_checks']).export_state())==physical_state_key(shared['state'])
        assert shared['state']['checks']==0 and shared['state']['actions']==[] and shared['state']['trace']==[]
        assert shared['recovery_state']['restore_count']==0
        evidence[str(qualification_shared.resolve())]=sha(qualification_shared)
        path=ROOT/'outputs/evaluation/shared_inputs'/row['case_id']/'normal.json';write(path,shared)
        # Reference documents stay in evaluator metadata. The actor receives only
        # row.case_path and the identical public shared observation/state.
        cases.append({**row,'tracks':{'normal':dict(path=str(path.resolve()),sha256=sha(path),
            observation_sha256=neutral_observation_hash(shared['observation']),
            preparation_checks=shared['state']['checks'],preparation_seconds=shared['preparation_seconds'])}})
    catalog=Path(selection['source_catalog_path'])
    value={**frozen,'cases':cases,'planned_cases':len(cases),'planned_trials':len(cases)*3,
        'asset_sha256':assets,'input_dependency_sha256':evidence,
        'source_catalog_path':str(catalog),'source_catalog_sha256':sha(catalog),
        'selected_cases_sha256':sha(ROOT/'outputs/input_audit/selected_cases.json')}
    value['manifest_sha256']=digest(value);write(target,value)
    progress('inputs_bound',products=len(cases),planned_trials=value['planned_trials'])

def manifest():
    verify_pre();value=read(ROOT/'outputs/evaluation/manifest.json')
    assert digest({k:v for k,v in value.items() if k!='manifest_sha256'})==value['manifest_sha256']
    for path,h in value['asset_sha256'].items():assert sha(path)==h
    for path,h in value.get('input_dependency_sha256',{}).items():assert sha(path)==h
    assert sha(value['source_catalog_path'])==value['source_catalog_sha256']
    assert sha(ROOT/'outputs/input_audit/selected_cases.json')==value['selected_cases_sha256']
    for case in value['cases']:
        assert sha(case['tracks']['normal']['path'])==case['tracks']['normal']['sha256']
    return value

def worker(index, arm):
    from disassembly_mujoco.agent import CodexCLIProvider
    value=manifest();case=value['cases'][index];shared=read(case['tracks']['normal']['path'])
    folder=ROOT/'outputs/evaluation/trials'/case['case_id']/'normal/repeat_01'/arm
    assert not (folder/'started.json').exists(), 'Do not repeat a started first episode'
    write(folder/'started.json',dict(utc=now(),arm=arm,first_encounter=True,bank='S6' if arm!=CONDITIONS[0] else None))
    provider=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    began=time.monotonic();bank=ROOT/'memory/S6.json'
    result=solve(case,arm,provider,shared,bank_path=bank if arm!=CONDITIONS[0] else None)
    result.update(case_id=case['case_id'],case_path=case['case_path'],source_assembly_id=case['source_assembly_id'],
        condition=arm,method=arm,base_method=arm,track='normal',repeat=1,
        model=MODEL,reasoning_effort=EFFORT,limits=LIMITS,first_encounter=True,
        preparation_checks=shared['state']['checks'],preparation_seconds=shared['preparation_seconds'],
        expected_initial_observation_sha256=neutral_observation_hash(shared['observation']),
        elapsed_seconds_total=time.monotonic()-began,goal_type='full_disassembly',
        library_available=arm!=CONDITIONS[0],bank_version='S6' if arm!=CONDITIONS[0] else None,
        bank_sha256=SkillBank(bank).sha256 if arm!=CONDITIONS[0] else None,
        protocol_sha256=value['manifest_sha256'])
    write(folder/'result.json',result)
    print(json.dumps({k:result.get(k) for k in ['case_id','condition','success','termination','checker_calls','llm_calls','elapsed_seconds_total']}),flush=True)

def evaluate():
    value=manifest();schedule=[]
    for index,case in enumerate(value['cases']):
        order=list(CONDITIONS[index%3:])+list(CONDITIONS[:index%3])
        schedule.extend((index,case['case_id'],arm) for arm in order)
    path=ROOT/'outputs/evaluation/schedule.json'
    if not path.exists():write(path,dict(schedule=schedule,created_utc=now()))
    else:assert read(path)['schedule']==[list(x) for x in schedule]
    for index,cid,arm in schedule:
        folder=ROOT/'outputs/evaluation/trials'/cid/'normal/repeat_01'/arm
        if (folder/'result.json').exists():continue
        assert not (folder/'started.json').exists(), 'Interrupted episodes stay recorded; no silent retry'
        progress('first_encounter_evaluation',case=cid,arm=arm)
        p=subprocess.run([sys.executable,'-B','-m','disassembly_real_v3.study','worker','--index',str(index),'--arm',arm])
        assert p.returncode==0, 'Retain failed subprocess; do not rerun to replace outcome'
    manifest();write(ROOT/'outputs/evaluation/complete.json',dict(status='COMPLETE',utc=now(),trials=len(schedule)))
    progress('evaluation_complete',trials=len(schedule))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','bind','evaluate','worker']);p.add_argument('--index',type=int);p.add_argument('--arm');a=p.parse_args()
    if a.command=='freeze':freeze()
    elif a.command=='bind':bind_inputs()
    elif a.command=='evaluate':evaluate()
    else:worker(a.index,a.arm)

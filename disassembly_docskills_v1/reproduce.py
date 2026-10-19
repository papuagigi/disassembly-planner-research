"""Portable source-bundle checks, offline replay, or explicitly separate new runs.

Raw first-episode evidence is never edited. Portable replay changes only a
working descriptor's absolute case_path, leaving case bytes and states exact.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone
from .common import ROOT,WORKSPACE,read,write,sha,utc

def run_dir():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    path=ROOT/'outputs/reproduction_runs'/stamp;path.mkdir(parents=True)
    return path

def verify_bundle():
    path=WORKSPACE/'SOURCE_BUNDLE_MANIFEST.json'
    if not path.exists():raise RuntimeError('Use the final source bundle for this portable check; the live study uses protocol verify.')
    value=read(path)
    for relative,expected in value['files'].items():
        p=(WORKSPACE/relative).resolve();p.relative_to(WORKSPACE)
        assert sha(p)==expected,('Missing or changed bundle file',relative)
    print(json.dumps(dict(status='PASS',bundle_files=len(value['files']))))
    return value

def unit():
    folder=run_dir()
    process=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],capture_output=True,text=True,cwd=WORKSPACE)
    (folder/'unit.log').write_text(process.stdout+process.stderr)
    write(folder/'unit.json',dict(status='PASS' if not process.returncode else 'FAIL',returncode=process.returncode,
        runtime=sys.executable,module_root=str(ROOT),log_sha256=sha(folder/'unit.log')))
    print(process.stdout+process.stderr)
    assert process.returncode==0

def case_entry(name=None):
    manifest=read(ROOT/'outputs/evaluation/manifest.json')
    cases=manifest['cases'];assert cases,'No qualified scored case exists'
    return manifest,next((c for c in cases if c['case_id']==name),cases[0]) if name is None else next(c for c in cases if c['case_id']==name)

def offline_replay(name=None,arm='A'):
    from .evidence_replay import replay_result
    manifest,case=case_entry(name);case_id=case['case_id']
    rp=ROOT/'outputs/evaluation/trials'/case_id/arm/'result.json';raw=read(rp)
    cp=ROOT/'cases/final_01'/(case_id+'.json');assert sha(cp)==case['case_sha256']
    shared=ROOT/'outputs/input_audit/qualification'/case['source_assembly_id']/'shared.json'
    assert sha(shared)==case['shared_sha256']
    folder=run_dir();descriptor={**raw,'case_path':str(cp)};path=folder/'portable_result_descriptor.json'
    write(path,descriptor)
    audit,_,_=replay_result(path,shared_path=shared,output=folder/'replay_audit.json')
    write(folder/'provenance.json',dict(original_raw_result=str(rp),original_raw_result_sha256=sha(rp),
        descriptor_only_case_path_remapped=True,no_actor_or_model_calls=True,original_score_unchanged=True))
    print(json.dumps(audit))

def new_model_episode(name=None,arm='A'):
    from .driver import run
    from .contracts import ARMS
    manifest,case=case_entry(name);conf=ARMS[arm];folder=run_dir()
    cp=ROOT/'cases/final_01'/(case['case_id']+'.json')
    shared=ROOT/'outputs/input_audit/qualification'/case['source_assembly_id']/'shared.json'
    run(dict(folder=str(folder),case_path=str(cp),shared_path=str(shared),architecture=conf['architecture'],
        bank_path=str(ROOT/'memory'/(conf['bank']+'.json')),limits=manifest['limits'],
        phase='reproduction_new_episode_not_primary_first_encounter',arm=arm,
        protocol_sha256=manifest['protocol_sha256']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['verify','unit','replay','new-model-episode'])
    p.add_argument('--case');p.add_argument('--arm',choices=['A','B','C','C_S0'],default='A');a=p.parse_args()
    if a.command=='verify':verify_bundle()
    elif a.command=='unit':unit()
    elif a.command=='replay':offline_replay(a.case,a.arm)
    else:new_model_episode(a.case,a.arm)

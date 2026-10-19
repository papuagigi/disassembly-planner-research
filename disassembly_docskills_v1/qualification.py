"""Finite evaluator-only qualification; never imports a model or learned bank.

Final source acquisition requires an already frozen code/bank/protocol receipt.
The retained reference is withheld from all actors. Selection by bounded DFS is
an explicit representability and search-bias limitation, not factory coverage.
"""
from __future__ import annotations
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import numpy as np
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress

def source_record(aid):
    from .data_tools.inventory_sources import load_mesh,shape_fingerprint,assembly_fingerprint
    receipt=read(ROOT/'data/source/asap_training'/aid/'source_receipt.json')
    parts=[];meshes=[];reasons=[]
    for member in receipt['members']:
        if not member['path'].endswith('.obj'):continue
        p=ROOT/member['path'];assert sha(p)==member['sha256']
        mesh=load_mesh(p.read_bytes());meshes.append(mesh)
        components=len(mesh.split(only_watertight=False))
        if not mesh.is_watertight:reasons.append('nonwatertight')
        if components!=1:reasons.append('multiple_components')
        if mesh.volume<=0:reasons.append('nonpositive_volume')
        parts.append(dict(id=p.stem,source_member=member['member'],raw_relative_path=member['path'],
            source_sha256=sha(p),source_bytes=p.stat().st_size,shape_fingerprint=shape_fingerprint(mesh),
            watertight=bool(mesh.is_watertight),connected_components=components,volume=float(mesh.volume),bounds=mesh.bounds.tolist()))
    signature=assembly_fingerprint(meshes)
    # Prior audit records contain rigid-transform/scale-invariant source signatures.
    prior_matches=[]
    for study in WORKSPACE.glob('disassembly_*'):
        if study==ROOT or not study.is_dir():continue
        for p in (study/'outputs').glob('**/*geometry_inventory.json'):
            doc=read(p)
            for r in doc.get('all_considered_candidates',doc.get('assemblies',[])):
                if isinstance(r,dict) and r.get('assembly_geometry_fingerprint')==signature:prior_matches.append(str(p))
    row=dict(id=aid,case_id='asap_'+aid,source_assembly_id=aid,source_group='training_assembly',
        source_repository_commit='3727e716b57e0b508c4e9ecd9fefa6953e8f72da',
        source_archive_url=receipt['url'],part_count=len(parts),parts=parts,
        geometry_eligible=not reasons and not prior_matches,geometry_exclusion_reasons=sorted(set(reasons)),
        assembly_geometry_fingerprint=signature,prior_product_geometry_matches=prior_matches,
        raw_byte_receipt=str(ROOT/'data/source/asap_training'/aid/'source_receipt.json'))
    return row

def configure():
    from .data_tools import convert_cad as c
    cp=ROOT/'outputs/protocol/conversion_config.json';cfg=read(cp)
    c.CONFIG=copy.deepcopy(cfg);c.COACD_SETTINGS=copy.deepcopy(cfg['coacd'])
    c.ASSEMBLIES=ROOT/'data/assemblies'/cfg['asset_namespace'];c.CASES=ROOT/'cases'/cfg['case_namespace']
    c.CASES.mkdir(parents=True,exist_ok=True)
    os.environ['DISASSEMBLY_REAL_CONVERSION_CONFIG']=str(cp)
    return c

def shared_input(cp,max_checks=240):
    from disassembly_real_v3.simulator import FullDisassemblySim
    from disassembly_learning_v3.shared_api import SharedAPI
    sim=FullDisassemblySim(cp,max_checks=max_checks);api=SharedAPI(sim,max_checks=max_checks)
    # One evaluator checkpoint is common to every arm; not a planner-specific aid.
    api.checkpoint()
    return dict(state=sim.export_state(),recovery_state=api.export_recovery_state(),observation=api.snapshot())

def search(cp,shared):
    from disassembly_real_v3.simulator import FullDisassemblySim
    from disassembly_learning_v3.shared_api import SharedAPI
    from disassembly_hybrid.graph import physical_state_key
    began=time.monotonic();cap=2400;seconds=180
    sim=FullDisassemblySim(cp,max_checks=cap,state=shared['state'])
    api=SharedAPI(sim,recovery_state=shared['recovery_state'],max_checks=cap,max_checkpoints=4096,max_restores=4096)
    tried={};best=0;capacity=False
    def dfs():
        nonlocal best,capacity
        if sim.success:return True
        if sim.checks>=cap or time.monotonic()-began>=seconds:capacity=True;return False
        key=physical_state_key(sim.export_state());spent=tried.setdefault(key,set());h=api.checkpoint()
        parts=sorted((p for p in api.snapshot()['remaining_parts'] if not p.get('fixed')),key=lambda p:(-p['center'][2],p['id']))
        for p in parts:
            for d in ['+z','+x','-x','+y','-y','-z']:
                if sim.checks>=cap or time.monotonic()-began>=seconds:capacity=True;return False
                if d not in p.get('allowed_directions',[]) or (p['id'],d) in spent:continue
                spent.add((p['id'],d));r=api.remove(p['id'],d);best=max(best,len(sim.actions))
                if r['valid']:
                    if dfs():return True
                    api.restore(h)
        return False
    success=dfs()
    return dict(success=bool(success),actions=sim.actions if success else [],trace=sim.trace,checks=sim.checks,
        elapsed_seconds=time.monotonic()-began,best_removed=best,capacity=capacity,limit=dict(checks=cap,seconds=seconds),
        no_actor_or_llm=True,not_unique_or_optimal=True,withheld_from_actors=True)

def verify_path(cp,shared,actions):
    from disassembly_real_v3.simulator import FullDisassemblySim
    sim=FullDisassemblySim(cp,max_checks=len(actions),state=shared['state'])
    for a in actions:
        r=sim.remove(a['part_id'],a['direction'])
        if not r['valid']:raise AssertionError('Retained reference could not be independently re-executed')
    assert sim.success
    return dict(success=True,actions=sim.actions,trace=sim.trace,state=sim.export_state(),case_sha256=sha(cp),
        verification_scope='local sampled geometry and MuJoCo residual dynamics only',withheld_from_actors=True,unique=False,optimality_proven=False)

def official_certificate(entry,actions,folder):
    seq=folder/'source_sequence.json';write(seq,dict(sequence=[{k:a[k] for k in ['part_id','direction']} for a in actions]))
    out=folder/'official_ASAP_certificate';old=WORKSPACE/'disassembly_real_v3'
    script=ROOT/'research/certify_source.py';env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1',
        'MPLCONFIGDIR':str(ROOT/'outputs/tmp/mpl'),
        'PYTHONPATH':os.pathsep.join(map(str,[old/'.upstream_build/redmax',old/'vendor/ASAP',WORKSPACE]))}
    with (folder/'source_certificate.log').open('x') as log:
        try:
            p=subprocess.run([str(old/'.upstream_venv/bin/python'),'-B',str(script),'--source-dir',
                str(ROOT/'data/source/asap_training'/entry['source_assembly_id']),'--case',entry['case_path'],
                '--sequence',str(seq),'--output',str(out),'--direction-frame','source'],stdout=log,stderr=subprocess.STDOUT,env=env,timeout=300)
        except subprocess.TimeoutExpired:return dict(success=False,status='official_capacity_timeout')
    path=out/'certificate.json'
    if not path.exists() or p.returncode:return dict(success=False,status='official_worker_error',returncode=p.returncode)
    value=read(path);return dict(success=value['success'],status=value['status'],receipt=str(path),sha256=sha(path))

def main():
    from .protocol import verify
    from .data_tools.range_zip import extract_assembly
    frozen=verify();reserve=read(ROOT/'outputs/input_audit/reserve.json');c=configure();selected=[];statuses=[]
    for aid in reserve['ids']:
        folder=ROOT/'outputs/input_audit/qualification'/aid;receipt=folder/'qualification.json'
        if receipt.exists():
            cached=read(receipt);statuses.append(cached['status_record'])
            if cached.get('case'):selected.append(cached['case'])
            continue
        if len(selected)>=3:
            statuses.append(dict(id=aid,status='not_attempted_after_predeclared_three'));continue
        progress('qualifying_new_source',source_id=aid,admitted=len(selected));folder.mkdir(parents=True,exist_ok=True)
        entry=None;details={};began=time.monotonic()
        try:
            raw=ROOT/'data/source/asap_training'/aid/'source_receipt.json'
            if not raw.exists():extract_assembly(aid)
            row=source_record(aid);write(folder/'source_inventory.json',row,exclusive=True)
            if not row['geometry_eligible']:status='source_geometry_or_prior_product_excluded'
            else:
                metadata=dict(source_archive_url=row['source_archive_url'],source_repository_commit=row['source_repository_commit'],source_group='training_assembly',novelty=row.get('prior_product_geometry_matches'),source_record_path=str(folder/'source_inventory.json'))
                manifest=c.normalize_source(row,sha(folder/'source_inventory.json'),metadata)
                mp=c.ASSEMBLIES/row['case_id']/'manifest.json';parts=c.prepare_assembly(mp);details['parts']=parts
                if any(p['status']!='ready' for p in parts):status='collision_preparation_excluded'
                else:
                    physical=c.screen_case(c.make_case(manifest));details['physics_status']=physical['status']
                    if physical['status']!='physical_valid':status='initial_physics_or_capacity_excluded'
                    else:
                        setup=physical['selected'];cp=ROOT/setup['case_path'];shared=shared_input(cp)
                        sp=folder/'shared.json';write(sp,shared)
                        witness=search(cp,shared);write(folder/'search.json',witness)
                        if not witness['success']:status='no_full_path_in_fixed_reference_budget'
                        else:
                            validated=verify_path(cp,shared,witness['actions']);wp=folder/'verified_path.json';write(wp,validated)
                            entry=dict(case_id=row['case_id'],source_assembly_id=aid,part_count=row['part_count'],case_path=str(cp.resolve()),case_sha256=sha(cp),
                                shared_path=str(sp.resolve()),shared_sha256=sha(sp),reference_path=str(wp.resolve()),reference_sha256=sha(wp),fixture_ids=setup['fixture_ids'],
                                local_verified=True,withheld_reference=True)
                            external=official_certificate(entry,witness['actions'],folder);entry['official']=external;status='locally_qualified'
        except Exception as exc:
            status='qualification_error';details['error']=repr(exc);details['traceback']=traceback.format_exc();entry=None
        row_status=dict(id=aid,status=status,elapsed_seconds=time.monotonic()-began,details=details)
        write(receipt,dict(status_record=row_status,case=entry),exclusive=True);statuses.append(row_status)
        if entry:selected.append(entry)
        write(ROOT/'outputs/input_audit/selection_progress.json',dict(cases=selected,statuses=statuses))
        print(json.dumps(dict(id=aid,status=status,admitted=len(selected))),flush=True)
        verify()
    final=dict(status='FINITE_RESERVE_COMPLETE',created_utc=utc(),cases=selected,statuses=statuses,requested_cases=3,
        selection_scope='Conditional on finite source/conversion/initial stability and independently verified full local path; bounded DFS selection bias explicit',
        official_ASAP_criteria_separate=True,reference_supplied_to_actors=False,protocol_sha256=sha(ROOT/'outputs/protocol/freeze.json'))
    write(ROOT/'outputs/input_audit/selected_cases.json',final,exclusive=True)
    progress('qualification_complete',admitted=len(selected),finite_reserve=20)

if __name__=='__main__':main()

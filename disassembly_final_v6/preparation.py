"""Restartable preparation with immutable completed receipts and input-only selection."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import copy
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress
from .dataset import extract,pools

class InitialNativeEngineError(RuntimeError):pass

def source_record(split,aid):
    from disassembly_docskills_v1.data_tools.inventory_sources import load_mesh,shape_fingerprint,assembly_fingerprint
    source=extract(split,aid);parts=[];meshes=[];reasons=[]
    for entry in source['members']:
        if not entry['path'].endswith('.obj'):continue
        p=ROOT/entry['path'];mesh=load_mesh(p.read_bytes());meshes.append(mesh)
        count=len(mesh.split(only_watertight=False))
        if not mesh.is_watertight:reasons.append('nonwatertight')
        if count!=1:reasons.append('multiple_components')
        if mesh.volume<=0:reasons.append('nonpositive_volume')
        parts.append(dict(id=p.stem,source_member=entry['member'],raw_relative_path=entry['path'],source_sha256=sha(p),
            source_bytes=p.stat().st_size,shape_fingerprint=shape_fingerprint(mesh),watertight=bool(mesh.is_watertight),
            connected_components=count,volume=float(mesh.volume),bounds=mesh.bounds.tolist()))
    return dict(id=aid,case_id='asap_'+aid,source_assembly_id=aid,source_group=split+'_assembly',
        source_repository_commit='3727e716b57e0b508c4e9ecd9fefa6953e8f72da',source_archive_url=source['url'],
        part_count=len(parts),parts=parts,geometry_eligible=not reasons,
        geometry_exclusion_reasons=sorted(set(reasons)),assembly_geometry_fingerprint=assembly_fingerprint(meshes))

def configure(stage):
    from .data_tools import convert_cad as c
    cp=ROOT/'outputs/protocol'/('conversion_'+stage+'.json');cfg=read(cp)
    c.CONFIG=copy.deepcopy(cfg);c.COACD_SETTINGS=copy.deepcopy(cfg['coacd'])
    c.ASSEMBLIES=ROOT/'data/assemblies'/stage;c.CASES=ROOT/'cases'/stage
    c.CASES.mkdir(parents=True,exist_ok=True)
    os.environ['DISASSEMBLY_REAL_CONVERSION_CONFIG']=str(cp)
    return c

def worker(stage,aid):
    folder=ROOT/'outputs/input_audit'/stage/aid;folder.mkdir(parents=True,exist_ok=True)
    with (folder/'worker.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        final=folder/'qualification.json'
        if final.exists():return read(final)
        write(folder/'heartbeat.json',dict(utc=utc(),pid=os.getpid(),phase='source'))
        began=time.monotonic();details={};entry=None;signature=None;c=configure(stage)
        try:
            inv=folder/'source_inventory.json'
            if inv.exists():
                record=read(inv)
                for p in record['parts']:assert sha(ROOT/p['raw_relative_path'])==p['source_sha256']
            else:
                record=source_record('training' if stage=='development' else 'test',aid);write(inv,record,exclusive=True)
            signature=record['assembly_geometry_fingerprint']
            if not record['geometry_eligible']:status='source_geometry_excluded'
            else:
                metadata=dict(source_archive_url=record['source_archive_url'],source_repository_commit=record['source_repository_commit'],
                    source_group=record['source_group'],source_record_path=str(inv))
                manifest=c.normalize_source(record,sha(inv),metadata)
                write(folder/'heartbeat.json',dict(utc=utc(),pid=os.getpid(),phase='collision_preparation'))
                parts=c.prepare_assembly(c.ASSEMBLIES/record['case_id']/'manifest.json');details['parts']=parts
                if any(p['status']!='ready' for p in parts):status='collision_preparation_excluded'
                else:
                    write(folder/'heartbeat.json',dict(utc=utc(),pid=os.getpid(),phase='initial_physics'))
                    physics=c.screen_case(c.make_case(manifest));details['physics_status']=physics['status']
                    if physics['status']!='physical_valid':status='initial_physics_or_capacity_excluded'
                    else:
                        setup=physics['selected'];case=ROOT/setup['case_path']
                        from .native_health import inspect_log
                        selected_trial=ROOT/setup['initial_physics']['trial_case']
                        native=inspect_log(selected_trial.with_suffix('.physics_worker.log'))
                        details['selected_initial_native_health']=native
                        if not native['warning_free_observed']:
                            raise InitialNativeEngineError('Initial state has native solver warnings or an unavailable native log;no planner outcome was queried')
                        from disassembly_docskills_v2.qualification import shared_input
                        shared=shared_input(case);sp=folder/'shared.json'
                        if sp.exists():assert read(sp)==shared
                        else:write(sp,shared,exclusive=True)
                        assert record['part_count']>=(3 if stage=='development' else 11) and len(setup['fixture_ids'])==1
                        entry=dict(case_id=record['case_id'],source_assembly_id=aid,part_count=record['part_count'],
                            required_removals=record['part_count']-1,case_path=str(case),case_sha256=sha(case),shared_path=str(sp),shared_sha256=sha(sp),
                            fixture_ids=setup['fixture_ids'],initial_physics_validated=True,full_path_known_before_evaluation=False,
                            source_inventory_path=str(inv),source_split=record['source_group'],geometry_fingerprint=signature)
                        status='initially_qualified_full_path_unknown'
        except Exception as exc:
            status='initial_native_engine_warning_or_unknown_excluded' if isinstance(exc,InitialNativeEngineError) else 'preparation_error'
            details.update(error=repr(exc),traceback=traceback.format_exc())
        result=dict(status_record=dict(id=aid,status=status,elapsed_seconds=time.monotonic()-began,details=details),
            case=entry,geometry_fingerprint=signature)
        write(final,result,exclusive=True);write(folder/'heartbeat.json',dict(utc=utc(),pid=os.getpid(),phase='finished'))
        return result

def run_one(stage,aid):
    if stage=='development':
        from .prior_preparation import get
        prior=get(aid)
        if prior is not None:return prior
    folder=ROOT/'outputs/input_audit'/stage/aid;folder.mkdir(parents=True,exist_ok=True)
    final=folder/'qualification.json'
    if final.exists():return read(final)
    # A replaced selector can attach to its surviving input worker. The OS lock
    # outlives stale heartbeat files and releases automatically on worker death.
    with (folder/'worker.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        fcntl.flock(lock,fcntl.LOCK_UN)
    if final.exists():return read(final)
    log=folder/('worker_'+str(len(list(folder.glob('worker_*.log')))+1)+'.log')
    with log.open('x') as f:
        result=subprocess.run([sys.executable,'-B','-m','disassembly_final_v6.preparation','worker',stage,aid],
            stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
    if result.returncode or not final.exists():
        raise RuntimeError('Preparation process interrupted; resume incomplete input only: '+str(log))
    return read(final)

def select(stage):
    pool=pools();final=ROOT/'outputs/input_audit'/('selected_'+stage+'.json')
    target=pool[stage+'_target']
    if stage=='evaluation':
        from .protocol import verify
        target=verify()['evaluation_target']
    if final.exists():
        prior=read(final)
        if prior['requested_cases_max']>=target:return prior
        assert stage=='development' and not (ROOT/'outputs/development/new_document/proposal.json').exists()
        history=ROOT/'outputs/input_audit/selection_amendments';history.mkdir(exist_ok=True)
        final.rename(history/f'selected_{stage}_target_{prior["requested_cases_max"]}.json')
    rows=pool[stage+'_candidates'];selected=[];statuses=[];seen=set()
    if stage=='evaluation':
        for r in read(ROOT/'outputs/input_audit/selected_development.json')['cases']:seen.add(r['geometry_fingerprint'])
        for p in (ROOT/'outputs/input_audit/development').glob('*/source_inventory.json'):
            seen.add(read(p)['assembly_geometry_fingerprint'])
        for row in read(ROOT/'outputs/input_audit/previous_geometry_fingerprints.json')['records']:
            seen.add(row['fingerprint'])
        if not target:rows=[]
    # Keep workers busy while draining results strictly in frozen input order.
    # Completion speed cannot select a different cohort. No actor is loaded.
    concurrency=pool['preparation_concurrency']
    cursor=next_submit=0;ready={};surplus=[]
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        active={}
        def submit():
            nonlocal next_submit
            while len(active)<concurrency and next_submit<len(rows) and len(selected)<target:
                index=next_submit;next_submit+=1
                active[executor.submit(run_one,stage,rows[index]['id'])]=index
        submit()
        while active:
            finished,_=wait(active,return_when=FIRST_COMPLETED)
            for future in finished:ready[active.pop(future)]=future.result()
            while cursor in ready and len(selected)<target:
                result=ready.pop(cursor);cursor+=1
                row=copy.deepcopy(result['status_record']);case=result.get('case');signature=result.get('geometry_fingerprint')
                if signature in seen:
                    row['status']='duplicate_product_geometry_excluded';case=None
                if signature:seen.add(signature)
                statuses.append(row)
                if case:selected.append(case)
                write(ROOT/'outputs/input_audit'/('progress_'+stage+'.json'),dict(cases=selected,statuses=statuses))
                print(json.dumps(dict(stage=stage,attempted=len(statuses),qualified=len(selected),target=target)),flush=True)
            progress('preparing_'+stage,attempted=len(statuses),qualified=len(selected),active_ids=[rows[i]['id'] for i in active.values()],completed_out_of_order=len(ready))
            submit()
        surplus=[dict(id=rows[i]['id'],status=result['status_record']['status'],used_for_selection=False) for i,result in sorted(ready.items())]
    value=dict(status='FINITE_COHORT_COMPLETE',utc=utc(),cases=selected,statuses=statuses,
        attempted=len(statuses),source_candidates=len(rows),requested_cases_max=target,
        selection=pool['selection'],no_actor_or_reference_search=True,
        additional_prepared_receipts_unused_for_selection=surplus)
    if stage=='development':
        # Uniformly allocate validation roles by cohort index before query labels.
        # This works for user-amended cohort sizes without inspecting outcomes.
        def is_validation(i):return ((i+1)*pool['validation_target'])//target>(i*pool['validation_target'])//target
        value['discovery_cases']=[c for i,c in enumerate(selected) if not is_validation(i)]
        value['validation_cases']=[c for i,c in enumerate(selected) if is_validation(i)]
    write(final,value,exclusive=True);progress(stage+'_prepared',qualified=len(selected),attempted=len(statuses));return value

def main(stage):
    folder=ROOT/'outputs/input_audit'/stage;folder.mkdir(parents=True,exist_ok=True)
    with (folder/'selector.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        write(folder/'selector_process.json',dict(pid=os.getpid(),utc=utc(),stage=stage))
        return select(stage)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['worker','run']);p.add_argument('stage',choices=['development','evaluation']);p.add_argument('aid',nargs='?');a=p.parse_args()
    worker(a.stage,a.aid) if a.command=='worker' else main(a.stage)

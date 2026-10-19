"""Original CAD qualification without selecting by a successful reference DFS."""
from __future__ import annotations
from pathlib import Path
import copy
import json
import os
import time
import traceback
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress

def configure():
    from .data_tools import convert_cad as c
    path=ROOT/'outputs/protocol/conversion_config.json';cfg=read(path)
    c.CONFIG=copy.deepcopy(cfg);c.COACD_SETTINGS=copy.deepcopy(cfg['coacd'])
    c.ASSEMBLIES=ROOT/'data/assemblies'/cfg['asset_namespace'];c.CASES=ROOT/'cases'/cfg['case_namespace']
    c.CASES.mkdir(parents=True,exist_ok=True)
    os.environ['DISASSEMBLY_REAL_CONVERSION_CONFIG']=str(path)
    return c

def prior_signatures():
    path=ROOT/'outputs/input_audit/prior_signatures.json'
    if path.exists():return read(path)
    signatures={}
    for study in WORKSPACE.glob('disassembly_*'):
        if study==ROOT or not study.is_dir():continue
        for pattern in ['**/*geometry_inventory.json','**/source_inventory.json']:
            for p in (study/'outputs').glob(pattern):
                try:
                    doc=read(p)
                    if isinstance(doc,list):rows=doc
                    elif 'assembly_geometry_fingerprint' in doc:rows=[doc]
                    else:rows=doc.get('all_considered_candidates',doc.get('assemblies',[]))
                    for r in rows:
                        if isinstance(r,dict) and r.get('assembly_geometry_fingerprint'):
                            signatures.setdefault(r['assembly_geometry_fingerprint'],str(p))
                except (ValueError,TypeError):continue
    write(path,signatures,exclusive=True);return signatures

def source_record(aid,prior):
    from disassembly_docskills_v1.data_tools.inventory_sources import load_mesh,shape_fingerprint,assembly_fingerprint
    receipt=read(ROOT/'data/source/asap_training'/aid/'source_receipt.json');parts=[];meshes=[];reasons=[]
    for member in receipt['members']:
        if not member['path'].endswith('.obj'):continue
        p=ROOT/member['path'];assert sha(p)==member['sha256']
        mesh=load_mesh(p.read_bytes());meshes.append(mesh);count=len(mesh.split(only_watertight=False))
        if not mesh.is_watertight:reasons.append('nonwatertight')
        if count!=1:reasons.append('multiple_components')
        if mesh.volume<=0:reasons.append('nonpositive_volume')
        parts.append(dict(id=p.stem,source_member=member['member'],raw_relative_path=member['path'],source_sha256=sha(p),
            source_bytes=p.stat().st_size,shape_fingerprint=shape_fingerprint(mesh),watertight=bool(mesh.is_watertight),
            connected_components=count,volume=float(mesh.volume),bounds=mesh.bounds.tolist()))
    signature=assembly_fingerprint(meshes);matches=[prior[signature]] if signature in prior else []
    return dict(id=aid,case_id='asap_'+aid,source_assembly_id=aid,source_group='training_assembly',
        source_repository_commit='3727e716b57e0b508c4e9ecd9fefa6953e8f72da',source_archive_url=receipt['url'],
        part_count=len(parts),parts=parts,geometry_eligible=not reasons and not matches,
        geometry_exclusion_reasons=sorted(set(reasons)),assembly_geometry_fingerprint=signature,prior_product_geometry_matches=matches)

def shared_input(case):
    from disassembly_real_v3.simulator import FullDisassemblySim
    from disassembly_learning_v3.shared_api import SharedAPI
    from .contracts import LIMITS
    sim=FullDisassemblySim(case,max_checks=LIMITS['max_checks']);api=SharedAPI(sim,max_checks=LIMITS['max_checks'])
    api.checkpoint()
    return dict(state=sim.export_state(),recovery_state=api.export_recovery_state(),observation=api.snapshot())

def main():
    from .protocol import verify
    from .data_tools.range_zip import extract_assembly
    verify();reserve=read(ROOT/'outputs/input_audit/reserve.json');prior=prior_signatures();c=configure()
    selected=[];statuses=[];seen_signatures=set(prior)
    for aid in reserve['ids']:
        if len(selected)>=24:break
        folder=ROOT/'outputs/input_audit/qualification'/aid;folder.mkdir(parents=True,exist_ok=True)
        receipt=folder/'qualification.json'
        if receipt.exists():
            old=read(receipt);statuses.append(old['status_record'])
            if old.get('case'):selected.append(old['case'])
            if old.get('geometry_fingerprint'):seen_signatures.add(old['geometry_fingerprint'])
            continue
        progress('qualifying_large_new_CAD',source_id=aid,qualified=len(selected),attempted=len(statuses))
        began=time.monotonic();entry=None;details={};fingerprint=None
        try:
            if not (ROOT/'data/source/asap_training'/aid/'source_receipt.json').exists():extract_assembly(aid)
            record=source_record(aid,prior);fingerprint=record['assembly_geometry_fingerprint']
            write(folder/'source_inventory.json',record,exclusive=True)
            if fingerprint in seen_signatures:status='duplicate_original_product_geometry_excluded'
            elif not record['geometry_eligible']:status='source_geometry_excluded'
            else:
                seen_signatures.add(fingerprint)
                metadata=dict(source_archive_url=record['source_archive_url'],source_repository_commit=record['source_repository_commit'],
                    source_group='training_assembly',source_record_path=str(folder/'source_inventory.json'))
                manifest=c.normalize_source(record,sha(folder/'source_inventory.json'),metadata)
                mp=c.ASSEMBLIES/record['case_id']/'manifest.json';parts=c.prepare_assembly(mp);details['parts']=parts
                if any(p['status']!='ready' for p in parts):status='collision_preparation_excluded'
                else:
                    physics=c.screen_case(c.make_case(manifest));details['physics_status']=physics['status']
                    if physics['status']!='physical_valid':status='initial_physics_or_capacity_excluded'
                    else:
                        setup=physics['selected'];case=ROOT/setup['case_path'];shared=shared_input(case)
                        sp=folder/'shared.json';write(sp,shared,exclusive=True)
                        assert record['part_count']>=11 and len(setup['fixture_ids'])==1
                        entry=dict(case_id=record['case_id'],source_assembly_id=aid,part_count=record['part_count'],
                            required_removals=record['part_count']-1,case_path=str(case.resolve()),case_sha256=sha(case),
                            shared_path=str(sp.resolve()),shared_sha256=sha(sp),fixture_ids=setup['fixture_ids'],
                            initial_physics_validated=True,full_path_known_before_evaluation=False,
                            reference_path=None,source_inventory_path=str(folder/'source_inventory.json'))
                        status='initially_qualified_full_path_unknown'
        except Exception as exc:
            status='qualification_error';details.update(error=repr(exc),traceback=traceback.format_exc())
        row=dict(id=aid,status=status,elapsed_seconds=time.monotonic()-began,details=details)
        write(receipt,dict(status_record=row,case=entry,geometry_fingerprint=fingerprint),exclusive=True);statuses.append(row)
        if entry:selected.append(entry)
        write(ROOT/'outputs/input_audit/selection_progress.json',dict(cases=selected,statuses=statuses))
        print(json.dumps(dict(id=aid,status=status,qualified=len(selected),elapsed_seconds=row['elapsed_seconds'])),flush=True)
        verify()
    final=dict(status='FINITE_COHORT_COMPLETE',created_utc=utc(),cases=selected,statuses=statuses,
        source_candidates=64,attempted=len(statuses),requested_cases_max=24,
        selection='initial physics only,not successful reference-path selection',no_actor_or_reference_search=True,
        unattempted_ids=[a for a in reserve['ids'] if a not in {r['id'] for r in statuses}],protocol_sha256=sha(ROOT/'outputs/protocol/freeze.json'))
    write(ROOT/'outputs/input_audit/selected_cases.json',final,exclusive=True)
    progress('qualification_complete',qualified=len(selected),attempted=len(statuses),unattempted=len(final['unattempted_ids']))

if __name__=='__main__':main()

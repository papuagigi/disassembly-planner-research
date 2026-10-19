"""Metadata-only reserve, provenance, and reproducible physical failure states."""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress

def reserve():
    from .data_tools.range_zip import index
    path=ROOT/'outputs/input_audit/reserve.json'
    if path.exists():return read(path)
    old=read(WORKSPACE/'disassembly_docskills_v1/outputs/input_audit/reserve.json')
    excluded=set(old['excluded_ids'])|set(old['ids'])
    evidence=[]
    skip={'.git','.venv','node_modules','vendor','source_snapshot','project_build','__pycache__','.upstream_venv','.upstream_build'}
    for folder in sorted(WORKSPACE.glob('disassembly*')):
        if not folder.is_dir() or folder==ROOT:continue
        for parent,dirs,names in os.walk(folder):
            dirs[:]=[d for d in dirs if d not in skip and not (Path(parent)/d).is_symlink()]
            for name in names:
                p=Path(parent)/name
                if p.suffix not in ('.obj','.json'):continue
                ids=re.findall(r'(?:asap_|asap_test/|asap_training/)(\d{5})',str(p))
                if ids:excluded.update(ids)
    groups=defaultdict(list)
    for entry in index().infolist():
        if entry.filename.endswith('.obj'):groups[Path(entry.filename).parent.name].append(entry)
    rows=[]
    for aid,parts in sorted(groups.items()):
        count=len(parts);size=sum(p.file_size for p in parts)
        if aid not in excluded and 11<=count<=20 and 100000<=size<=2000000:
            rows.append(dict(id=aid,part_count=count,obj_bytes=size))
    selected=rows[:64]
    assert len(selected)==64,'The fixed source pool cannot be silently reduced'
    result=dict(created_utc=utc(),stage='METADATA_ONLY_NO_NEW_OBJ_FETCH',ids=[r['id'] for r in selected],rows=selected,
        rule='first64 ascending unused source IDs,11–20 original OBJ components,100k–2M OBJ bytes; at most24 initially valid CADs; no full-path gating',
        excluded_ids=sorted(excluded),metadata_eligible_count=len(rows),raw_geometry_opened=False,
        source_split='official ASAP training_assembly; study-held-out only',central_sha256=sha(ROOT/'data/source/training_zip_central.bin'))
    write(path,result,exclusive=True);print('RESERVE',len(selected),selected[:3],flush=True)
    return result

def failure_states():
    from disassembly_real_v3.simulator import FullDisassemblySim
    from disassembly_learning_v3.shared_api import SharedAPI
    out=ROOT/'outputs/development/failure_seeds';records=[]
    specs=[('support','disassembly_real_v3/outputs/supplementary/trials/asap_00749/normal/repeat_01/B_code_with_library/result.json',11),
           ('interlock','disassembly_docskills_v1/outputs/evaluation/trials/asap_01275/A/result.json',43)]
    for label,relative,number in specs:
        original_path=WORKSPACE/relative;original=read(original_path);case=Path(original['case_path'])
        selected=next(t for t in original['trace'] if t['checker_call']==number)
        assert selected['reason']=='unstable_remainder' and not selected['committed']
        sim=FullDisassemblySim(case,max_checks=120);api=SharedAPI(sim,max_checks=120)
        api.checkpoint()
        # Prefix chosen before new candidate proposal. Both conditions see exactly
        # the same actual accepted removals and failure; no reference future path.
        prefix=[t for t in original['trace'] if t['checker_call']<number and t.get('committed')]
        for t in prefix:
            assert api.remove(t['part_id'],t['direction'])['valid']
            api.checkpoint()
        failure=api.remove(selected['part_id'],selected['direction'])
        assert failure['reason']=='unstable_remainder' and failure['stability']['unstable_parts']
        shared=dict(state=sim.export_state(),recovery_state=api.export_recovery_state(),observation=api.snapshot())
        folder=out/label;folder.mkdir(parents=True,exist_ok=True)
        write(folder/'shared.json',shared,exclusive=True)
        row=dict(label=label,case_path=str(case),source_id=case.stem,source_result=str(original_path),source_sha256=sha(original_path),
            original_checker_call=number,failure=failure,seed_checks=sim.checks,seed_removed=len(sim.actions),
            shared_path=str(folder/'shared.json'),shared_sha256=sha(folder/'shared.json'),
            expected_scope='Previously rejected part becomes stably removable after residual geometry changes; successful future sequence never given to validator')
        write(folder/'receipt.json',row,exclusive=True);records.append(row)
    write(ROOT/'outputs/development/failure_seeds.json',dict(created_utc=utc(),seeds=records),exclusive=True)
    # Evidence is full actual failure feedback, not a provided repair algorithm.
    compact=[]
    for label,relative,number in specs:
        original_path=WORKSPACE/relative;original=read(original_path)
        fields=['checker_call','part_id','direction','valid','committed','reason','blockers','stability','remaining_before','remaining_after','physical_state_key_before']
        compact.append(dict(source=str(original_path),sha256=sha(original_path),
            initial_support_edges=original['initial_observation'].get('support_edges'),
            direction_vectors_world=original['initial_observation'].get('direction_vectors_world'),
            trace=[{k:t.get(k) for k in fields} for t in original['trace']],
            restores=[e for e in original['recovery_state']['events'] if e['operation']=='restore']))
    write(ROOT/'outputs/development/failure_evidence.json',dict(created_utc=utc(),sources=compact,api_exception_target=False),exclusive=True)
    progress('physical_failure_states_reproduced',states=len(records))

def doctor():
    from disassembly_mujoco.agent import CodexCLIProvider
    from .contracts import MODEL,EFFORT
    provider=CodexCLIProvider(ROOT/'outputs/development/connectivity_live',model=MODEL,reasoning_effort=EFFORT,timeout=60)
    response,metadata=provider.probe()
    write(ROOT/'outputs/development/connectivity.json',dict(response=response,metadata=metadata,requested_model=MODEL,reasoning_effort=EFFORT),exclusive=True)
    print('MODEL_PROBE',response,metadata.get('usage'),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['reserve','failure_states','doctor']);a=p.parse_args();globals()[a.command]()

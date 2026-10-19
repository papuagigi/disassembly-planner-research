"""Resume only interrupted input preparation; preserve all prior study bytes."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import time
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress


def main():
    from disassembly_docskills_v2.protocol import verify
    verify()
    old=WORKSPACE/'disassembly_docskills_v2'
    folder=ROOT/'outputs/recovery/00403';folder.mkdir(parents=True,exist_ok=True)
    if (folder/'complete.json').exists():return read(folder/'complete.json')
    cfg=read(old/'outputs/protocol/conversion_config.json')
    cp=ROOT/'outputs/protocol/recovery_config.json'
    if not cp.exists():write(cp,cfg,exclusive=True)
    assert read(cp)==cfg
    os.environ['DISASSEMBLY_REAL_CONVERSION_CONFIG']=str(cp)
    from .data_tools import convert_cad as c
    c.CONFIG=cfg;c.COACD_SETTINGS=cfg['coacd']
    c.ASSEMBLIES=ROOT/'data/assemblies/evaluation';c.CASES=ROOT/'cases/evaluation'
    for rel in ['data/source/asap_training/00403','data/assemblies/evaluation/asap_00403']:
        target=ROOT/rel
        if not target.exists():shutil.copytree(old/rel,target)
    inventory=old/'outputs/input_audit/qualification/00403/source_inventory.json'
    assert (old/'data/assemblies/evaluation/asap_00403/manifest.json').exists()
    complete_parts={}
    for p in (old/'data/assemblies/evaluation/asap_00403/prepared').glob('part_*_result.json'):
        if read(p)['status']=='ready':complete_parts[p.name]=sha(p)
    write(folder/'restart_evidence.json',dict(utc=utc(),
        final_prior_log_utc='2026-10-19T02:02:45.800426+00:00',
        observed_boot_kst='2026-10-19 14:57:06 +09:00',
        no_old_worker_or_supervisor_alive=True,old_process_exit_signal_not_recorded=True,
        external_stop_cause_not_proven=True,
        verified_resume_defects=['source_inventory exclusive-create rejects an existing partial case',
          'orphan part log exclusive-create rejects interrupted conversion',
          'screening receipt was returned as if final instead of replaying completed setup trials',
          'supervisor state lacked a heartbeat/reboot-safe resume'],
        source_inventory_sha256=sha(inventory),completed_parts=complete_parts,
        no_final_actor_episode_started=True),exclusive=not (folder/'restart_evidence.json').exists())
    progress('recovering_interrupted_CAD',case_id='asap_00403',completed_parts_reused=len(complete_parts))
    manifest=c.ASSEMBLIES/'asap_00403/manifest.json';began=time.monotonic()
    parts=c.prepare_assembly(manifest)
    for name,digest in complete_parts.items():
        assert sha(manifest.parent/'prepared'/name)==digest,'Completed part changed instead of reuse'
    receipt=dict(status='INTERRUPTED_PREPARATION_RECOVERED',created_utc=utc(),
        reused_completed_parts=len(complete_parts),parts=parts,wall_seconds=time.monotonic()-began,
        no_model_calls=True,old_protocol_verified=True,
        all_parts_ready=all(p['status']=='ready' for p in parts))
    # A genuine conversion timeout/quality rejection is a finished preparation
    # outcome, not a reason to retry or claim the source is impossible.
    write(folder/'complete.json',receipt,exclusive=True)
    verify();progress('interrupted_CAD_recovery_finished',all_parts_ready=receipt['all_parts_ready'])
    print(json.dumps({k:v for k,v in receipt.items() if k!='parts'}),flush=True)


if __name__=='__main__':main()

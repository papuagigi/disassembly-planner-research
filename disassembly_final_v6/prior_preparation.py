"""Reuse immutable completed input work;never restart a prior planner."""
import fcntl
from pathlib import Path
from .common import ROOT,read,sha,write


def get(aid):
    manifest=read(ROOT/'protocol/prior_preparation.json')
    row=manifest['completed'].get(aid)
    if row:
        p=Path(row['path']);assert sha(p)==row['sha256']
    else:
        pending=manifest['pending'].get(aid)
        if not pending:return None
        folder=Path(pending['folder'])
        # The old input-only worker may finish after its selector was stopped.
        # Wait for its existing lock without creating or modifying any old file.
        with (folder/'worker.lock').open('r') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            fcntl.flock(f,fcntl.LOCK_UN)
        p=folder/'qualification.json'
        if not p.exists():return None
    value=read(p)
    case=value.get('case')
    if case:
        assert sha(case['case_path'])==case['case_sha256']
        assert sha(case['shared_path'])==case['shared_sha256']
    receipt=ROOT/'outputs/input_audit/reused_preparation'/(aid+'.json')
    record=dict(original_path=str(p),original_sha256=sha(p),no_model_calls=True,
                no_prior_file_modified=True,status=value['status_record']['status'])
    if receipt.exists():assert read(receipt)==record
    else:write(receipt,record,exclusive=True)
    return value

"""Run four already-selected development episodes while new inputs prepare.

These are the same planned jobs later reused by collect(),not extra trials.
Final scored A/B/C episodes remain serial and uncontended.
"""
import fcntl
import os
from .common import ROOT,WORKSPACE,read,write,sha,utc
from .dataset import pools
from .cohort import resolved_case
from .capacity import probe
from .final_learning import discovery_job,audit_result
from .driver import run
from .post_status import checkpoint

def main():
    assert read(WORKSPACE/'disassembly_docskills_v3/outputs/pipeline_complete.json')['status']=='COMPLETE'
    assert 'OK' in (ROOT/'outputs/early_regressions.log').read_text()
    lockpath=ROOT/'outputs/development/discovery_collection.lock';lockpath.parent.mkdir(parents=True,exist_ok=True)
    with lockpath.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        rows=[]
        for raw in pools()['reused_discovery_cases']:
            case=resolved_case(raw);assert probe(case)['eligible']
            write(ROOT/'outputs/early_discovery_state.json',dict(utc=utc(),pid=os.getpid(),phase='RUNNING',case=case['case_id'],completed=len(rows),total=4,
                note='Offline discovery overlaps input preparation;not a scored A/B/C timing experiment'))
            result=run(discovery_job(case));folder=ROOT/'outputs/development/full_search'/case['case_id']
            audit=audit_result(folder,case)
            rows.append(dict(case_id=case['case_id'],success=bool(result['success']),checks=result['checker_calls'],
                actual_restores=result.get('recovery_state',{}).get('restore_count',0),result_sha256=sha(folder/'result.json'),audit=audit['status']))
            checkpoint()
        write(ROOT/'outputs/early_discovery_state.json',dict(utc=utc(),pid=os.getpid(),phase='COMPLETE',completed=4,episodes=rows,
            reused_by_main_collection_without_rerun=True))
        checkpoint()

if __name__=='__main__':main()

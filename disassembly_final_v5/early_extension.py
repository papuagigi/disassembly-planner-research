"""The first of three planned new development jobs,not an additional trial."""
import fcntl
import os
from pathlib import Path
from .common import ROOT,read,write,sha,utc
from .dataset import pools
from .cohort import resolved_case
from .capacity import probe
from .final_learning import discovery_job,audit_result
from .driver import run
from .native_health import audit
from .post_status import checkpoint

def main():
    path=ROOT/'outputs/development/discovery_collection.lock';path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        case=resolved_case(pools()['prequalified_additional_cases'][0])
        assert probe(case)['eligible']
        write(ROOT/'outputs/early_discovery_state.json',dict(utc=utc(),pid=os.getpid(),phase='RUNNING',
            case=case['case_id'],planned_new_development_index=1,total_new_development=3,
            scope='Offline learning may overlap input preparation;not a final timing comparison. Main collection reuses this result without rerun.'))
        result=run(discovery_job(case));folder=ROOT/'outputs/development/full_search'/case['case_id']
        physical=audit_result(folder,case);health=audit(folder)
        write(ROOT/'outputs/early_discovery_state.json',dict(utc=utc(),pid=os.getpid(),phase='COMPLETE',case=case['case_id'],
            raw_success=bool(result['success']),result_sha256=sha(folder/'result.json'),replay=physical['status'],
            native_engine_health=health['status'],reused_by_main_without_rerun=True))
        checkpoint()

if __name__=='__main__':main()

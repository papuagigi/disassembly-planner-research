"""Collect the remaining planned training prefix while validation inputs prepare.

No new trial,selection rule,actor or budget. Main collection reuses results.
Never run this helper for validation or final test episodes.
"""
import fcntl
import os
import sys
import traceback
from .common import ROOT,read,write,sha,utc
from .scope import study_scope
from .cohort import resolved_case
from .capacity import probe
from .final_learning import discovery_job,audit_result
from .driver import run
from .native_health import audit
from .post_native_classify import failure_class
from .post_status import checkpoint


def planned_prefix():
    scope=study_scope()
    assert scope['new_discovery_CADs']==3
    progress=read(ROOT/'outputs/input_audit/progress_development.json')
    prefix=[resolved_case(c) for c in progress['cases'][:3]]
    assert len(prefix)==3 and prefix[0]['case_id']=='asap_05459'
    assert len({c['case_id'] for c in prefix})==3
    assert all(11<=c['part_count']<=20 and c['source_split']=='training_assembly' for c in prefix)
    final=ROOT/'outputs/input_audit/selected_development.json'
    if final.exists():
        assigned=read(final)['discovery_cases'][scope['reused_discovery_CADs']:]
        assert [c['case_id'] for c in prefix]==[c['case_id'] for c in assigned]
    for c in prefix:
        assert sha(c['case_path'])==c['case_sha256'] and sha(c['shared_path'])==c['shared_sha256']
        assert probe(c)['eligible']
    return prefix


def main():
    prefix=planned_prefix()
    if '--check-only' in sys.argv:
        print({'planned_training_prefix':[c['case_id'] for c in prefix],'new_model_calls':0})
        return
    state=ROOT/'outputs/early_remaining_state.json'
    lock=ROOT/'outputs/development/discovery_collection.lock'
    rows=[]
    try:
        with lock.open('a+') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            for case in prefix[1:]:
                write(state,dict(utc=utc(),pid=os.getpid(),phase='RUNNING',case=case['case_id'],
                    assigned_training_prefix=[c['case_id'] for c in prefix],completed=rows,
                    no_extra_trials=True,offline_training_overlap_only=True))
                result=run(discovery_job(case))
                folder=ROOT/'outputs/development/full_search'/case['case_id']
                physical=audit_result(folder,case);health=audit(folder)
                rows.append(dict(case_id=case['case_id'],raw_success=bool(result['success']),
                    observed_failure_class=failure_class(result,health,folder/'worker.log'),
                    result_sha256=sha(folder/'result.json'),replay_status=physical['status'],
                    native_engine_health=health['status'],reused_by_main_without_rerun=True))
                checkpoint()
            write(state,dict(utc=utc(),pid=os.getpid(),phase='COMPLETE',completed=rows,
                no_extra_trials=True,reused_by_main_without_rerun=True))
        checkpoint()
    except BaseException as exc:
        write(state,dict(utc=utc(),pid=os.getpid(),phase='STOPPED_WITH_RECORDED_ERROR',
            error=repr(exc),traceback=traceback.format_exc(),completed=rows))
        raise


if __name__=='__main__':
    main()

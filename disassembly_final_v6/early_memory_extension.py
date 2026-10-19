"""Exactly two authorized additional training episodes;never a test retry."""
import os
import traceback
from .common import ROOT,read,write,utc
from .capacity import probe
from .final_learning import memory_cases,collect_memory_extension


def main():
    state=ROOT/'outputs/memory_extension_state.json'
    try:
        cases=memory_cases()
        assert [c['case_id'] for c in cases]==['asap_05459','asap_01613']
        for c in cases:assert probe(c)['eligible']
        write(state,dict(utc=utc(),pid=os.getpid(),status='RUNNING',
            case_ids=[c['case_id'] for c in cases],planner_concurrency=1,
            budget_change='Only1GiB→4GiBRSS;600checks/900s/8calls retained from these development jobs'))
        rows=collect_memory_extension()
        write(state,dict(utc=utc(),pid=os.getpid(),status='COMPLETE',episodes=rows,
            planner_concurrency=1,main_collector_reuses_without_rerun=True))
    except BaseException as exc:
        write(state,dict(utc=utc(),pid=os.getpid(),status='STOPPED_WITH_RECORDED_ERROR',error=repr(exc),traceback=traceback.format_exc()))
        raise


if __name__=='__main__':main()

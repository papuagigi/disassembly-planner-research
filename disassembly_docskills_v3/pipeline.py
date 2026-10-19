"""Finite, restart-aware research pipeline; not a recurring automation."""
from __future__ import annotations
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import threading
import time
import traceback
from .common import ROOT,read,write,utc

def started(stage):
    write(ROOT/'outputs/pipeline_state.json',dict(utc=utc(),pid=os.getpid(),phase=stage,status='RUNNING'))

def alive(pid,needle):
    if not pid:return False
    result=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
    if 'not permitted' in result.stderr.lower():raise RuntimeError('Cannot verify the existing process;do not start duplicate work')
    return needle in result.stdout

def main(adopt_preparation_pid=None):
    (ROOT/'outputs').mkdir(exist_ok=True)
    with (ROOT/'outputs/pipeline.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        stop=threading.Event()
        def pulse():
            while not stop.wait(10):
                state=read(ROOT/'outputs/pipeline_state.json') if (ROOT/'outputs/pipeline_state.json').exists() else {}
                write(ROOT/'outputs/pipeline_heartbeat.json',dict(utc=utc(),pid=os.getpid(),phase=state.get('phase'),process_owned_heartbeat=True))
        threading.Thread(target=pulse,daemon=True).start()
        try:
            started('development_input_preparation')
            while alive(adopt_preparation_pid,'disassembly_docskills_v3.preparation run development'):
                write(ROOT/'outputs/pipeline_state.json',dict(utc=utc(),pid=os.getpid(),phase='development_input_preparation',status='ATTACHED_TO_EXISTING_SELECTOR',selector_pid=adopt_preparation_pid))
                time.sleep(10)
            from .preparation import main as prepare
            prepare('development')
            started('development_physical_failure_collection')
            from .learning import collect_run,validate_and_freeze
            collect_run()
            started('document_generation_and_independent_validation')
            validate_and_freeze()
            started('freeze_before_new_test_geometry')
            from .protocol import freeze
            freeze()
            started('heldout_input_preparation')
            prepare('evaluation')
            started('matched_first_episode_comparison')
            from .campaign import main as campaign
            campaign()
            started('aggregate_tokens_and_all_outcomes')
            from .post_analysis import main as analyze
            analyze()
            from .post_status import main as status
            status()
            started('independent_mujoco_replays')
            from .post_replay import main as replay
            replay()
            started('verify_previous_artifacts')
            from .preservation import audit
            audit()
            assert read(ROOT/'replay/audit.json')['status']=='PASS','Some replay evidence still needs investigation'
            counts=read(ROOT/'outputs/development/complete.json');bound=read(ROOT/'outputs/evaluation/manifest.json')
            write(ROOT/'outputs/pipeline_complete.json',dict(status='COMPLETE',utc=utc(),no_PPT_changes=True,
                actual_discovery_CADs=counts['actual_new_discovery_CADs'],actual_validation_CADs=counts['actual_new_validation_CADs'],
                actual_test_CADs=len(bound['cases']),minimums=read(ROOT/'outputs/protocol/freeze.json')['minimum_CAD_requirements']))
            write(ROOT/'outputs/pipeline_state.json',dict(status='COMPLETE',utc=utc(),pid=os.getpid()))
        except BaseException as exc:
            write(ROOT/'outputs/pipeline_state.json',dict(status='STOPPED_WITH_RECORDED_ERROR',utc=utc(),pid=os.getpid(),error=repr(exc),traceback=traceback.format_exc()))
            raise
        finally:stop.set()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--adopt-preparation-pid',type=int);a=p.parse_args();main(a.adopt_preparation_pid)

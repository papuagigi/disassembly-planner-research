"""Finite final study;no recurring automation and no favorable-result loop."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
from .common import ROOT,WORKSPACE,read,write,utc

def stage(name):
    write(ROOT/'outputs/pipeline_state.json',dict(utc=utc(),pid=os.getpid(),status='RUNNING',phase=name))
    from .post_status import checkpoint
    checkpoint()

def wait_for_prior(filename):
    prior=WORKSPACE/'disassembly_docskills_v3'
    if not (prior/'outputs/pipeline_state.json').exists():return
    while not (prior/'outputs'/filename).exists():
        state=read(prior/'outputs/pipeline_state.json')
        if state.get('status')=='STOPPED_WITH_RECORDED_ERROR':raise RuntimeError('Earlier v3 study needs recovery before new timed work: '+str(state.get('error')))
        time.sleep(10)

def publish():
    script=WORKSPACE/'collaboration_tools/publish_snapshot.py'
    if script.exists():
        p=subprocess.run([sys.executable,'-B',str(script)],capture_output=True,text=True)
        write(ROOT/'outputs/github_publish_latest.json',dict(utc=utc(),returncode=p.returncode,stdout=p.stdout[-2000:],stderr=p.stderr[-1000:]))

def main():
    from .bootstrap import configure
    configure()
    (ROOT/'outputs').mkdir(exist_ok=True)
    with (ROOT/'outputs/pipeline.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        stop=threading.Event()
        def pulse():
            while not stop.wait(10):write(ROOT/'outputs/heartbeat.json',dict(utc=utc(),pid=os.getpid(),state=read(ROOT/'outputs/pipeline_state.json')))
        threading.Thread(target=pulse,daemon=True).start()
        try:
            stage('waiting_for_prior_frozen_evaluation');wait_for_prior('evaluation/complete.json')
            stage('prepare_development_inputs')
            from .cohort import select
            select('development')
            stage('waiting_for_prior_replays_and_integrity');wait_for_prior('pipeline_complete.json')
            stage('verify_regressions_before_new_learning')
            with (ROOT/'outputs/regressions.log').open('w') as f:
                p=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],stdout=f,stderr=subprocess.STDOUT)
            assert p.returncode==0,'Regression failure;no new model calls'
            from .final_learning import collect,validate_and_freeze_bank
            stage('full_search_learning');collect();publish()
            stage('single_proposal_and_independent_validation');validate_and_freeze_bank();publish()
            stage('freeze_before_final_test')
            from .protocol import freeze
            freeze()
            stage('prepare_unseen_test_inputs');select('evaluation');publish()
            stage('matched_final_first_episodes')
            from .campaign import main as campaign
            campaign()
            stage('aggregate_outcomes_and_tokens')
            from .post_analysis import main as analyze
            analyze()
            stage('independent_mujoco_replays')
            from .post_replay import main as replay
            replay()
            assert read(ROOT/'replay/audit.json')['status']=='PASS'
            stage('final_handoff')
            from .post_finish import main as finish
            finish()
            write(ROOT/'outputs/pipeline_complete.json',dict(status='COMPLETE',utc=utc(),development=read(ROOT/'outputs/development/complete.json'),
                test_CADs=len(read(ROOT/'outputs/evaluation/manifest.json')['cases']),
                test_episodes=read(ROOT/'outputs/evaluation/manifest.json')['planned_episodes'],replay_verified=True,PPT_waits_for_user_review=True))
            write(ROOT/'outputs/pipeline_state.json',dict(status='COMPLETE',utc=utc(),pid=os.getpid()))
            from .post_status import main as status
            status();publish()
        except BaseException as e:
            write(ROOT/'outputs/pipeline_state.json',dict(status='STOPPED_WITH_RECORDED_ERROR',utc=utc(),pid=os.getpid(),error=repr(e),traceback=traceback.format_exc()))
            from .post_status import main as status
            status();publish();raise
        finally:stop.set()

if __name__=='__main__':main()

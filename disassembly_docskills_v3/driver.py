"""One isolated process per episode; no silent reruns of started first episodes."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from .common import ROOT,read,write,sha,utc

def finalize_interrupted(job,returncode=None,elapsed=0.):
    """Retain an already-started first episode; never replace it with a retry."""
    from .metrics import summarize
    folder=Path(job['folder']);result=folder/'result.json'
    if result.exists():return read(result)
    retained=read(folder/'progress.json') if (folder/'progress.json').exists() else {}
    shared=read(job['shared_path']) if job.get('shared_path') else {};case=read(job['case_path'])
    defaults=dict(case_id=case['id'],case_path=job['case_path'],architecture=job['architecture'],limits=job['limits'],
        state=shared.get('state',{}),recovery_state=shared.get('recovery_state',{}),
        initial_observation=shared.get('observation',{}),observation=shared.get('observation',{}),
        trace=shared.get('state',{}).get('trace',[]),actions=shared.get('state',{}).get('actions',[]),
        checker_calls=shared.get('state',{}).get('checks',0),llm_calls=len(list((folder/'llm_calls').glob('call_*'))),
        decisions=[],document_reads=[],loaded_skill_ids=[],token_usage={},execution_steps=0,
        elapsed_seconds=elapsed,error=dict(type='WorkerFailure',message='Worker stopped before final result;retained initial/progress evidence only'),
        total_part_count=len(case['parts']),required_removals=len(case['parts'])-1,
        completed_removals=len(shared.get('state',{}).get('actions',[])),learning_updates=0,
        model='gpt-6-luna',reasoning_effort='low',protocol_sha256=job.get('protocol_sha256'))
    for k,v in defaults.items():retained.setdefault(k,v)
    retained.update(success=False,termination='episode_worker_failed_or_hard_timeout',condition=job['arm'],
        phase=job['phase'],worker_returncode=returncode,first_encounter=job['phase']=='evaluation',
        interrupted_episode_retained_without_retry=True)
    write(result,retained,exclusive=True);write(folder/'metrics.json',summarize(retained),exclusive=True)
    write(folder/'lifecycle_final.json',dict(utc=utc(),status='INTERRUPTED_FIRST_EPISODE_FINALIZED_WITHOUT_RETRY',returncode=returncode),exclusive=True)
    return retained

def matching_worker_alive(folder,job_path):
    lifecycle=folder/'lifecycle_started.json'
    if not lifecycle.exists():return False
    pid=read(lifecycle)['pid']
    result=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
    if 'not permitted' in result.stderr.lower():raise RuntimeError('Cannot inspect prior worker;do not duplicate this episode')
    return 'disassembly_docskills_v3.driver worker' in result.stdout and str(job_path) in result.stdout

def worker(job_path):
    from .actors import solve
    from .metrics import summarize
    from disassembly_mujoco.agent import CodexCLIProvider
    from .contracts import MODEL,EFFORT
    job=read(job_path);folder=Path(job['folder']);limits=job['limits']
    def deadline(sig,frame):
        from .actors import LimitError
        raise LimitError('whole_episode_wall_deadline')
    signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,limits['timeout_seconds'])
    provider=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    try:
        result=solve(job['case_path'],provider,job['bank_path'],job['architecture'],
            shared=read(job['shared_path']) if job.get('shared_path') else None,
            limits=limits,progress_path=folder/'progress.json',public_task_note=job.get('public_task_note'))
    finally:signal.setitimer(signal.ITIMER_REAL,0)
    result.update(condition=job['arm'],model=MODEL,reasoning_effort=EFFORT,
        phase=job['phase'],first_encounter=job['phase']=='evaluation',case_sha256=sha(job['case_path']),
        protocol_sha256=job.get('protocol_sha256'),normal_initialization=True,repeat=1)
    write(folder/'result.json',result,exclusive=True);write(folder/'metrics.json',summarize(result),exclusive=True)

def run(job):
    folder=Path(job['folder']).resolve();folder.relative_to(ROOT);folder.mkdir(parents=True,exist_ok=True)
    result=folder/'result.json'
    if result.exists():return read(result)
    job_path=folder/'job.json'
    if job_path.exists():
        saved=read(job_path)
        for key in ['case_path','shared_path','architecture','bank_path','limits','arm','phase','protocol_sha256']:
            assert saved.get(key)==job.get(key),('Started job contract changed',key)
        if matching_worker_alive(folder,job_path):raise RuntimeError('The existing first-episode worker is still live;never start a duplicate')
        return finalize_interrupted(saved)
    job={**job,'folder':str(folder),'created_utc':utc()};write(job_path,job,exclusive=True)
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'};worker_started=time.monotonic()
    with (folder/'worker.log').open('x') as f:
        process=subprocess.Popen([sys.executable,'-B','-m','disassembly_docskills_v3.driver','worker',str(job_path)],env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        write(folder/'lifecycle_started.json',dict(utc=utc(),pid=process.pid,job_path=str(job_path),no_retry=True),exclusive=True)
        try:rc=process.wait(timeout=job['limits']['timeout_seconds']+20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);rc=process.wait()
    if not result.exists():
        finalize_interrupted(job,rc,time.monotonic()-worker_started)
    elif not (folder/'lifecycle_final.json').exists():
        write(folder/'lifecycle_final.json',dict(utc=utc(),status='FINISHED',returncode=rc),exclusive=True)
    value=read(result)
    print(json.dumps(dict(folder=str(folder.relative_to(ROOT)),success=value['success'],termination=value['termination'],checks=value.get('checker_calls'),calls=value.get('llm_calls'))),flush=True)
    return value

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['worker','run']);p.add_argument('job');a=p.parse_args()
    worker(a.job) if a.command=='worker' else run(read(a.job))

"""One isolated process per v7 episode; a started episode is never rerun.

Adapted from disassembly_final_v6/driver.py: same provider (CodexCLIProvider,
explicit gpt-6-luna / low), same SIGALRM whole-episode deadline, same
finalize-without-retry rule. The Codex CLI executable directory is put on PATH
explicitly because it is not on the login PATH of this machine.
"""
from __future__ import annotations
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .common import ROOT, WORKSPACE, read, write, sha, utc

CODEX_DIR = '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS'


def finalize_interrupted(job, returncode=None, elapsed=0.):
    from .metrics import summarize
    folder = Path(job['folder'])
    result = folder / 'result.json'
    if result.exists():
        return read(result)
    retained = read(folder / 'progress.json') if (folder / 'progress.json').exists() else {}
    shared = read(job['shared_path']) if job.get('shared_path') else {}
    case = read(job['case_path'])
    defaults = dict(case_id=case['id'], case_path=job['case_path'], architecture=job['architecture'], limits=job['limits'],
                    state=shared.get('state', {}), recovery_state=shared.get('recovery_state', {}),
                    trace=shared.get('state', {}).get('trace', []), actions=shared.get('state', {}).get('actions', []),
                    checker_calls=shared.get('state', {}).get('checks', 0), llm_calls=len(list((folder / 'llm_calls').glob('call_*'))),
                    decisions=[], document_reads=[], token_usage={}, elapsed_seconds=elapsed,
                    error=dict(type='WorkerFailure', message='Worker stopped before final result; progress evidence retained'),
                    total_part_count=len(case['parts']), required_removals=len(case['parts']) - 1)
    for k, v in defaults.items():
        retained.setdefault(k, v)
    retained.update(success=False, termination='episode_worker_failed_or_hard_timeout', condition=job['arm'], phase=job['phase'],
                    worker_returncode=returncode, interrupted_episode_retained_without_retry=True, model='gpt-6-luna', reasoning_effort='low')
    write(result, retained, exclusive=True)
    write(folder / 'metrics.json', summarize(retained), exclusive=True)
    write(folder / 'lifecycle_final.json', dict(utc=utc(), status='INTERRUPTED_EPISODE_FINALIZED_WITHOUT_RETRY', returncode=returncode), exclusive=True)
    return retained


def worker(job_path):
    os.environ['PATH'] = CODEX_DIR + os.pathsep + os.environ.get('PATH', '')
    sys.path.insert(0, str(WORKSPACE / 'disassembly_planner_2d'))
    from planner2d.llm import CodexCLIProvider
    from .actors import solve, LimitError
    from .metrics import summarize
    from .contracts import MODEL, EFFORT
    job = read(job_path)
    folder = Path(job['folder'])
    limits = job['limits']

    def deadline(sig, frame):
        raise LimitError('whole_episode_wall_deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, limits['timeout_seconds'])
    provider = CodexCLIProvider(folder / 'llm_calls', model=MODEL, reasoning_effort=EFFORT, timeout=120)
    try:
        result = solve(job['case_path'], provider, job['bank_path'], job['architecture'], shared=read(job['shared_path']),
                       limits=limits, progress_path=folder / 'progress.json',
                       physics_variant=job.get('physics_variant'))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    result.update(condition=job['arm'], model=MODEL, reasoning_effort=EFFORT, phase=job['phase'],
                  first_encounter=job['phase'] == 'pilot', case_sha256=sha(job['case_path']),
                  protocol_sha256=job.get('protocol_sha256'), provider_executable=provider.executable)
    write(folder / 'result.json', result, exclusive=True)
    write(folder / 'metrics.json', summarize(result), exclusive=True)


def run(job):
    folder = Path(job['folder']).resolve()
    folder.relative_to(ROOT)
    folder.mkdir(parents=True, exist_ok=True)
    result = folder / 'result.json'
    if result.exists():
        return read(result)
    job_path = folder / 'job.json'
    if job_path.exists():
        saved = read(job_path)
        for key in ['case_path', 'shared_path', 'architecture', 'bank_path', 'limits', 'arm', 'phase', 'protocol_sha256', 'physics_variant']:
            assert saved.get(key) == job.get(key), ('Started job contract changed', key)
        return finalize_interrupted(saved)  # never rerun a started first episode
    job = {**job, 'folder': str(folder), 'created_utc': utc()}
    write(job_path, job, exclusive=True)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}
    started = time.monotonic()
    with (folder / 'worker.log').open('x') as f:
        process = subprocess.Popen([sys.executable, '-B', '-m', 'disassembly_repair_v7.driver', 'worker', str(job_path)], env=env,
                                   stdout=f, stderr=subprocess.STDOUT, start_new_session=True, cwd=str(WORKSPACE))
        write(folder / 'lifecycle_started.json', dict(utc=utc(), pid=process.pid, job_path=str(job_path), no_retry=True), exclusive=True)
        try:
            rc = process.wait(timeout=job['limits']['timeout_seconds'] + 20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            rc = process.wait()
    if not result.exists():
        finalize_interrupted(job, rc, time.monotonic() - started)
    elif not (folder / 'lifecycle_final.json').exists():
        write(folder / 'lifecycle_final.json', dict(utc=utc(), status='FINISHED', returncode=rc), exclusive=True)
    value = read(result)
    print(json.dumps(dict(folder=str(folder.relative_to(ROOT)), success=value['success'], termination=value['termination'],
                          checks=value.get('checker_calls'), calls=value.get('llm_calls'))), flush=True)
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['worker', 'run'])
    p.add_argument('job')
    a = p.parse_args()
    worker(a.job) if a.command == 'worker' else run(read(a.job))

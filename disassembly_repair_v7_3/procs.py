"""Process hygiene (v7.2).

v7.1 left 19 orphaned `multiprocessing.spawn` workers after stopping search parents
with pkill; the campaign guard matched module names only and could not see them.
Here every background search runs in its own session (process group) and is
stopped by killing the whole group, and the guard lists any python process that
belongs to this project's work, including spawn workers.
"""
from __future__ import annotations
import os
import signal
import subprocess
import sys

PATTERNS = ('spawn_main', 'multiprocessing.spawn', 'disassembly_repair_v7.', 'disassembly_repair_v7_2.', 'disassembly_repair_v7_3.',
            'disassembly_final_v6.pipeline', 'disassembly_final_v6.driver')


def project_processes(exclude_pids=()):
    out = subprocess.run(['ps', '-axo', 'pid=,ppid=,command='], capture_output=True, text=True).stdout
    me = {os.getpid(), os.getppid(), *exclude_pids}
    rows = []
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        pid, ppid, cmd = int(parts[0]), int(parts[1]), parts[2]
        if pid in me or 'ps -axo' in cmd:
            continue
        if 'python' in cmd and any(p in cmd for p in PATTERNS):
            rows.append(dict(pid=pid, ppid=ppid, command=cmd[-160:]))
    return rows


def start_group(cmd, log_path, env=None, cwd=None):
    """Start a detached command in its own process group; returns the group leader pid."""
    log = open(log_path, 'a')
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env, cwd=cwd)
    return proc.pid


def kill_group(pid, sig=signal.SIGTERM):
    try:
        os.killpg(pid, sig)
        return True
    except ProcessLookupError:
        return False


if __name__ == '__main__':
    rows = project_processes()
    for r in rows:
        print(r)
    if '--kill-orphans' in sys.argv:
        for r in rows:
            if r['ppid'] == 1:
                os.kill(r['pid'], signal.SIGTERM)

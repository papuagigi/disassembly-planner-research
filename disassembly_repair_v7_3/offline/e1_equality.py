"""E1 acceptance: replay every recorded v7.1 pilot and v7.2 episode with the threaded winding installed.

usage: python -m disassembly_repair_v7_3.offline.e1_equality [workers]
v7.1 episodes use the v7 verifier (no rejection cache, as they were run); v7.2 episodes use
the v7.2-compatible verifier copied into v7.3. Both assert identical trace fields, state keys
and charged checks. Writes outputs/e1/equality.json; E1 is accepted only if every row PASSes.
"""
from __future__ import annotations
import concurrent.futures as cf
import glob
import multiprocessing as mp
import sys
import time

from ..common import ROOT, V7, V72, read, write, utc


def one(row):
    kind, result_path, shared_path = row
    from ..fast_geometry import install
    started = time.monotonic()
    try:
        if kind == 'v7.1':
            install()   # the v7 verifier applies physics itself; E1 only swaps the winding function
            from disassembly_repair_v7.replay_verify import replay_result
        else:
            from ..replay_verify import replay_result
        rec = replay_result(result_path, shared_path=shared_path, capture=False, allow_incomplete=True)[0]
        return dict(kind=kind, result=result_path, status=rec['status'], physical_queries_replayed=rec['physical_queries_replayed'],
                    seconds=round(time.monotonic() - started, 1))
    except Exception as exc:
        return dict(kind=kind, result=result_path, status='FAIL', error=repr(exc)[:1500], seconds=round(time.monotonic() - started, 1))


def rows():
    out = []
    for job in sorted(glob.glob(str(V7 / 'outputs/pilot/trials/*/*/job.json'))):
        out.append(('v7.1', job.replace('job.json', 'result.json'), read(job)['shared_path']))
    for stage in ('collection', 'validation', 'retry'):
        for job in sorted(glob.glob(str(V72 / 'outputs' / stage / '*/*/job.json'))):
            out.append(('v7.2', job.replace('job.json', 'result.json'), read(job)['shared_path']))
    return out


def main(workers=3):
    todo = rows()
    with cf.ProcessPoolExecutor(workers, mp_context=mp.get_context('spawn')) as ex:
        done = list(ex.map(one, todo))
    status = 'PASS' if all(r['status'].startswith('PASS') for r in done) else 'FAIL'
    write(ROOT / 'outputs/e1/equality.json', dict(utc=utc(), status=status, episodes=len(done), rows=done,
                                                  rule='E1 accepted only if every recorded v7.1/v7.2 episode replays identically'))
    print(status, len(done), [r for r in done if not r['status'].startswith('PASS')][:5], flush=True)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)

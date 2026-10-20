"""Parallel independent replay audits for v7.2 results (no model call; untimed).

usage: python -m disassembly_repair_v7_2.offline.replay_many OUT.json RESULT1:SHARED1 [RESULT2:SHARED2 ...]
"""
from __future__ import annotations
import concurrent.futures as cf
import multiprocessing as mp
import sys

from ..common import utc, write


def one(pair):
    from ..replay_verify import replay_result
    rp, sp = pair.split('::')
    try:
        rec, _, _ = replay_result(rp, shared_path=sp, capture=False, allow_incomplete=True)
        return dict(result=rp, status=rec['status'], physical_queries_replayed=rec['physical_queries_replayed'],
                    guarded_or_cached_replayed=rec['guarded_requests_replayed'],
                    restores_verified=rec['restores_verified'], charged_unfinished_checks=rec['charged_unfinished_checks'])
    except Exception as exc:
        return dict(result=rp, status='FAIL', error=repr(exc)[:1500])


def main(out, pairs, workers=6):
    with cf.ProcessPoolExecutor(min(workers, len(pairs)), mp_context=mp.get_context('spawn')) as ex:
        rows = list(ex.map(one, pairs))
    write(out, dict(utc=utc(), status='PASS' if all(r['status'].startswith('PASS') for r in rows) else 'FAIL', episodes=rows))
    for r in rows:
        print(r, flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])

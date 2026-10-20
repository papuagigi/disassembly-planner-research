"""v7.2 learning cycle (development only): case registry and failure-collection runs.

Development CADs are KNOWN CADs (fully disassembled in earlier development under
P0, hence feasible under monotone P2). They are never reported as first
encounters. Pilot CADs 06146/05902 are reserved for the retry evaluation and are
not used here.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
from pathlib import Path

from .common import ROOT, WORKSPACE, V6, read, write, utc, sha

PHYSICS = 'P2_persist_up_to_stable_penetration'
DEV_CASES = {
    'asap_01613': 'disassembly_final_v5/cases/development/asap_01613.json',
    'asap_02406': 'disassembly_docskills_v3/cases/development/asap_02406.json',
    'asap_03674': 'disassembly_docskills_v3/cases/development/asap_03674.json',
    'asap_07375': 'disassembly_final_v4/cases/development/asap_07375.json',
    'asap_05459': 'disassembly_final_v4/cases/development/asap_05459.json',
    'asap_02402': 'disassembly_docskills_v3/cases/development/asap_02402.json',
}
COLLECTION = ('asap_01613', 'asap_02406', 'asap_03674', 'asap_07375')
VALIDATION = ('asap_05459', 'asap_02402')
BANKS = {'S0': V6 / 'memory/S0.json', 'S3': V6 / 'memory/S3.json'}


def case(cid):
    path = WORKSPACE / DEV_CASES[cid]
    shared = ROOT / 'outputs/cases' / cid / 'shared.json'
    if not shared.exists():
        from disassembly_repair_v7.pilot_inputs import shared_input
        write(shared, shared_input(path), exclusive=True)
    return dict(case_id=cid, case_path=str(path), shared_path=str(shared), case_sha256=sha(path), shared_sha256=sha(shared))


def job(cid, arm, bank, phase, folder, limits=None, physics=PHYSICS, note=None):
    from .contracts import LIMITS, ARMS
    c = case(cid)
    return dict(folder=str(folder), case_path=c['case_path'], shared_path=c['shared_path'],
                architecture=ARMS[arm]['architecture'], bank_path=str(bank), limits=limits or LIMITS,
                phase=phase, arm=arm, protocol_sha256=None, physics_variant=physics)


def collect(arms, cases, workers=2):
    """Development failure collection: A with S0, B/C with the current S3 bank. Two episodes run concurrently."""
    from .driver import run
    jobs = []
    for cid in cases:
        for arm in arms:
            bank = BANKS['S0'] if arm == 'A' else BANKS['S3']
            jobs.append(job(cid, arm, bank, 'collection', ROOT / 'outputs/collection' / cid / arm))
    write(ROOT / ('outputs/collection/plan_' + ''.join(arms) + '.json'),
          dict(utc=utc(), jobs=[{k: j[k] for k in ('folder', 'arm', 'bank_path', 'phase')} for j in jobs], workers=workers,
               note='Development only; concurrent runs share CPU, so wall-time pressure differs from sequential evaluation.'))
    with cf.ThreadPoolExecutor(workers) as ex:
        for r in ex.map(run, jobs):
            pass


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['collect'])
    p.add_argument('--arms', default='AB')
    p.add_argument('--workers', type=int, default=2)
    a = p.parse_args()
    collect(tuple(a.arms), COLLECTION, a.workers)

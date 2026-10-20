"""Independent replays of every finished validation and retry episode (run only when no timed episode is running).

usage: python -m disassembly_repair_v7_3.offline.replay_all [workers] [validation evaluation]
Writes outputs/replay/<stage>.json via replay_many (no model call).
"""
from __future__ import annotations
import sys

from ..common import ROOT, read
from .replay_many import main as replay_many


def pairs(stage):
    out = []
    for job in sorted((ROOT / 'outputs' / stage).glob('*/*/job.json')):
        result = job.parent / 'result.json'
        if result.exists():
            out.append(f"{result}::{read(job)['shared_path']}")
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    workers = int(args.pop(0)) if args and args[0].isdigit() else 6
    for stage in args or ['validation', 'evaluation']:
        p = pairs(stage)
        if p:
            replay_many(str(ROOT / 'outputs/replay' / f'{stage}.json'), p, workers=workers)

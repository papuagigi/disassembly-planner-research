"""Verify that the completed v6 baseline and its dependencies are byte-identical.

Run before and after any v7 step:  python -B -m disassembly_repair_v7.protect
"""
from __future__ import annotations
import sys
from .common import HANDOFF, WORKSPACE, ROOT, read, sha, utc, write


def verify(record=True):
    expected = read(HANDOFF / 'evidence.json')['protected_sha256']
    mismatches = []
    for rel, value in expected.items():
        path = WORKSPACE / rel
        if not path.exists():
            mismatches.append(dict(path=rel, problem='missing'))
        elif sha(path) != value:
            mismatches.append(dict(path=rel, problem='sha256_changed'))
    result = dict(utc=utc(), checked=len(expected), mismatches=mismatches,
                  status='PASS' if not mismatches else 'FAIL',
                  source='claude_repair_handoff/evidence.json protected_sha256')
    if record:
        write(ROOT / 'outputs/protection_check_latest.json', result)
    return result


if __name__ == '__main__':
    r = verify()
    print(r['status'], r['checked'], r['mismatches'])
    sys.exit(0 if r['status'] == 'PASS' else 1)

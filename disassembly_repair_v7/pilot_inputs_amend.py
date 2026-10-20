"""Selection amendment A1 (2026-10-20, before any pilot episode; no planner outcome involved).

Event: candidate 06186 passed the v6 qualification, then its P2 reference search
crashed inside MuJoCo (`mj_stackAlloc: out of memory, stack overflow at
PrimalAllocate`, ncon=5499) after 966 checks. The frozen selection code had no
rule for a native engine failure and the selector stopped.

Rule: a native MuJoCo engine failure during the v7 physical screen excludes the
candidate as `native_engine_resource_excluded`. This mirrors v6, which excluded
inputs with initial native engine warnings, and the handoff rule that native
resource failures are not physical evidence. `pilot_inputs.py` stays byte-
identical (frozen hash); this wrapper replaces `physical_screen` at runtime only.
"""
from __future__ import annotations
import json

from . import pilot_inputs as pi
from .common import read, utc, write

_original = pi.physical_screen


def _native(exc):
    return type(exc).__module__.startswith('mujoco') or 'mj_' in str(exc) or type(exc).__name__ == 'FatalError'


def guarded_physical_screen(entry):
    marker = pi.INPUTS / entry['source_assembly_id'] / 'native_engine_error.json'
    if marker.exists():
        return 'native_engine_resource_excluded', 'native_engine_error'
    try:
        return _original(entry)
    except Exception as exc:
        if not _native(exc):
            raise
        write(marker, dict(utc=utc(), error_type=type(exc).__name__, error=str(exc)[:2000], amendment='A1',
                           scope='Native engine resource failure during qualification; not physical evidence.'), exclusive=True)
        return 'native_engine_resource_excluded', 'native_engine_error'


pi.physical_screen = guarded_physical_screen

if __name__ == '__main__':
    print(json.dumps({k: v for k, v in pi.select().items() if k != 'statuses'}, ensure_ascii=False)[:2000])

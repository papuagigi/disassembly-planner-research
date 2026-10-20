"""v7.3 paths. Helpers are reused from v7; only ROOT differs (outputs go under disassembly_repair_v7_3)."""
from pathlib import Path

from disassembly_repair_v7.common import (WORKSPACE, V6, HANDOFF, KNOWN_V6_CADS, utc, sha, digest, read, write,  # noqa: F401
                                          v6_trial)

ROOT = Path(__file__).resolve().parent
V7 = WORKSPACE / 'disassembly_repair_v7'
V72 = WORKSPACE / 'disassembly_repair_v7_2'
V7_PILOT_CADS = ('asap_06146', 'asap_03012', 'asap_05902')  # v7.1 pilot CADs: development data from v7.3 on

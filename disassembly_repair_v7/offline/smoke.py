"""Pre-freeze integration smoke test with the real provider on a KNOWN development CAD.

Reduced limits; not a performance result and not a first encounter.
"""
import json
from ..common import ROOT, WORKSPACE, V6, write, read, sha
from ..contracts import LIMITS, ARMS
from ..driver import run
from ..pilot_inputs import shared_input

CASE = WORKSPACE / 'disassembly_final_v5/cases/development/asap_01613.json'


def main():
    out = ROOT / 'outputs/smoke'
    shared = out / 'asap_01613_shared.json'
    if not shared.exists():
        write(shared, shared_input(CASE), exclusive=True)
    limits = {**LIMITS, 'max_calls': 3, 'timeout_seconds': 240.}
    for arm in 'ABC':
        conf = ARMS[arm]
        run(dict(folder=str(out / 'asap_01613' / arm), case_path=str(CASE), shared_path=str(shared),
                 architecture=conf['architecture'], bank_path=str(V6 / 'memory' / (conf['bank'] + '.json')),
                 limits=limits, phase='smoke_known_development_cad', arm=arm, protocol_sha256=None))


if __name__ == '__main__':
    main()

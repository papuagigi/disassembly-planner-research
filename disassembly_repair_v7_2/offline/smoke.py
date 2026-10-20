"""v7.2 integration smoke with the real provider on KNOWN development CAD 01613 (reduced limits; not a result)."""
from ..common import ROOT, WORKSPACE, V6, V7, write, read
from ..contracts import LIMITS, ARMS
from ..driver import run

CASE = WORKSPACE / 'disassembly_final_v5/cases/development/asap_01613.json'
SHARED = V7 / 'outputs/smoke/asap_01613_shared.json'   # same initial state as the v7 smoke


def main():
    out = ROOT / 'outputs/smoke'
    limits = {**LIMITS, 'max_calls': 3, 'timeout_seconds': 240.}
    for arm in 'ABC':
        conf = ARMS[arm]
        run(dict(folder=str(out / 'asap_01613' / arm), case_path=str(CASE), shared_path=str(SHARED),
                 architecture=conf['architecture'], bank_path=str(V6 / 'memory' / (conf['bank'] + '.json')),
                 limits=limits, phase='smoke_known_development_cad', arm=arm, protocol_sha256=None,
                 physics_variant='P2_persist_up_to_stable_penetration'))


if __name__ == '__main__':
    main()

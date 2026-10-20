"""v7.3 integration smoke with the real provider on KNOWN development CAD 02402 (reduced limits; not a result).

Exercises E1 + R7 + contract notes 8-10 end to end for A/B/C, and the note writer v2 on the smoke records."""
from ..common import ROOT, V6
from ..contracts import LIMITS, ARMS
from ..driver import run
from ..learning73 import dev_case, PHYSICS


def main():
    out = ROOT / 'outputs/smoke'
    case = dev_case('asap_02402')
    limits = {**LIMITS, 'max_calls': 3, 'timeout_seconds': 240.}
    for arm in 'ABC':
        conf = ARMS[arm]
        run(dict(folder=str(out / 'asap_02402' / arm), case_path=case['case_path'], shared_path=case['shared_path'],
                 architecture=conf['architecture'], bank_path=str(V6 / 'memory' / (conf['bank'] + '.json')),
                 limits=limits, phase='smoke_known_development_cad', arm=arm, protocol_sha256=None, physics_variant=PHYSICS))
    from ..skill_writer import write_note
    from ..campaign import s3_copy
    write_note('smoke_asap_02402', [out / 'asap_02402' / a / 'result.json' for a in 'ABC'],
               ROOT / 'memory/smoke_note_asap_02402.json', s3_copy())


if __name__ == '__main__':
    main()

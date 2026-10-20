"""Collection results (+ v6 dev traces) -> mining bundle -> S4 bank (at most 2 writer calls)."""
import glob
from pathlib import Path

from ..common import ROOT, WORKSPACE, read, write, utc
from ..mine import mine
from ..skill_writer import write_bank

KNOWN_IDS = ('05954', '06444', '03114', '06146', '03012', '05902', '01613', '02406', '03674', '07375', '05459', '02402',
             '02429', '03756', '04243', '05828', '07385', '07722', '08243', '06186', '03107')


def main():
    paths = sorted(glob.glob(str(ROOT / 'outputs/collection/*/*/result.json')))
    paths += sorted(glob.glob(str(WORKSPACE / 'disassembly_final_v6/outputs/evaluation/trials/*/*/result.json')))
    bundle_path = ROOT / 'outputs/mining/bundle.json'
    mine([Path(p) for p in paths], bundle_path)
    report = None
    for attempt in (1, 2):
        if (ROOT / 'memory/S4.json').exists():
            break
        report = write_bank(bundle_path, version='S4', forbidden_ids=KNOWN_IDS)
        print('writer attempt', attempt, report['gate'], flush=True)
    write(ROOT / 'outputs/mining/make_s4.json', dict(utc=utc(), inputs=paths, bank_exists=(ROOT / 'memory/S4.json').exists(),
                                                     last_report=report))


if __name__ == '__main__':
    main()

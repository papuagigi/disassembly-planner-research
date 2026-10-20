"""Development-only S5 refinement (<= 2 more writer calls with model-free gate feedback)."""
from ..common import ROOT, read
from ..skill_writer import refine_s5
from disassembly_repair_v7_2.offline.make_s4 import KNOWN_IDS


def main():
    extra = tuple(c['id'] for c in read(ROOT / 'outputs/protocol/selection_candidates.json')['candidates'])
    best, refinements = refine_s5(ROOT / 'outputs/mining/bundle_s5.json', KNOWN_IDS + extra)
    for h in refinements:
        g = h.get('gate') or {}
        print('call', h['call'], 'problems', h['problems'][:3], 'gate', g.get('successes'),
              [(r['case_id'], r['success'], r['removed'], r['checks'], r.get('ended')) for r in g.get('rows', [])], flush=True)
    print('adopted', best['call'], flush=True)


if __name__ == '__main__':
    main()

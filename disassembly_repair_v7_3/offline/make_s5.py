"""Development evidence -> S5 SKILL.md (writer gpt-6-luna/low, <= 3 calls, model-free rule gate between calls)."""
from ..common import ROOT, read
from ..mine73 import build
from ..skill_writer import write_s5
from disassembly_repair_v7_2.offline.make_s4 import KNOWN_IDS


def main():
    path = ROOT / 'outputs/mining/bundle_s5.json'
    if not path.exists():
        build(path)
    selected = ROOT / 'outputs/protocol/selection_candidates.json'
    extra = tuple(c['id'] for c in read(selected)['candidates']) if selected.exists() else ()
    chosen, history = write_s5(path, forbidden_ids=KNOWN_IDS + extra)
    for h in history:
        g = h.get('gate') or {}
        print('call', h['call'], 'problems', h['problems'][:3], 'gate', g.get('successes'),
              [(r['case_id'], r['success'], r['removed'], r['checks'], (r['error'] or {}).get('type')) for r in g.get('rows', [])], flush=True)
    print('chosen', chosen and chosen['call'], flush=True)


if __name__ == '__main__':
    main()

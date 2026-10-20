"""Write analysis/REGRESSION.md and regression.csv from outputs/regression/*/summary.json."""
from __future__ import annotations
import csv

from ..common import ROOT, read, v6_trial

V6_REF = {'a_v7': ('asap_05954', 'A'), 'b_v7': ('asap_05954', 'B'), 'c_v7': ('asap_06444', 'C')}
COLS = ['scenario', 'termination', 'final_removed', 'best_removed', 'checks', 'first_valid_action_check', 'accepted_edge_reentries',
        'guarded_requests', 'restores', 'auto_checkpoints', 'llm_calls', 'recomputed_child_key_mismatches', 'wall_seconds']


def v6_row(case, arm):
    from ..metrics import summarize
    r = read(v6_trial(case, arm))
    m = summarize({**r, 'condition': arm})
    seen, re = set(), 0
    for t in r['trace']:
        if t.get('committed'):
            k = (t['physical_state_key_before'], t['part_id'], t['direction'])
            re += k in seen
            seen.add(k)
    return dict(scenario='v6 ' + case + '/' + arm, termination=r['termination'], final_removed=m['final_removed'],
                best_removed=m['best_removed'], checks=m['checks'], first_valid_action_check=m['first_valid_action_check'],
                accepted_edge_reentries=re, guarded_requests='-', restores=m['restores'], auto_checkpoints='-',
                llm_calls=m['llm_calls'], recomputed_child_key_mismatches='-', wall_seconds=round(r['elapsed_seconds']),
                total_tokens=m['total_tokens'])


def main():
    rows = []
    for name in ['a_v6_repro', 'a_v7', 'b_v6_repro', 'b_v7', 'c_v7']:
        p = ROOT / 'outputs/regression' / name / 'summary.json'
        if not p.exists():
            continue
        s = read(p)
        if name in V6_REF:
            rows.append(v6_row(*V6_REF[name]))
        rows.append({k: (round(s[k]) if k == 'wall_seconds' else s.get(k)) for k in COLS})
    with (ROOT / 'analysis/regression.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS + ['total_tokens'], extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    lines = ['| ' + ' | '.join(COLS) + ' |', '|' + '---|' * len(COLS)]
    for r in rows:
        lines.append('| ' + ' | '.join(str(r.get(c, '')) for c in COLS) + ' |')
    return '\n'.join(lines)


if __name__ == '__main__':
    print(main())

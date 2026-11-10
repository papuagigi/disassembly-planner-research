"""Aggregate the frozen v7.4 evaluation with the metrics pre-registered in campaign74.py (no model call, no physics).

usage: python -m disassembly_repair_v7_4.offline.aggregate74
Writes analysis/evaluation_runs.csv, analysis/summary_v74.json and analysis/RESULT_TABLES.md.
Every finished episode is included; only infrastructure-invalid episodes (provider_error / native_engine_resource with
0 charged checks) would be excluded, and they are listed.
"""
from __future__ import annotations
import csv
import math
import statistics

from ..common import ROOT, read, write, utc

CONDITIONS = ['a1/A/none', 'a1/B/S5', 'a1/C/S5', 'a2/B/S5+note', 'a2/C/S5+note']
FIELDS = ['case_id', 'tier', 'label', 'condition', 'attempt', 'arm', 'rep', 'success', 'termination', 'required_removed', 'checks',
          'wasted_checks', 'failed_checks', 'restores', 'llm_calls', 'total_tokens', 'elapsed_seconds', 'model_seconds',
          'other_seconds', 'invalid']


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def rows():
    tiers = {c['case_id']: c['tier'] for c in read(ROOT / 'outputs/protocol/selection_selected.json')['cases']}
    out = []
    for p in sorted((ROOT / 'outputs/evaluation').glob('*/*/metrics.json')):
        m, label = read(p), p.parent.name
        attempt, arm, memory, rep = label.split('_')
        model_s = sum(read(c)['elapsed_seconds'] or 0. for c in sorted(p.parent.glob('llm_calls/*/metadata.json')))
        cond = f"{attempt}/{arm}/{ {'none': 'none', 'base': 'S5', 'note': 'S5+note'}[memory] }".replace(' ', '')
        invalid = m['termination'] in ('provider_error', 'native_engine_resource') and not m['checks']
        out.append(dict(case_id=p.parent.parent.name, tier=tiers[p.parent.parent.name], label=label, condition=cond,
                        attempt=int(attempt[1]), arm=arm, rep=int(rep[1:]), success=bool(m['success']), termination=m['termination'],
                        required_removed=m['required_removed'], checks=m['checks'],
                        wasted_checks=m['checks'] - m['required_removed'] if m['success'] else None,
                        failed_checks=m['failed_checks'], restores=m['restores'], llm_calls=m['llm_calls'],
                        total_tokens=m['total_tokens'], elapsed_seconds=round(m['elapsed_seconds'], 1),
                        model_seconds=round(model_s, 1), other_seconds=round(m['elapsed_seconds'] - model_s, 1), invalid=invalid))
    return out


def q(xs):
    xs = sorted(xs)
    if not xs:
        return None
    qs = statistics.quantiles(xs, n=4, method='inclusive') if len(xs) > 1 else [xs[0]] * 3
    return dict(median=qs[1], q1=qs[0], q3=qs[2], max=xs[-1], mean=round(statistics.mean(xs), 2))


def summarize(rs):
    valid = [r for r in rs if not r['invalid']]
    succ = [r for r in valid if r['success']]
    return dict(runs=len(valid), successes=len(succ), success_rate=round(len(succ) / len(valid), 3) if valid else None,
                wilson95=wilson(len(succ), len(valid)), wasted_checks=q([r['wasted_checks'] for r in succ]),
                zero_waste=sum(r['wasted_checks'] == 0 for r in succ),
                tokens=q([r['total_tokens'] for r in valid]), llm_calls=q([r['llm_calls'] for r in valid]),
                elapsed=q([r['elapsed_seconds'] for r in valid]), model_seconds=q([r['model_seconds'] for r in valid]),
                other_seconds=q([r['other_seconds'] for r in valid]))


def paired(rs, x, y, key):
    """Per-CAD means of `key` for conditions x and y; Wilcoxon signed-rank on the per-CAD differences (secondary)."""
    from scipy.stats import wilcoxon
    cads = sorted({r['case_id'] for r in rs})
    mean = lambda c, cond: statistics.mean([r[key] for r in rs if r['case_id'] == c and r['condition'] == cond  # noqa: E731
                                            and r[key] is not None] or [float('nan')])
    pairs = [(c, mean(c, x), mean(c, y)) for c in cads]
    diffs = [b - a for _, a, b in pairs if not (math.isnan(a) or math.isnan(b))]
    nz = [d for d in diffs if d != 0]
    p = wilcoxon(nz).pvalue if len(nz) >= 2 else None
    return dict(x=x, y=y, metric=key, per_cad={c: [round(a, 2), round(b, 2)] for c, a, b in pairs},
                y_lower=sum(d < 0 for d in diffs), y_higher=sum(d > 0 for d in diffs), ties=sum(d == 0 for d in diffs),
                median_diff_y_minus_x=statistics.median(diffs) if diffs else None, wilcoxon_p=None if p is None else round(p, 4))


def fmt(s):
    return '–' if s is None else f"{s['median']:g} [{s['q1']:g}–{s['q3']:g}], max {s['max']:g}"


def main():
    rs = rows()
    analysis = ROOT / 'analysis'
    analysis.mkdir(exist_ok=True)
    with open(analysis / 'evaluation_runs.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rs)
    groups = {c: summarize([r for r in rs if r['condition'] == c]) for c in CONDITIONS}
    cads = sorted({r['case_id'] for r in rs}, key=lambda c: (rs[[r['case_id'] for r in rs].index(c)]['tier'], c))
    per_cad = {c: {k: summarize([r for r in rs if r['case_id'] == c and r['condition'] == k]) for k in CONDITIONS} for c in cads}
    by_tier = {t: {k: summarize([r for r in rs if r['tier'] == t and r['condition'] == k]) for k in CONDITIONS}
               for t in sorted({r['tier'] for r in rs})}
    comparisons = [paired(rs, x, y, key) for x, y in [('a1/A/none', 'a1/B/S5'), ('a1/B/S5', 'a1/C/S5'),
                                                     ('a1/B/S5', 'a2/B/S5+note'), ('a1/C/S5', 'a2/C/S5+note')]
                   for key in ('wasted_checks', 'total_tokens', 'elapsed_seconds')]
    notes = sorted((ROOT / 'outputs/note_writer').glob('*_report.json'))
    writer = dict(notes=len(notes), problems={p.stem: read(p)['problems'] for p in notes if read(p)['problems']},
                  total_tokens=[(read(p)['usage'] or {}).get('input_tokens', 0) + (read(p)['usage'] or {}).get('output_tokens', 0)
                                for p in notes])
    replay = read(ROOT / 'outputs/replay/evaluation.json') if (ROOT / 'outputs/replay/evaluation.json').exists() else None
    summary = dict(utc=utc(), episodes=len(rs), invalid=[r['label'] + '@' + r['case_id'] for r in rs if r['invalid']],
                   groups=groups, by_tier=by_tier, per_cad=per_cad, comparisons=comparisons, note_writer=writer,
                   all_repeats_succeeded={k: [c for c in cads if per_cad[c][k]['successes'] == per_cad[c][k]['runs'] == 3]
                                          for k in CONDITIONS},
                   replay=None if replay is None else dict(status=replay['status'], episodes=len(replay['episodes']),
                                                           failed=[e['result'] for e in replay['episodes']
                                                                   if not e['status'].startswith('PASS')]))
    write(analysis / 'summary_v74.json', summary)

    md = ['# v7.4 result tables (offline/aggregate74.py; all 180 frozen episodes, unfiltered)\n\n',
          '| condition | success | Wilson 95% | wasted checks, successful (median [IQR], max) | zero-waste | tokens median | '
          'calls median | elapsed s median (model / other) |\n|---|---|---|---|---|---|---|---|\n']
    for k, g in groups.items():
        md.append(f"| {k} | {g['successes']}/{g['runs']} | {g['wilson95']} | {fmt(g['wasted_checks'])} | {g['zero_waste']}/{g['successes']} | "
                  f"{g['tokens']['median']:g} | {g['llm_calls']['median']:g} | {g['elapsed']['median']:g} "
                  f"({g['model_seconds']['median']:g} / {g['other_seconds']['median']:g}) |\n")
    md.append('\n## By part-count tier (mean wasted checks of successful episodes; success)\n\n| tier | ' + ' | '.join(CONDITIONS) +
              ' |\n' + '|---' * (len(CONDITIONS) + 1) + '|\n')
    for t, g in by_tier.items():
        md.append(f'| {t} parts | ' + ' | '.join(f"{v['wasted_checks']['mean'] if v['wasted_checks'] else '–'} ({v['successes']}/{v['runs']})"
                                                 for v in g.values()) + ' |\n')
    md.append('\n## Per CAD (wasted checks of the 3 repeats: median, max; success)\n\n| CAD | tier | ' + ' | '.join(CONDITIONS) +
              ' |\n|---|---' + '|---' * len(CONDITIONS) + '|\n')
    for c in cads:
        tier = next(r['tier'] for r in rs if r['case_id'] == c)
        md.append(f'| {c} | {tier} | ' + ' | '.join(
            f"{v['wasted_checks']['median']:g}, {v['wasted_checks']['max']:g} ({v['successes']}/{v['runs']})" if v['wasted_checks'] else f"– ({v['successes']}/{v['runs']})"
            for v in per_cad[c].values()) + ' |\n')
    md.append('\n## Paired per-CAD comparisons (descriptive; Wilcoxon on per-CAD means is secondary)\n\n'
              '| x → y | metric | CADs y lower | y higher | ties | median diff (y−x) | Wilcoxon p |\n|---|---|---|---|---|---|---|\n')
    for c in comparisons:
        md.append(f"| {c['x']} → {c['y']} | {c['metric']} | {c['y_lower']} | {c['y_higher']} | {c['ties']} | "
                  f"{c['median_diff_y_minus_x']:g} | {c['wilcoxon_p']} |\n")
    md.append(f"\nNote writer: {writer['notes']} notes, problems {writer['problems'] or 'none'}, tokens per note "
              f"{min(writer['total_tokens'])}–{max(writer['total_tokens'])}.\n")
    if summary['replay']:
        md.append(f"\nIndependent replays: {summary['replay']['status']} ({summary['replay']['episodes']}), failed {summary['replay']['failed']}\n")
    md.append(f"\nInvalid (excluded) episodes: {summary['invalid'] or 'none'}\n")
    (analysis / 'RESULT_TABLES.md').write_text(''.join(md), encoding='utf-8')
    print(''.join(md))


if __name__ == '__main__':
    main()

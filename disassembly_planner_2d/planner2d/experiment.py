"""Frozen, bounded skill ablation. Each evaluation trial is preserved, including failure."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

from .agent import solve_llm
from .llm import CodexCLIProvider
from .geometry import check_action, initial_state
from .scenarios import list_scenes
from .search import solve_exact, solve_heuristic


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def provider(folder, protocol):
    return CodexCLIProvider(folder / 'llm_calls', model=protocol['model'],
                            reasoning_effort=protocol['reasoning_effort'], timeout=protocol['timeout_seconds'])


def collect(root):
    """Create scripted failure/LLM repair corpus in a NEW experiment root."""
    protocol = read(root / 'protocol_draft.json')
    for scene in list_scenes():
        if scene['split'] != 'development':
            continue
        target = next(p for p in scene['parts'] if p['id'] == scene['target_id'])
        seed = {'part_id': scene['target_id'], 'direction': target['allowed_directions'][0]}
        if check_action(scene, initial_state(scene), seed)['valid']:
            raise ValueError('A recovery source must start from an actually rejected seed')
        folder = root / 'development_sources' / scene['id']
        folder.mkdir(parents=True, exist_ok=False)
        write(folder / 'scene.json', scene)
        result = solve_llm(scene, provider(folder, protocol), max_calls=protocol['max_calls'],
                           max_checks=protocol['max_checks'], initial_actions=[seed])
        write(folder / 'result.json', result)
        print(json.dumps({'scene_id': scene['id'], 'success': result['success']}), flush=True)


def discover(root):
    from .skills import CANDIDATE_SCHEMA, build_library, discovery_prompt
    protocol = read(root / 'protocol_draft.json')
    scenes = [s for s in list_scenes() if s['split'] == 'development']
    runs = [read(root / 'development_sources' / s['id'] / 'result.json') for s in scenes]
    prompt = discovery_prompt(runs, scenes)
    candidates, meta = provider(root / 'discovery', protocol).complete(prompt, CANDIDATE_SCHEMA, 1)
    write(root / 'candidate_skills.json', candidates)
    library = build_library(runs, scenes, candidates['skills'], discovery_metadata=meta)
    write(root / 'library.json', library)
    print(json.dumps({'library_sha256': library['sha256'], 'entries': len(library['skills'])}), flush=True)


def validate_development(root):
    from .skills import verify_library
    protocol, library = read(root / 'protocol_draft.json'), read(root / 'library.json')
    verify_library(library)
    audit = []
    for scene in list_scenes():
        if scene['split'] != 'development':
            continue
        folder = root / 'development_validation' / scene['id']
        folder.mkdir(parents=True, exist_ok=False)
        result = solve_llm(scene, provider(folder, protocol), max_calls=protocol['max_calls'],
                           max_checks=protocol['max_checks'], library=library)
        result['evaluation_kind'] = 'development_library_sanity_check'
        write(folder / 'result.json', result)
        audit.append({k: result.get(k) for k in ('scene_id', 'success', 'checker_calls', 'llm_calls', 'removed_count', 'elapsed_seconds')})
        print(json.dumps(audit[-1]), flush=True)
    write(root / 'development_validation.json', {'all_success': all(x['success'] for x in audit), 'results': audit,
          'library_sha256': library['sha256'], 'scope': 'Development sanity only; no isolated causal skill efficacy claim.'})


def trial_row(result, scene_id, repeat, method, oracle, order):
    usage = result.get('token_usage', {})
    success = result['success']
    removed = result['removed_count'] if success else None
    return {'scene_id': scene_id, 'repeat': repeat, 'method': method, 'order': order,
            'success': success, 'termination': result['termination'], 'removed_count': removed,
            'oracle_removed_count': oracle, 'excess_removals': removed - oracle if removed is not None else None,
            'optimal_success': bool(success and removed == oracle),
            'checker_calls': result['checker_calls'],
            'failed_candidates': sum(not t['check']['valid'] for t in result['trace']),
            'llm_calls': result.get('llm_calls', 0), 'elapsed_seconds': result['elapsed_seconds'],
            'input_tokens': usage.get('input_tokens') if method in ('no_library', 'with_library') else 0,
            'output_tokens': usage.get('output_tokens') if method in ('no_library', 'with_library') else 0,
            'cached_input_tokens': usage.get('cached_input_tokens') if method in ('no_library', 'with_library') else 0,
            'library_entries_supplied': result.get('library_entries_supplied', 0),
            'provider_error': result.get('provider_error')}


def write_csv(path, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ['method'])
        writer.writeheader()
        writer.writerows(rows)


def evaluate(root):
    from .skills import verify_library
    from .report import write_report
    protocol, library = read(root / 'protocol_draft.json'), read(root / 'library.json')
    verify_library(library)
    validation = read(root / 'development_validation.json')
    if not validation['all_success'] or validation['library_sha256'] != library['sha256']:
        raise ValueError('Development validation must pass for the exact library snapshot before evaluation')
    target = root / 'evaluation'
    target.mkdir(exist_ok=False)
    scenes = [s for s in list_scenes() if s['split'] == 'evaluation']
    manifest = dict(protocol)
    manifest.update({'frozen_at_utc': datetime.now(timezone.utc).isoformat(), 'library_sha256': library['sha256'],
                     'scene_hashes': {s['id']: sha(s) for s in scenes},
                     'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in sorted(Path(__file__).parent.glob('*.py'))},
                     'model_identity_limit': 'Explicit CLI model slug and reasoning setting; backend snapshot not exposed.',
                     'generation_seed': None, 'temperature': None,
                     'seed_note': 'CLI does not expose controlled sampling seed here. Repeat is an independent request, not seed-paired noise.'})
    manifest['manifest_sha256'] = sha(manifest)
    write(root / 'manifest.json', manifest)
    rows, oracles = [], {}
    for scene in scenes:
        folder = target / scene['id']
        write(folder / 'scene.json', scene)
        for method, solver in [('exact', solve_exact), ('heuristic', solve_heuristic)]:
            result = solver(scene, max_checks=10000)
            if method == 'exact':
                if not result['success']:
                    raise ValueError('Reference not solved within budget')
                oracles[scene['id']] = result['removed_count']
            write(folder / (method + '.json'), result)
            rows.append(trial_row(result, scene['id'], 0, method, oracles[scene['id']], -1))
    order = 0
    for repeat in range(1, protocol['evaluation_repeats'] + 1):
        for index, scene in enumerate(scenes):
            conditions = ['no_library', 'with_library']
            if (index + repeat - 1) % 2:
                conditions.reverse()
            for method in conditions:
                order += 1
                folder = target / scene['id'] / ('repeat_%02d' % repeat) / method
                folder.mkdir(parents=True, exist_ok=False)
                result = solve_llm(scene, provider(folder, protocol), max_calls=protocol['max_calls'],
                                   max_checks=protocol['max_checks'], library=library if method == 'with_library' else None)
                result.update({'method': method, 'evaluation_kind': 'frozen_skill_ablation',
                               'repeat': repeat, 'execution_order': order, 'manifest_sha256': manifest['manifest_sha256'],
                               'recorded_at_utc': datetime.now(timezone.utc).isoformat()})
                write(folder / 'result.json', result)
                rows.append(trial_row(result, scene['id'], repeat, method, oracles[scene['id']], order))
                write(root / 'trial_rows.json', rows)
                write_csv(root / 'trials.csv', rows)
                print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    for scene in scenes:
        folder = target / scene['id']
        results = [read(folder / (m + '.json')) for m in ('exact', 'heuristic')]
        results += [read(folder / 'repeat_01' / m / 'result.json') for m in ('no_library', 'with_library')]
        write_report(scene, results, folder / 'viewer.html')
    write(root / 'evaluation_complete.json', {'completed_at_utc': datetime.now(timezone.utc).isoformat(),
          'trials': order, 'manifest_sha256': manifest['manifest_sha256']})
    summarize(root)


def stats(rows):
    completed = [r for r in rows if r['success']]
    def avg(key, subset=None):
        values = [r[key] for r in (rows if subset is None else subset) if r.get(key) is not None]
        return statistics.mean(values) if values else None
    result = {'n': len(rows), 'successes': len(completed), 'success_rate': len(completed) / len(rows),
              'optimal_successes': sum(r['optimal_success'] for r in rows),
              'optimal_success_rate': sum(r['optimal_success'] for r in rows) / len(rows),
              'mean_removed_success': avg('removed_count', completed),
              'mean_excess_success': avg('excess_removals', completed),
              'provider_errors': sum(bool(r.get('provider_error')) for r in rows)}
    for key in ('checker_calls', 'failed_candidates', 'llm_calls', 'elapsed_seconds', 'input_tokens', 'output_tokens'):
        values = [r[key] for r in rows if r.get(key) is not None]
        result['mean_' + key] = avg(key)
        result['median_' + key] = statistics.median(values) if values else None
        result['min_' + key] = min(values) if values else None
        result['max_' + key] = max(values) if values else None
        result['total_' + key] = sum(values) if values else None
        result['observed_' + key + '_n'] = len(values)
    return result


def summarize(root):
    manifest = read(root / 'manifest.json')
    rows = read(root / 'trial_rows.json')
    expected = len(manifest['scene_hashes']) * manifest['evaluation_repeats'] * 2
    if sum(r['method'] in ('no_library', 'with_library') for r in rows) != expected:
        raise ValueError('Incomplete evaluation must not be reported as complete')
    methods = [{'method': method, **stats([r for r in rows if r['method'] == method])}
               for method in ('exact', 'heuristic', 'no_library', 'with_library')]
    per_scene = [{'scene_id': sid, 'method': method,
                  **stats([r for r in rows if r['scene_id'] == sid and r['method'] == method])}
                 for sid in manifest['scene_hashes'] for method in ('exact', 'heuristic', 'no_library', 'with_library')]
    paired = []
    for sid in manifest['scene_hashes']:
        for rep in range(1, manifest['evaluation_repeats'] + 1):
            pair = {r['method']: r for r in rows if r['scene_id'] == sid and r['repeat'] == rep}
            a, b = pair['no_library'], pair['with_library']
            d = {'scene_id': sid, 'repeat': rep}
            for key in ('checker_calls', 'failed_candidates', 'llm_calls', 'elapsed_seconds', 'input_tokens', 'output_tokens'):
                d['delta_' + key] = b[key] - a[key] if a[key] is not None and b[key] is not None else None
            d['both_success'] = a['success'] and b['success']
            d['delta_excess_removals'] = b['excess_removals'] - a['excess_removals'] if d['both_success'] else None
            paired.append(d)
    costs = {}
    for stage in ('model_probe', 'development_sources', 'discovery', 'development_validation', 'evaluation'):
        logs = [read(p) for p in (root / stage).rglob('metadata.json')]
        costs[stage] = {'calls': len(logs), 'elapsed_seconds': sum(x['elapsed_seconds'] for x in logs),
                        'input_tokens': sum(x.get('usage', {}).get('input_tokens', 0) for x in logs),
                        'output_tokens': sum(x.get('usage', {}).get('output_tokens', 0) for x in logs),
                        'missing_usage_calls': sum(not x.get('usage') for x in logs)}
    summary = {'protocol': manifest, 'methods': methods, 'per_scene': per_scene, 'paired_differences': paired,
               'costs': costs, 'library_entries': len(read(root / 'library.json')['skills']),
               'notes': ['Four fixed evaluation geometries, each repeated three times per LLM condition.',
                         'Repeats are not additional independent products. No inferential significance claim.',
                         'Removed parts includes target. Failed outcomes have null removals, not zero.',
                         'Means include all fixed trials except success-only metrics explicitly labelled.',
                         'Wall time includes CLI startup and network. Tokens are reported usage, not monetary cost.',
                         'Library text supplied does not prove a skill was actually used in model reasoning.',
                         'Exact/heuristic run once per geometry. Exact search proves optimality; LLM checks proposals.']}
    write(root / 'summary.json', summary)
    write_csv(root / 'summary.csv', methods)
    write_csv(root / 'per_scene.csv', per_scene)
    write_csv(root / 'paired_differences.csv', paired)
    print(json.dumps({'complete': True, 'methods': methods}, ensure_ascii=False), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('collect', 'discover', 'validate', 'evaluate', 'summarize'))
    p.add_argument('--root', type=Path, default=Path('outputs/skill_ablation_v1'))
    args = p.parse_args()
    {'collect': collect, 'discover': discover, 'validate': validate_development,
     'evaluate': evaluate, 'summarize': summarize}[args.stage](args.root.resolve())


if __name__ == '__main__':
    main()

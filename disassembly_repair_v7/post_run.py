"""After the pilot: native-log audit, independent MuJoCo replays, viewer, MD/JSON/CSV.

No model call and no change to any score. Reference sequences (found before
evaluation by the non-LLM feasibility control) are replayed and shown only here.
"""
from __future__ import annotations
import csv
import os
import shutil
from pathlib import Path

from .common import ROOT, V6, WORKSPACE, read, sha, utc, write
from .metrics import summarize

LABELS = {'A': 'A7 · LLM 코드 / 문서 없음', 'B': 'B7 · LLM 코드 / 같은 SKILL.md',
          'C': 'C7 · Graph·LLM 순위·DFS / 같은 SKILL.md'}
TRIALS = ROOT / 'outputs/pilot/trials'


def rel(path, base):
    return os.path.relpath(Path(path).resolve(), Path(base).resolve())


def viewer():
    folder = ROOT / 'viewer'
    folder.mkdir(exist_ok=True)
    if not (folder / 'vendor').exists():
        shutil.copytree(V6 / 'viewer/vendor', folder / 'vendor')
    html = (V6 / 'viewer/index.html').read_text().replace('실제 분해 실패 절차 · 대형 CAD 비교', 'v7 수리판 · 새 CAD 첫 실행')
    html = html.replace('viewer.js?rev=final-document-v4', 'viewer.js?rev=repair-v7')
    (folder / 'index.html').write_text(html)
    js = (V6 / 'viewer/viewer.js').read_text()
    js = js.replace("names={A:'A · LLM 코드 / 문서 없음',B:'B · LLM 코드 / 문서 있음',C:'C · Graph·LLM 순위·DFS / 같은 분해 절차 문서'}",
                    "names={A:'" + LABELS['A'] + "',B:'" + LABELS['B'] + "',C:'" + LABELS['C'] + "'}")
    js = js.replace("'이 예산에서 검증된 성공 경로가 없습니다. 분해 불가능을 뜻하지 않습니다.'",
                    "'참고 경로 없음'")
    (folder / 'viewer.js').write_text(js)


def native(folder):
    from disassembly_final_v6.native_health import inspect_log
    return inspect_log(Path(folder) / 'worker.log')


def reference_episode(case, out):
    from disassembly_real_v3.simulator import FullDisassemblySim
    from .physics_variants import apply as apply_physics
    apply_physics(case.get('physics_variant'))
    ref = read(case['reference_path'])
    steps = ref['reference_sequence']
    path = out / 'reference' / case['case_id'] / 'episode.json'
    if not path.exists():
        shared = read(case['shared_path'])
        sim = FullDisassemblySim(case['case_path'], max_checks=len(steps), state=shared['state'], capture=True)
        for pid, d in steps:
            assert sim.remove(pid, d)['valid']
        assert sim.success
        sim.dump_demo(path, title=case['case_id'] + ' · 사전 물리 기준 경로(평가 후 공개)',
                      summary=dict(reference=True, condition='reference', success=True, required_removals=case['required_removals'],
                                   final_removed=len(steps), llm_calls=0, checks=sim.checks,
                                   source_scope='LLM 없는 기준 탐색이 평가 전에 찾은 경로 · planner 입력에 없음 · 유일/최적 아님'))
        ep = read(path)
        ep.update(case_id=case['case_id'], condition='reference', assembly_display_name=case['case_id'],
                  reference_sequence=dict(steps=[dict(part_id=p, direction=d) for p, d in steps]))
        for f in ep['frames']:
            f['completed_removals'] = len(f['removed'])
        write(path, ep)
    return path, steps


def replay_all():
    from disassembly_docskills_v1.post_replay import annotate
    from .replay_verify import replay_result
    manifest = read(ROOT / 'outputs/pilot/manifest.json')
    viewer()
    out = ROOT / 'replay'
    items, audits, errors, refs = [], [], [], []
    for case in manifest['cases']:
        try:
            ref_path, ref_steps = reference_episode(case, out)
            refs.append(dict(case_id=case['case_id'], url=rel(ref_path, ROOT / 'viewer')))
        except Exception as exc:
            ref_path, ref_steps = None, None
            errors.append(dict(case_id=case['case_id'], arm='reference', error=repr(exc)))
        for arm in 'ABC':
            rp = TRIALS / case['case_id'] / arm / 'result.json'
            if not rp.exists():
                continue
            result = read(rp)
            dest = out / 'data' / case['case_id'] / arm
            dest.mkdir(parents=True, exist_ok=True)
            epath, apath = dest / 'episode.json', dest / 'audit.json'
            if not epath.exists():
                try:
                    audit, sim, extra = replay_result(rp, shared_path=case['shared_path'], capture=True, allow_incomplete=True)
                except Exception as exc:
                    errors.append(dict(case_id=case['case_id'], arm=arm, error=repr(exc)[:1500]))
                    continue
                health = native(TRIALS / case['case_id'] / arm)
                summary = dict(**summarize({**result, 'condition': arm}), condition=arm, method_label=LABELS[arm], reference=False,
                               model=manifest['model'], reasoning_effort=manifest['reasoning_effort'], limits=manifest['limits'],
                               required_removals=case['required_removals'], actions=result.get('actions', []),
                               replay_audit=audit['status'], native_engine_health=health['status'],
                               native_warning_count=health['warning_count'],
                               source_scope='v7 사전등록 새 CAD 첫 실행 · 로컬 물리 모델 조건부 결과')
                summary.pop('error', None)
                sim.events = extra['events']
                sim.dump_demo(epath, title=case['case_id'] + ' · ' + LABELS[arm], summary=summary)
                episode = read(epath)
                annotate(episode, {**result, 'condition': arm, '_path': rp, '_episode_parent': dest}, result['recovery_state']['events'], extra)
                episode.update(schema='repair_v7_pilot_replay_v1', assembly_display_name=case['case_id'].replace('asap_', 'ASAP '),
                               rank_history=[{k: v for k, v in h.items() if k != 'effective_order'} for h in result.get('rank_history', [])],
                               turn_progress=result.get('turn_progress', []))
                if ref_path:
                    episode['reference_sequence'] = dict(steps=[dict(part_id=p, direction=d) for p, d in ref_steps],
                                                         episode_url=rel(ref_path, dest), after_evaluation=True, unique=False, optimality_proven=False)
                write(epath, episode)
                write(apath, audit, exclusive=True)
            audit = read(apath)
            audits.append(dict(case_id=case['case_id'], arm=arm, **{k: audit[k] for k in ('status', 'physical_queries_replayed', 'guarded_requests_replayed', 'restores_verified')}))
            items.append(dict(case_id=case['case_id'], arm=arm, label=LABELS[arm], url=rel(epath, ROOT / 'viewer'),
                              result_url=rel(rp, ROOT / 'viewer'), episode_sha256=sha(epath), summary=read(epath)['summary']))
    write(out / 'index.json', dict(status='PASS' if not errors else 'INCOMPLETE', created_utc=utc(), episodes=items, references=refs,
                                   default_url=items[0]['url'] if items else None))
    write(out / 'audit.json', dict(status='PASS' if not errors else 'FAIL', episodes=audits, errors=errors, no_model_calls=True))
    return errors


def aggregate():
    manifest = read(ROOT / 'outputs/pilot/manifest.json')
    rows = []
    for case in manifest['cases']:
        for arm in 'ABC':
            rp = TRIALS / case['case_id'] / arm / 'result.json'
            if not rp.exists():
                rows.append(dict(case_id=case['case_id'], condition=arm, status='NOT_RUN'))
                continue
            r = read(rp)
            m = summarize({**r, 'condition': arm})
            m['native_engine_health'] = native(TRIALS / case['case_id'] / arm)['status']
            m['reference_length'] = len(read(case['reference_path'])['reference_sequence'])
            rows.append(m)
    flat = [{k: (v if not isinstance(v, (dict, list)) else str(v)) for k, v in r.items()} for r in rows]
    keys = sorted({k for r in flat for k in r})
    with (ROOT / 'analysis/pilot_trials.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(flat)
    by_arm = {}
    for arm in 'ABC':
        sel = [r for r in rows if r.get('condition') == arm and 'success' in r]
        by_arm[arm] = dict(episodes=len(sel), successes=sum(r['success'] for r in sel),
                           final_removed=[r['final_removed'] for r in sel], best_removed=[r['best_removed'] for r in sel],
                           required=[r['required_removed'] for r in sel], checks=[r['checks'] for r in sel],
                           llm_calls=[r['llm_calls'] for r in sel], total_tokens=sum(r['total_tokens'] for r in sel),
                           unknown_usage_calls=sum(r['unknown_usage_calls'] for r in sel),
                           termination_classes=[r['termination_class'] for r in sel])
    write(ROOT / 'analysis/pilot_results.json', dict(utc=utc(), episodes=rows, by_arm=by_arm,
                                                     scope='Small pre-registered pilot; local physics model; not industrial validation.'))
    return rows, by_arm


def markdown(rows, by_arm):
    cols = ['case_id', 'condition', 'success', 'termination_class', 'final_removed', 'best_removed', 'required_removed',
            'reference_length', 'checks', 'first_valid_action_check', 'accepted_edge_revisits', 'repeated_rejected_queries',
            'guarded_requests', 'restores_with_state_change', 'restores_without_state_change', 'no_progress_calls',
            'llm_calls', 'total_tokens', 'unknown_usage_calls', 'elapsed_seconds', 'native_engine_health']
    lines = ['# v7 pilot results (pre-registered, first encounters)', '',
             'Scope: never-opened official ASAP CADs (training split primary, test split backup) qualified by unchanged v6 conversion/initial physics and a non-LLM reference sequence under physics P2 (never given to planners). Episodes ran under P2. gpt-6-luna/low, v6 limits, one episode per arm, sequential. Local physics model; small pilot; not industrial validation. v6->v7 changed several mechanisms (CHANGELOG.md), so no single-cause attribution.', '',
             '| ' + ' | '.join(cols) + ' |', '|' + '---|' * len(cols)]
    for r in rows:
        val = []
        for c in cols:
            v = r.get(c, '')
            val.append(f'{v:.0f}' if isinstance(v, float) else str(v))
        lines.append('| ' + ' | '.join(val) + ' |')
    lines += ['', '## Per arm', '', '| arm | episodes | successes | final removed | best removed | required | checks | calls | tokens (in+out) | unknown-usage calls | termination classes |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for arm, a in by_arm.items():
        lines.append(f"| {arm} | {a['episodes']} | {a['successes']} | {a['final_removed']} | {a['best_removed']} | {a['required']} | {a['checks']} | {a['llm_calls']} | {a['total_tokens']} | {a['unknown_usage_calls']} | {a['termination_classes']} |")
    (ROOT / 'analysis/PILOT_RESULTS.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    rows, by_arm = aggregate()
    markdown(rows, by_arm)
    print(by_arm)
    print(replay_all())

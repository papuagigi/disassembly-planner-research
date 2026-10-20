"""v7.3 development validation and final evaluation on NEW CADs (sequential, frozen, no reruns).

Pre-registered here (before any v7.3 validation or evaluation outcome):
VALIDATION  development CADs 05459, 02406, 07375, 03674 (held out from S5 writing: mine73.VALIDATION_CADS).
            Arms A(S0), B(S5), C(S5), 2 repeats each, arm order rotated per CAD; one episode at a time.
            Infrastructure-invalid episodes are excluded from both numerator and denominator: termination class
            provider_error or native_engine_resource with 0 charged checks (rare after R7; listed in the decision).
            X in {B, C} passes if its success rate > A's, or equal and the median charged checks of its successful
            runs <= A's (if no arm succeeded: mean best_removed > A's). S5 is admitted iff at least one of B, C passes
            and neither B nor C has a lower success rate than A.
EVALUATION  the 4 NEW CADs of outputs/protocol/selection_selected.json (never opened before v7.3; reference sequences
            never shown to planners). Base bank Sx = S5 if admitted, else S3 (last admitted; byte-identical copy) and
            then an exploratory S5 branch is added and reported separately (never pooled).
            Per CAD: attempt 1 A(S0), B(Sx), C(Sx) [+ B(S5), C(S5) if exploratory]; assembly note written by
            gpt-6-luna/low from the three primary attempt-1 records (+ a second note from A, B(S5), C(S5));
            attempt 2: B(Sx+note), C(Sx+note), [B(S5+note), C(S5+note)], A(S0), B(Sx), C(Sx), B(Sx+note) r2,
            C(Sx+note) r2, in this order.
            Primary metrics: success, charged checks, elapsed seconds, tokens; every episode reported as-is.
Common: gpt-6-luna/low, v7.2 limits (8 calls, 240 checks, 900 s, 8 GiB), physics P2, E1 threaded winding (decision-
identical, accepted by outputs/e1/equality.json), R7 recoverable responses, contract notes 8-10, note writer v2.
"""
from __future__ import annotations
import argparse
import shutil
import statistics
from pathlib import Path

from .common import ROOT, V6, read, write, utc, sha
from .learning73 import dev_case, eval_case, job, PHYSICS
from .mine73 import VALIDATION_CADS
from .procs import project_processes

S0_BANK = V6 / 'memory/S0.json'
S5_BANK = ROOT / 'memory/S5.json'
FREEZE = {'validation': ROOT / 'outputs/protocol/freeze_validation.json', 'evaluation': ROOT / 'outputs/protocol/freeze_evaluation.json'}
CODE_FILES = ['actors.py', 'shared_api.py', 'runtime.py', 'controller.py', 'contracts.py', 'driver.py', 'metrics.py', 'campaign.py',
              'learning73.py', 'mine73.py', 'skill_writer.py', 'procs.py', 'replay_verify.py', 'provider.py', 'fast_geometry.py']


def freeze(stage, banks, extra=None):
    path = FREEZE[stage]
    if path.exists():
        return verify(stage)
    from disassembly_final_v6.documents import DocumentBank
    files = [ROOT / f for f in CODE_FILES]
    for b in banks:
        bank = DocumentBank(b)
        files += [bank.path] + [bank.path.parent / r['path'] for r in bank.manifest['skills']]
    e1 = read(ROOT / 'outputs/e1/equality.json')
    assert e1['status'] == 'PASS', 'E1 must be accepted before any frozen run'
    value = dict(stage=stage, utc=utc(), status='FROZEN_BEFORE_OUTCOMES', banks=[str(b) for b in banks], rules=__doc__.strip(),
                 physics=PHYSICS, e1_equality=dict(status=e1['status'], episodes=e1['episodes']),
                 sha256={str(p): sha(p) for p in files}, **(extra or {}))
    write(path, value, exclusive=True)
    return value


def verify(stage):
    value = read(FREEZE[stage])
    for p, h in value['sha256'].items():
        assert sha(p) == h, ('frozen file changed', p)
    return value


def run_one(spec):
    """Start a timed episode only when no other project python process is alive (waits up to 30 min)."""
    import time
    from .driver import run
    waited = 0
    while True:
        busy = project_processes()
        if not busy:
            break
        if waited == 0:
            write(ROOT / 'outputs/waits.jsonl.last', dict(utc=utc(), folder=spec['folder'], busy=busy))
        if waited > 1800:
            raise RuntimeError(('background project process during a timed episode', busy))
        time.sleep(15)
        waited += 15
    spec['waited_for_quiet_seconds'] = waited
    return run(spec)


def validation():
    freeze('validation', [S0_BANK, S5_BANK])
    rows = []
    for rep in (1, 2):
        for i, cid in enumerate(VALIDATION_CADS):
            order = ['A', 'B', 'C'][i % 3:] + ['A', 'B', 'C'][:i % 3]
            for arm in order:
                verify('validation')
                folder = ROOT / 'outputs/validation' / cid / f'{arm}_r{rep}'
                spec = job(dev_case(cid), arm, S0_BANK if arm == 'A' else S5_BANK, 'validation', folder, sha(FREEZE['validation']))
                r = run_one(spec)
                m = read(folder / 'metrics.json')
                rows.append(dict(case_id=cid, arm=arm, rep=rep, success=bool(r['success']), checks=m['checks'], removed=m['best_removed'],
                                 termination_class=m['termination_class'], elapsed=m['elapsed_seconds'], folder=str(folder)))
                write(ROOT / 'outputs/validation/progress.json', dict(utc=utc(), rows=rows))
    decision = admission(rows)
    write(ROOT / 'outputs/validation/decision.json', dict(utc=utc(), rows=rows, **decision), exclusive=True)
    return decision


def infrastructure_invalid(row):
    return row['termination_class'] in ('provider_error', 'native_engine_resource') and row['checks'] == 0


def admission(rows):
    valid = [r for r in rows if not infrastructure_invalid(r)]

    def stats(arm):
        sel = [r for r in valid if r['arm'] == arm]
        succ = [r for r in sel if r['success']]
        return dict(successes=len(succ), runs=len(sel), rate=(len(succ) / len(sel)) if sel else None,
                    median_checks_successful=statistics.median([r['checks'] for r in succ]) if succ else None,
                    mean_removed=statistics.mean([r['removed'] for r in sel]) if sel else None)
    s = {arm: stats(arm) for arm in 'ABC'}

    def passes(x):
        a, b = s['A'], s[x]
        if b['rate'] is None or a['rate'] is None:
            return False
        if b['rate'] != a['rate']:
            return b['rate'] > a['rate']
        if a['successes'] == 0:
            return b['mean_removed'] > a['mean_removed']
        return b['median_checks_successful'] <= a['median_checks_successful']
    p = {x: passes(x) for x in 'BC'}
    admitted = (p['B'] or p['C']) and all(s[x]['rate'] is not None and s[x]['rate'] >= s['A']['rate'] for x in 'BC')
    return dict(stats=s, passes=p, admitted=bool(admitted), excluded_infrastructure=[r['folder'] for r in rows if infrastructure_invalid(r)],
                rule='see campaign.py docstring')


def s3_copy():
    from disassembly_final_v6.documents import DocumentBank, make_bank
    target = ROOT / 'memory/S3copy.json'
    if not target.exists():
        src = DocumentBank(V6 / 'memory/S3.json')
        docs = []
        for row in src.manifest['skills']:
            dst = ROOT / 'memory/S3copy' / row['id'] / 'SKILL.md'
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(V6 / 'memory' / row['path'], dst)
            assert sha(dst) == row['sha256']
            docs.append(dst)
        make_bank(target, docs, version='S3copy', evidence=dict(source=str(V6 / 'memory/S3.json')))
    return target


SECOND = [('B', 'note', 1), ('C', 'note', 1), ('B', 'S5note', 1), ('C', 'S5note', 1), ('A', 'none', 1), ('B', 'base', 1),
          ('C', 'base', 1), ('B', 'note', 2), ('C', 'note', 2)]   # 'S5note' rows only in the exploratory branch


def evaluation():
    from .skill_writer import write_note
    d = read(ROOT / 'outputs/validation/decision.json')
    base_bank, label = (S5_BANK, 'S5') if d['admitted'] else (s3_copy(), 'S3')
    exploratory = label != 'S5'
    cads = [c['case_id'] for c in read(ROOT / 'outputs/protocol/selection_selected.json')['cases']]
    freeze('evaluation', [S0_BANK, base_bank] + ([S5_BANK] if exploratory else []),
           extra=dict(base_bank=label, exploratory_s5=exploratory, cads=cads))
    results = []

    def episode(cid, case, arm, bank, name, phase):
        verify('evaluation')
        folder = ROOT / 'outputs/evaluation' / cid / name
        r = run_one(job(case, arm, bank, phase, folder, sha(FREEZE['evaluation'])))
        results.append(dict(case_id=cid, label=name, arm=arm, bank=Path(bank).stem, success=bool(r['success']),
                            checks=r.get('checker_calls'), termination=r.get('termination')))
        write(ROOT / 'outputs/evaluation/progress.json', dict(utc=utc(), base_bank=label, exploratory_s5=exploratory, results=results))
        return folder / 'result.json'

    for cid in cads:
        case = eval_case(cid)
        first = {'A': episode(cid, case, 'A', S0_BANK, 'first_A', 'first_encounter')}
        for arm in ('B', 'C'):
            first[arm] = episode(cid, case, arm, base_bank, f'first_{arm}', 'first_encounter')
        if exploratory:
            for arm in ('B', 'C'):
                first[arm + '-S5'] = episode(cid, case, arm, S5_BANK, f'first_{arm}_S5', 'first_encounter_exploratory')
        banks = {'none': S0_BANK, 'base': base_bank, 'note': ROOT / 'memory' / f'{label}_note_{cid}.json'}
        if not banks['note'].exists():
            write_note(cid, [first['A'], first['B'], first['C']], banks['note'], base_bank)
        if exploratory:
            banks['S5note'] = ROOT / 'memory' / f'S5_note_{cid}.json'
            if not banks['S5note'].exists():
                write_note(cid + '_S5', [first['A'], first['B-S5'], first['C-S5']], banks['S5note'], S5_BANK)
        for arm, memory, rep in SECOND:
            if memory in banks:
                phase = 'second_attempt_exploratory' if memory == 'S5note' else 'second_attempt'
                bank = banks['none'] if arm == 'A' else banks[memory]
                episode(cid, case, arm, bank, f'second_{arm}_{memory}_r{rep}', phase)
    write(ROOT / 'outputs/evaluation/complete.json', dict(utc=utc(), base_bank=label, exploratory_s5=exploratory, results=results),
          exclusive=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['validation', 'evaluation'])
    a = p.parse_args()
    print(validation() if a.stage == 'validation' else evaluation())

"""v7.2 validation and same-assembly retry evaluation (sequential, frozen, no reruns).

Pre-registered here (before any validation or retry outcome):
VALIDATION  CADs 05459, 02402 (development; not used for collection). Arms A(S0), B(S4), C(S4), 2 repeats each.
            Admission of S4: for X in {B, C}: X "passes" if success_X > success_A, or success_X == success_A and
            the median charged checks over X's successful runs <= A's (if no arm succeeded: mean best_removed).
            S4 is admitted iff at least one of B, C passes and neither B nor C has fewer successes than A.
            If not admitted, the retry evaluation uses the last admitted bank S3 (copied byte-identically).
RETRY       CADs 05902, 06146 (v7.1 pilot CADs; never used to build S4). For each CAD:
            attempt 1: A(S0), B(Sx), C(Sx) once each (Sx = S4 if admitted else S3);
            assembly note: gpt-6-luna/low writes one note from those three attempt records only;
            attempt 2: B(Sx+note) x2, C(Sx+note) x2, B(Sx) x1, C(Sx) x1, A(S0) x1, in a fixed interleaved order.
            Primary metrics: success, charged checks, elapsed seconds, tokens; reported as-is.
Model gpt-6-luna/low, v7.2 limits (8 calls, 240 checks, 900 s, 8 GiB), physics P2, one episode at a time.
"""
from __future__ import annotations
import argparse
import shutil
import statistics

from .common import ROOT, V7, V6, read, write, utc, sha
from .learning import case, job, BANKS, VALIDATION, PHYSICS
from .procs import project_processes

RETRY_CADS = ('asap_05902', 'asap_06146')
FREEZE = {'validation': ROOT / 'outputs/protocol/freeze_validation.json', 'retry': ROOT / 'outputs/protocol/freeze_retry.json'}
CODE_FILES = ['actors.py', 'shared_api.py', 'runtime.py', 'controller.py', 'contracts.py', 'driver.py', 'metrics.py',
              'campaign.py', 'learning.py', 'skill_writer.py', 'procs.py', 'replay_verify.py']


def retry_case(cid):
    sel = read(V7 / 'outputs/protocol/pilot_selected_P2.json')
    c = [x for x in sel['cases'] if x['case_id'] == cid][0]
    return dict(case_id=cid, case_path=c['case_path'], shared_path=c['shared_path'])


def freeze(stage, bank_path):
    path = FREEZE[stage]
    if path.exists():
        return verify(stage)
    from disassembly_final_v6.documents import DocumentBank
    bank = DocumentBank(bank_path)
    files = [ROOT / f for f in CODE_FILES] + [bank.path] + [bank.path.parent / r['path'] for r in bank.manifest['skills']]
    value = dict(stage=stage, utc=utc(), status='FROZEN_BEFORE_OUTCOMES', bank=str(bank.path), bank_sha256=bank.sha256,
                 bank_content_sha256=bank.content_sha256, rules=__doc__.strip(), physics=PHYSICS,
                 sha256={str(p): sha(p) for p in files})
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
    frozen = freeze('validation', ROOT / 'memory/S4.json')
    rows = []
    for rep in (1, 2):
        for i, cid in enumerate(VALIDATION):
            order = ['A', 'B', 'C'][i:] + ['A', 'B', 'C'][:i]
            for arm in order:
                verify('validation')
                bank = BANKS['S0'] if arm == 'A' else ROOT / 'memory/S4.json'
                folder = ROOT / 'outputs/validation' / cid / f'{arm}_r{rep}'
                spec = job(cid, arm, bank, 'validation', folder)
                spec['protocol_sha256'] = sha(FREEZE['validation'])
                r = run_one(spec)
                rows.append(dict(case_id=cid, arm=arm, rep=rep, success=bool(r['success']), checks=r.get('checker_calls'),
                                 removed=len(r.get('actions', [])), elapsed=r.get('elapsed_seconds'), folder=str(folder)))
                write(ROOT / 'outputs/validation/progress.json', dict(utc=utc(), rows=rows))
    decision = admission(rows)
    write(ROOT / 'outputs/validation/decision.json', dict(utc=utc(), rows=rows, **decision), exclusive=True)
    return decision


def admission(rows):
    def stats(arm):
        sel = [r for r in rows if r['arm'] == arm]
        succ = [r for r in sel if r['success']]
        return dict(successes=len(succ), runs=len(sel),
                    median_checks_successful=statistics.median([r['checks'] for r in succ]) if succ else None,
                    mean_removed=statistics.mean([r['removed'] for r in sel]) if sel else None)
    s = {arm: stats(arm) for arm in 'ABC'}

    def passes(x):
        a, b = s['A'], s[x]
        if b['successes'] != a['successes']:
            return b['successes'] > a['successes']
        if a['successes'] == 0:
            return b['mean_removed'] > a['mean_removed']
        return b['median_checks_successful'] <= a['median_checks_successful']
    p = {x: passes(x) for x in 'BC'}
    admitted = (p['B'] or p['C']) and all(s[x]['successes'] >= s['A']['successes'] for x in 'BC')
    return dict(stats=s, passes=p, admitted=bool(admitted), rule='see campaign.py docstring')


def bank_for_retry():
    d = read(ROOT / 'outputs/validation/decision.json')
    if d['admitted']:
        return ROOT / 'memory/S4.json', 'S4'
    # copy S3 under v7_2/memory so notes can be bundled with it (bytes identical)
    from disassembly_final_v6.documents import DocumentBank, make_bank
    target = ROOT / 'memory/S3copy.json'
    if not target.exists():
        src = DocumentBank(V6 / 'memory/S3.json')
        docs = []
        for row in src.manifest['skills']:
            s = (V6 / 'memory' / row['path'])
            dst = ROOT / 'memory/S3copy' / row['id'] / 'SKILL.md'
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, dst)
            assert sha(dst) == row['sha256']
            docs.append(dst)
        make_bank(target, docs, version='S3copy', evidence=dict(source=str(V6 / 'memory/S3.json')))
    return target, 'S3'


SECOND = [('B', 'note', 1), ('C', 'note', 1), ('B', 'base', 1), ('C', 'base', 1), ('A', 'none', 1),
          ('B', 'note', 2), ('C', 'note', 2)]


def retry():
    from .contracts import LIMITS, ARMS
    from .driver import run
    from .skill_writer import write_note
    base_bank, label = bank_for_retry()
    frozen = freeze('retry', base_bank)
    results = []
    for cid in RETRY_CADS:
        c = retry_case(cid)
        first = []
        for arm in ('A', 'B', 'C'):
            verify('retry')
            bank = BANKS['S0'] if arm == 'A' else base_bank
            folder = ROOT / 'outputs/retry' / cid / f'first_{arm}'
            spec = dict(folder=str(folder), case_path=c['case_path'], shared_path=c['shared_path'],
                        architecture=ARMS[arm]['architecture'], bank_path=str(bank), limits=LIMITS, phase='retry_first_attempt',
                        arm=arm, protocol_sha256=sha(FREEZE['retry']), physics_variant=PHYSICS)
            r = run_one(spec)
            first.append(folder / 'result.json')
            results.append(dict(case_id=cid, label=f'first_{arm}', success=bool(r['success']), checks=r.get('checker_calls')))
        note_bank = ROOT / 'memory' / f'{label}_note_{cid}.json'
        if not note_bank.exists():
            write_note(cid, first, note_bank, base_bank)
        for arm, memory, rep in SECOND:
            verify('retry')
            bank = BANKS['S0'] if arm == 'A' else (note_bank if memory == 'note' else base_bank)
            folder = ROOT / 'outputs/retry' / cid / f'second_{arm}_{memory}_r{rep}'
            spec = dict(folder=str(folder), case_path=c['case_path'], shared_path=c['shared_path'],
                        architecture=ARMS[arm]['architecture'], bank_path=str(bank), limits=LIMITS, phase='retry_second_attempt',
                        arm=arm, protocol_sha256=sha(FREEZE['retry']), physics_variant=PHYSICS)
            r = run_one(spec)
            results.append(dict(case_id=cid, label=f'second_{arm}_{memory}_r{rep}', success=bool(r['success']),
                                checks=r.get('checker_calls')))
            write(ROOT / 'outputs/retry/progress.json', dict(utc=utc(), results=results))
    write(ROOT / 'outputs/retry/complete.json', dict(utc=utc(), base_bank=label, results=results), exclusive=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['validation', 'retry'])
    a = p.parse_args()
    print(validation() if a.stage == 'validation' else retry())

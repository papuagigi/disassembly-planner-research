"""v7.4 reliability evaluation of the unchanged v7.3 planner on easy NEW CADs, with repeats (sequential, frozen, no reruns).

Pre-registered here (before any v7.4 episode; the CADs come from selection74, which uses no planner outcome):
CADS     the 12 NEW CADs of outputs/protocol/selection_selected.json (4 each with 5, 6 and 7 parts, i.e. 4-6 required
         removals). If the pool yields fewer, the cases found are used if there are >= 9; otherwise the user is asked.
BANK     Sx = the 범용 SKILL.md chosen at freeze time (--bank S5 = latest v7.3 document, not admitted in v7.3 validation;
         --bank S3 = last admitted, byte-identical v7.3 copy). Read-only from disassembly_repair_v7_3/memory.
PER CAD  attempt 1: three repeats of A(S0), B(Sx), C(Sx); arm order rotated by (CAD index + repeat).
         조립체별 SKILL.md: written once by gpt-6-luna/low from the three repeat-1 attempt-1 records (note writer v2,
         host-appended Recorded sequence), exactly as in v7.3.
         attempt 2: three repeats of B(Sx + 조립체별) and C(Sx + 조립체별), order alternating by repeat.
         15 episodes per CAD, 180 in all, one at a time on a quiet machine; a started episode is never rerun.
METRICS  every episode is reported as-is. Infrastructure-invalid episodes (termination provider_error or
         native_engine_resource with 0 charged checks) are excluded from numerator and denominator and listed.
         Reliability: success rate per condition (36 episodes each) with a Wilson 95% interval; CADs where every
         repeat succeeded.
         Efficiency (reported whatever the success rates; the main comparison when rates are tied):
           wasted checks = charged checks - required removals (successful episodes; median, IQR, max),
           total tokens and LLM calls per episode,
           elapsed seconds, split into model seconds (sum of per-call elapsed_seconds) and the rest (physics + host).
         Variability: per-CAD spread over the three repeats of each condition.
         Comparisons, paired by CAD (descriptive; a Wilcoxon signed-rank test on per-CAD means is secondary):
           A vs B (effect of the 범용 SKILL.md), B vs C (role split), attempt 1 vs attempt 2 within B and within C
           (effect of the 조립체별 SKILL.md). No single-cause claim beyond what the design isolates.
Common: gpt-6-luna/low, v7.3 limits (8 calls, 240 checks, 900 s, 8 GiB), physics P2, E1 threaded winding, R7
recoverable responses, contract notes 8-10. The planner modules are byte-identical copies of v7.3 (freeze checks it).
"""
from __future__ import annotations
import argparse
import filecmp
from pathlib import Path

from .common import ROOT, V6, V73, read, write, utc, sha
from .learning73 import eval_case, job, PHYSICS
from .procs import project_processes

S0_BANK = V6 / 'memory/S0.json'
BANKS = {'S5': V73 / 'memory/S5.json', 'S3': V73 / 'memory/S3copy.json'}
FREEZE = ROOT / 'outputs/protocol/freeze_evaluation.json'
# Amendment 1 (user-approved after 9 attempt-1 episodes; no planner-visible change): make_bank stores document paths
# relative to the note bank's folder, so the note writer reads byte-identical copies of the base bank under ROOT/memory.
AMENDMENT = ROOT / 'outputs/protocol/amendment1_note_base_path.json'
NOTE_BASES = {k: ROOT / 'memory' / v.name for k, v in BANKS.items()}
REPEATS = 3
IDENTICAL_TO_V73 = ['actors.py', 'shared_api.py', 'runtime.py', 'controller.py', 'contracts.py', 'metrics.py', 'learning73.py',
                    'mine73.py', 'mine.py', 'skill_writer.py', 'provider.py', 'fast_geometry.py', 'replay_verify.py']
CODE_FILES = IDENTICAL_TO_V73 + ['common.py', 'driver.py', 'procs.py', 'campaign74.py', 'selection74.py']


def freeze(bank_label):
    if FREEZE.exists():
        value = verify()
        assert value['bank'] == bank_label, ('frozen with another bank', value['bank'])
        return value
    from disassembly_final_v6.documents import DocumentBank
    differing = [f for f in IDENTICAL_TO_V73 if not filecmp.cmp(ROOT / f, V73 / f, shallow=False)]
    assert not differing, ('planner copy differs from v7.3', differing)
    selected = read(ROOT / 'outputs/protocol/selection_selected.json')
    cads = [c['case_id'] for c in selected['cases']]
    assert len(cads) >= 9, ('fewer than 9 CADs: ask the user', cads)
    files = [ROOT / f for f in CODE_FILES]
    for b in (S0_BANK, BANKS[bank_label]):
        bank = DocumentBank(b)
        files += [bank.path] + [bank.path.parent / r['path'] for r in bank.manifest['skills']]
    value = dict(utc=utc(), status='FROZEN_BEFORE_OUTCOMES', bank=bank_label, cads=cads, repeats=REPEATS, rules=__doc__.strip(),
                 physics=PHYSICS, planner_identical_to_v73=IDENTICAL_TO_V73, sha256={str(p): sha(p) for p in files},
                 selection_sha256=sha(ROOT / 'outputs/protocol/selection_selected.json'))
    write(FREEZE, value, exclusive=True)
    return value


def verify():
    value = read(FREEZE)
    amended = read(AMENDMENT)['sha256'] if AMENDMENT.exists() else {}
    for p, h in value['sha256'].items():
        assert sha(p) == amended.get(p, h), ('frozen file changed', p)
    for p, h in amended.items():
        assert sha(p) == h, ('amended file changed', p)
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


def schedule(cads):
    """(cid, attempt, arm, memory, repeat) in run order; the note is written after the last attempt-1 episode of a CAD."""
    rows = []
    for i, cid in enumerate(cads):
        for rep in range(1, REPEATS + 1):
            k = (i + rep) % 3
            for arm in (['A', 'B', 'C'][k:] + ['A', 'B', 'C'][:k]):
                rows.append((cid, 1, arm, 'none' if arm == 'A' else 'base', rep))
        for rep in range(1, REPEATS + 1):
            for arm in (('B', 'C') if rep % 2 else ('C', 'B')):
                rows.append((cid, 2, arm, 'note', rep))
    return rows


def local_base(bank_label):
    """Byte-identical copy of the v7.3 base bank under ROOT/memory (amendment 1)."""
    from disassembly_final_v6.documents import DocumentBank
    src, dst = BANKS[bank_label], NOTE_BASES[bank_label]
    rows = DocumentBank(src).manifest['skills']
    for f in [Path(src.name)] + [Path(r['path']) for r in rows]:
        a, b = src.parent / f, dst.parent / f
        if not b.exists():
            b.parent.mkdir(parents=True, exist_ok=True)
            b.write_bytes(a.read_bytes())
        assert sha(a) == sha(b), ('local base copy differs', f)
    return dst


def evaluation(bank_label):
    from .skill_writer import write_note
    frozen = freeze(bank_label)
    base = BANKS[bank_label]
    progress = ROOT / 'outputs/evaluation/progress.json'
    results = read(progress)['results'] if progress.exists() else []
    for cid, attempt, arm, memory, rep in schedule(frozen['cads']):
        name = f'a{attempt}_{arm}_{memory}_r{rep}'
        folder = ROOT / 'outputs/evaluation' / cid / name
        if attempt == 2:
            note = ROOT / 'memory' / f'{bank_label}_note_{cid}.json'
            if not note.exists():
                first = [ROOT / 'outputs/evaluation' / cid / f'a1_{a}_{"none" if a == "A" else "base"}_r1' / 'result.json' for a in 'ABC']
                write_note(cid, first, note, local_base(bank_label))
            bank = note
        else:
            bank = S0_BANK if arm == 'A' else base
        if (folder / 'result.json').exists():   # resume after an interruption; never rerun a finished episode
            continue
        assert not folder.exists(), ('started episode without result: finalize, do not rerun', folder)
        verify()
        phase = 'first_encounter' if attempt == 1 else 'second_attempt'
        r = run_one(job(eval_case(cid), arm, bank, phase, folder, sha(FREEZE)))
        results.append(dict(case_id=cid, label=name, attempt=attempt, arm=arm, memory=memory, rep=rep, bank=Path(bank).stem,
                            success=bool(r['success']), checks=r.get('checker_calls'), termination=r.get('termination')))
        write(progress, dict(utc=utc(), bank=bank_label, results=results))
    write(ROOT / 'outputs/evaluation/complete.json', dict(utc=utc(), bank=bank_label, episodes=len(schedule(frozen['cads']))),
          exclusive=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['freeze', 'evaluation', 'schedule'])
    p.add_argument('--bank', choices=sorted(BANKS), required=True)
    a = p.parse_args()
    if a.command == 'schedule':
        rows = schedule([c['case_id'] for c in read(ROOT / 'outputs/protocol/selection_selected.json')['cases']])
        print(len(rows), rows[:16])
    else:
        print(freeze(a.bank) if a.command == 'freeze' else evaluation(a.bank))

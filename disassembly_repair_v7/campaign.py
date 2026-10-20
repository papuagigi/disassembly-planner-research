"""Run the frozen v7 pilot: each selected case once per arm, sequentially, no reruns."""
from __future__ import annotations
import json
import subprocess

from .common import ROOT, V6, read, sha, utc, write
from .contracts import ARMS
from .protocol import verify
from .driver import run

TRIALS = ROOT / 'outputs/pilot/trials'


def heavy_processes():
    out = subprocess.run(['ps', '-axo', 'command'], capture_output=True, text=True).stdout
    keys = ('disassembly_repair_v7.feasibility', 'disassembly_repair_v7.pilot_inputs', 'disassembly_repair_v7.offline',
            'disassembly_final_v6.pipeline', 'disassembly_final_v6.driver')
    return [line[:160] for line in out.splitlines() if any(k in line for k in keys)]


def main():
    done = ROOT / 'outputs/pilot/complete.json'
    if done.exists():
        return read(done)
    frozen = verify()
    from .pilot_inputs import SELECTED
    selected = read(SELECTED)
    cases = selected['cases']
    manifest_path = ROOT / 'outputs/pilot/manifest.json'
    if not manifest_path.exists():
        from .protocol import FREEZE
        write(manifest_path, dict(utc=utc(), protocol_sha256=sha(FREEZE), cases=cases,
                                  selection_status=selected['status'], planned_episodes=3 * len(cases), arms=ARMS,
                                  limits=frozen['limits'], model=frozen['model'], reasoning_effort=frozen['reasoning_effort'],
                                  first_encounter=True, reference_given_to_planners=False,
                                  physics_variant=frozen['physics_variant']), exclusive=True)
    manifest = read(manifest_path)
    arms = list(ARMS)
    completed = []
    for i, case in enumerate(manifest['cases']):
        for arm in arms[i % 3:] + arms[:i % 3]:
            verify()
            busy = heavy_processes()
            assert not busy, ('heavy background process during a timed episode', busy)
            for p in [case['case_path'], case['shared_path']]:
                assert sha(p) == (case['case_sha256'] if p == case['case_path'] else case['shared_sha256'])
            conf = ARMS[arm]
            folder = TRIALS / case['case_id'] / arm
            write(ROOT / 'outputs/pilot/progress.json', dict(utc=utc(), case=case['case_id'], arm=arm, completed=len(completed),
                                                             planned=manifest['planned_episodes']))
            run(dict(folder=str(folder), case_path=case['case_path'], shared_path=case['shared_path'],
                     architecture=conf['architecture'], bank_path=str(V6 / 'memory' / (conf['bank'] + '.json')),
                     limits=manifest['limits'], phase='pilot', arm=arm, protocol_sha256=manifest['protocol_sha256'],
                     physics_variant=manifest['physics_variant']))
            completed.append(dict(case_id=case['case_id'], arm=arm, result=str(folder / 'result.json'), sha256=sha(folder / 'result.json')))
    write(done, dict(status='COMPLETE', utc=utc(), episodes=completed, expected=manifest['planned_episodes'],
                     no_memory_updates=True), exclusive=True)
    return read(done)


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False)[:1500])

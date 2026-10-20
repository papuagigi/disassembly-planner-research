"""Post-hoc diagnosis of the 06146/C memory-guard stop (no model call; score unchanged).

Replays the preserved C responses through the v7 actor with the real simulator
under P2, with the RSS guard raised to 16 GiB, while a sampler thread records
RSS every 0.25 s together with the current check count and API event.
"""
from __future__ import annotations
import resource
import sys
import threading
import time

from ..common import ROOT, read, utc, write
from .providers import ReplayProvider


def rss_now():
    # Current RSS via ps (ru_maxrss is a peak, not a time series).
    import subprocess, os
    out = subprocess.run(['ps', '-o', 'rss=', '-p', str(os.getpid())], capture_output=True, text=True).stdout.strip()
    return int(out) * 1024 if out else 0


def main(case_id='asap_06146', arm='C'):
    from ..actors import solve
    from ..common import V6
    manifest = read(ROOT / 'outputs/pilot/manifest.json')
    case = [c for c in manifest['cases'] if c['case_id'] == case_id][0]
    original = read(ROOT / 'outputs/pilot/trials' / case_id / arm / 'result.json')
    provider = ReplayProvider([d['response'] for d in original['decisions']])
    samples, state = [], {}
    stop = threading.Event()

    def sampler():
        t0 = time.monotonic()
        while not stop.wait(0.25):
            samples.append(dict(t=round(time.monotonic() - t0, 2), rss_gib=round(rss_now() / 2**30, 3), **dict(state)))

    def progress(path_unused=None):
        pass
    threading.Thread(target=sampler, daemon=True).start()
    limits = {**manifest['limits'], 'max_rss_bytes': 16 * 2**30}

    class Tap(ReplayProvider):
        pass
    # Track check counts via the progress file the actor writes.
    out = ROOT / 'outputs/diagnostics/memory_probe'
    started = time.monotonic()

    def watcher():
        import json
        p = out / 'progress.json'
        while not stop.wait(0.5):
            try:
                row = json.loads(p.read_text())
                state.update(checks=row.get('checker_calls'), removed=len(row.get('actions', [])), calls=row.get('llm_calls'))
            except Exception:
                pass
    threading.Thread(target=watcher, daemon=True).start()
    result = solve(case['case_path'], provider, V6 / 'memory/S3.json', 'graph_dfs', shared=read(case['shared_path']),
                   limits=limits, progress_path=out / 'progress.json', physics_variant=manifest['physics_variant'])
    stop.set()
    peak = max(samples, key=lambda s: s['rss_gib']) if samples else None
    write(out / 'memory_probe.json', dict(utc=utc(), case_id=case_id, arm=arm, termination=result['termination'],
                                         checks=result['checker_calls'], removed=len(result['actions']),
                                         peak_ru_maxrss_gib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30, 3),
                                         peak_sample=peak, samples=samples, elapsed=time.monotonic() - started,
                                         note='Replayed preserved responses; not an evaluation rerun.'))
    print('termination', result['termination'], 'checks', result['checker_calls'], 'removed', len(result['actions']), 'peak', peak, flush=True)


if __name__ == '__main__':
    main(*sys.argv[1:])

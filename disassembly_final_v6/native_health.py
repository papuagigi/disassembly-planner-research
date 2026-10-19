"""Separate deterministic replay from native solver resource validity.

Read the actual isolated episode log. Do not rerun or rescore an episode,
change MuJoCo settings, or suppress its warnings. Missing logs are unknown.
"""
from collections import Counter
from pathlib import Path
from .common import read, write, sha, utc


def inspect_log(path):
    path = Path(path)
    if not path.exists():
        return dict(status='UNKNOWN_MISSING_WORKER_LOG', warning_count=None,
                    warning_messages={}, warning_free_observed=False)
    warnings = Counter()
    for line in path.read_text(errors='replace').splitlines():
        if line.startswith('WARNING:'):
            # Native MuJoCo warnings start this way. Preserve the message,
            # excluding per-occurrence timing/contact counts for grouping.
            message = line.split(' Time = ', 1)[0].split('(ncon = ', 1)[0].strip()
            warnings[message] += 1
    return dict(status='NATIVE_ENGINE_WARNINGS_RECORDED' if warnings else 'NO_NATIVE_WARNINGS_RECORDED',
                warning_count=sum(warnings.values()), warning_messages=dict(warnings),
                warning_free_observed=not warnings, worker_log_sha256=sha(path))


def audit(folder):
    folder = Path(folder)
    result = folder / 'result.json'
    value = inspect_log(folder / 'worker.log')
    episode=read(result);error=episode.get('error') or {}
    message=error.get('message','').lower()
    native_error=error.get('type')=='FatalError' or any(term in message for term in
        ['mj_stackalloc','arena memory','mesh volume is too small','mass and inertia of moving bodies'])
    if native_error:
        value.update(status='NATIVE_ENGINE_ERROR_RECORDED',warning_free_observed=False,
                     native_error=dict(type=error.get('type'),message=error.get('message')))
    value.update(utc=utc(), result_sha256=sha(result), no_model_calls=True,
                 scope='Observed native episode warnings only; not a proof of physical fidelity. '
                       'Deterministic replay can reproduce a solver-overflow error. '
                       'Original episode score, costs and logs remain unchanged.')
    output = folder / 'engine_health.json'
    if output.exists():
        prior = read(output)
        assert prior['result_sha256'] == value['result_sha256']
        assert prior.get('worker_log_sha256') == value.get('worker_log_sha256')
        return prior
    write(output, value, exclusive=True)
    return value


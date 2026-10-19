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


def failure_class(result,health,worker_log=None):
    """Observed mechanism; never infer planner impossibility from engine failure."""
    text=Path(worker_log).read_text(errors='replace') if worker_log and Path(worker_log).exists() else ''
    error=(result.get('error') or {}).get('message','')
    combined=(text+'\n'+error).lower()
    if 'mj_stackalloc' in combined or 'arena memory' in combined or 'too many contacts' in combined:
        return 'mujoco_resource_failure_or_warning'
    if any(term in combined for term in ['mesh volume is too small','inertia must be','mass and inertia of moving bodies']):
        return 'mujoco_model_compile_failure'
    if health['status']=='NATIVE_ENGINE_WARNINGS_RECORDED':return 'mujoco_other_native_warning'
    if 'resident-memory ceiling' in error:return 'actor_memory_budget_exhausted'
    if result.get('success'):return 'raw_goal_reached'
    termination=result.get('termination','unknown')
    if termination=='execution_or_provider_error':
        return 'execution_or_provider_error_requires_raw_log'
    if termination=='episode_worker_failed_or_hard_timeout':return 'worker_failure_or_hard_timeout'
    if termination in ('wall_time_budget_exhausted','check_budget_exhausted','call_budget_exhausted','search_exhausted','limit'):
        return 'planner_'+termination
    return termination

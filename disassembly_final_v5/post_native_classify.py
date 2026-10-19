"""Post-score observed failure mechanisms;no episode outcome is changed."""
from pathlib import Path

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
    if health['status']=='NATIVE_ENGINE_ERROR_RECORDED':return 'mujoco_other_native_error'
    if 'resident-memory ceiling' in error:return 'actor_memory_budget_exhausted'
    if result.get('success'):return 'raw_goal_reached'
    termination=result.get('termination','unknown')
    if termination=='execution_or_provider_error':
        return 'execution_or_provider_error_requires_raw_log'
    if termination=='episode_worker_failed_or_hard_timeout':return 'worker_failure_or_hard_timeout'
    if termination in ('wall_time_budget_exhausted','check_budget_exhausted','call_budget_exhausted','search_exhausted','limit'):
        return 'planner_'+termination
    return termination

"""Separate measured physical failures from operational resource stops."""
from collections import Counter


def eligibility(result,native_health,physical_audit_status):
    reasons=Counter(t.get('reason') for t in result.get('trace',[]))
    failure_count=sum(reasons[k] for k in ['path_collision','unstable_remainder'])
    error=result.get('error') or {}
    memory_limited='resident-memory ceiling' in error.get('message','')
    native_ok=bool(native_health.get('warning_free_observed'))
    replay_ok=physical_audit_status in ('PASS','PASS_VERIFIED_PREFIX')
    if not native_ok:
        excluded='Native engine warning/error or unknown native health;not physical failure evidence.'
    elif not replay_ok:
        excluded='Physical event replay has not verified the recorded prefix.'
    elif not failure_count:
        excluded='No observed collision or unstable-remainder rejection;no new failure-repair procedure.'
    else:
        excluded=None
    return dict(usable=excluded is None,excluded_reason=excluded,
        observed_physical_failure_queries=failure_count,
        physical_feedback_counts=dict(reasons),physical_prefix_replay=physical_audit_status,
        termination=result.get('termination'),recorded_error=error or None,
        actor_memory_limited=memory_limited,
        resource_stop_is_not_physical_failure=True,
        scope='Only completed verified physical feedback may support a procedure. '
              'An operational stop is never a collision/support-failure label. '
              'A verified physical-failure prefix may remain usable after a resource stop.')

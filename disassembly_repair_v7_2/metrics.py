"""v7.2 metrics = v7 metrics + cached rejections, API deadline stops and native engine errors."""
from __future__ import annotations

from disassembly_repair_v7.metrics import summarize as v7_summarize, classify  # noqa: F401


def native_engine_errors(result):
    texts = [str(result.get('error') or '')] + [str(d.get('execution_error') or '') for d in result.get('decisions', [])]
    return sum(1 for t in texts if 'mj_' in t or 'FatalError' in t)


def summarize(result):
    m = v7_summarize(result)
    rec = result.get('recovery_state', {}) or {}
    m['cached_rejections'] = len(rec.get('cached_rejections', []))
    m['deadline_stops'] = len(rec.get('deadline_stops', []))
    m['native_engine_errors'] = native_engine_errors(result)
    if m['native_engine_errors'] and m['termination_class'] in ('planner_or_schema_error', 'other_limit'):
        m['termination_class'] = 'native_engine_resource'
    m['physics_variant'] = result.get('physics_variant')
    m['v7_version'] = result.get('v7_version')
    return m

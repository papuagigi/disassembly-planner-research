"""v7 episode metrics and termination taxonomy (defined before pilot outcomes)."""
from __future__ import annotations
from collections import Counter

TERMINATION_CLASS = {
    'goal_reached': 'success',
    'wall_time_budget_exhausted': 'time_budget',
    'check_budget_exhausted': 'physics_check_budget',
    'call_budget_exhausted': 'model_call_budget',
    'no_progress_stop': 'no_progress_rule',
    'search_exhausted': 'search_exhausted_within_episode',
    'execution_budget_exhausted': 'generated_code_budget',
}


def classify(result):
    term = result.get('termination')
    err = result.get('error') or {}
    if term in TERMINATION_CLASS:
        return TERMINATION_CLASS[term]
    text = (err.get('type', '') + ' ' + err.get('message', '')).lower()
    if 'provider' in text or 'codex' in text or 'timeout' in text and 'model' in text:
        return 'provider_error'
    if 'resident-memory' in text or 'memorylimit' in text:
        return 'memory_guard'
    if 'prompt_byte' in text or 'response_byte' in text:
        return 'prompt_or_response_byte_cap'
    if term == 'limit':
        return 'other_limit'
    if term == 'episode_worker_failed_or_hard_timeout':
        return 'worker_failure'
    return 'planner_or_schema_error'


def summarize(result):
    trace = result.get('trace', [])
    rec = result.get('recovery_state', {}) or {}
    events = rec.get('events', [])
    total = result.get('total_part_count') or 0
    required = result.get('required_removals', max(1, total - 1))
    final = len(result.get('actions', []))
    best = max([final] + [total - len(t.get('remaining_after', [])) for t in trace if t.get('remaining_after') is not None])
    committed, rejected, revisits, dup_rejected = set(), set(), 0, 0
    for t in trace:
        key = (t.get('physical_state_key_before'), t.get('part_id'), t.get('direction'))
        if t.get('committed'):
            revisits += key in committed
            committed.add(key)
        elif not t.get('valid'):
            dup_rejected += key in rejected
            rejected.add(key)
    restores = [e for e in events if e.get('operation') == 'restore' and e.get('status') == 'completed']
    usage = result.get('token_usage', {}) or {}
    decisions = result.get('decisions', [])
    unknown_usage = sum(1 for d in decisions if d.get('metadata') is not None and not (d['metadata'].get('usage') or {}))
    turns = result.get('turn_progress', [])
    return dict(
        case_id=result.get('case_id'), condition=result.get('condition'), success=bool(result.get('success')),
        termination=result.get('termination'), termination_class=classify(result),
        required_removed=required, final_removed=final, best_removed=best,
        final_progress=final / max(1, required), best_progress=best / max(1, required),
        checks=result.get('checker_calls', 0), failed_checks=sum(1 for t in trace if not t.get('valid')),
        failure_causes=dict(Counter(t.get('reason') for t in trace if not t.get('valid'))),
        first_valid_action_check=next((t.get('checker_call') for t in trace if t.get('valid')), None),
        accepted_removals=sum(1 for t in trace if t.get('committed')),
        accepted_edge_revisits=revisits, repeated_rejected_queries=dup_rejected,
        guarded_requests=len(rec.get('guarded_requests', [])),
        restores=len(restores),
        restores_with_state_change=sum(1 for e in restores if e.get('state_key_before') != e.get('state_key_after')),
        restores_without_state_change=sum(1 for e in restores if e.get('state_key_before') == e.get('state_key_after')),
        checkpoints=len(rec.get('checkpoints', {})),
        auto_checkpoints=sum(1 for a in rec.get('auto_checkpoints', []) if a.get('created')),
        llm_calls=result.get('llm_calls', 0),
        no_progress_calls=(sum(1 for t in turns if not t.get('progress')) if result.get('architecture') == 'code' else None),
        call_reasons=dict(Counter(d.get('call_reason') for d in decisions)),
        input_tokens=usage.get('input_tokens', 0), cached_input_tokens=usage.get('cached_input_tokens', 0),
        output_tokens=usage.get('output_tokens', 0),
        total_tokens=usage.get('input_tokens', 0) + usage.get('output_tokens', 0),
        unknown_usage_calls=unknown_usage,
        elapsed_seconds=result.get('elapsed_seconds', 0.), execution_steps=result.get('execution_steps', 0),
        document_reads=len(result.get('document_reads', [])),
        error=result.get('error'))

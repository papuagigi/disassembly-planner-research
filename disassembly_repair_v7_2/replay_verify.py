"""v7.2 replay verifier: copy of disassembly_repair_v7/replay_verify.py that also replays cached rejections.

Original: v7 independent replay verifier (adapted copy of disassembly_final_v6/post_evidence.py).

Re-executes every recorded API event of a finished v7 episode with the real
simulator and the v7 LedgerAPI, asserting the same trace fields, state keys and
charged checks. Differences from v6: guarded dead-end requests must replay as
guarded (no physics, no trace row); checkpoint metadata is compared through the
mapped handle because v7 deduplicates exact-state checkpoints. No model call.
"""
from __future__ import annotations
import math

from disassembly_real_v3.simulator import FullDisassemblySim
from disassembly_hybrid.graph import physical_state_key

from .common import read, sha, utc, write
from disassembly_repair_v7.shared_api import GUARD_REASON
from .shared_api import HardenedAPI as LedgerAPI, CACHE_REASON_TAG

FIELDS = ('valid', 'reason', 'part_id', 'direction', 'committed', 'blockers', 'stability', 'remaining_before', 'remaining_after',
          'physical_state_key_before', 'physical_state_key_after', 'path_samples', 'physics_steps')


def equal(a, b, path='root'):
    if isinstance(a, dict):
        assert isinstance(b, dict) and set(a) == set(b), (path, 'keys')
        for k in a:
            equal(a[k], b[k], path + '.' + k)
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), (path, 'length')
        for i, (x, y) in enumerate(zip(a, b)):
            equal(x, y, path + f'[{i}]')
    elif isinstance(a, float):
        assert isinstance(b, (int, float)) and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-10), (path, a, b)
    else:
        assert a == b, (path, a, b)


def replay_result(result_path, *, shared_path=None, output=None, capture=False, allow_incomplete=False, sim=None):
    original = read(result_path)
    from disassembly_repair_v7.physics_variants import apply as apply_physics
    apply_physics(original.get('physics_variant'))  # replay under the episode's own physics condition
    cp = original['case_path']
    shared = read(shared_path) if shared_path else None
    max_checks = original['limits']['max_checks']
    sim = sim or FullDisassemblySim(cp, max_checks=max_checks, state=shared['state'] if shared else None, capture=capture)
    api = LedgerAPI(sim, recovery_state=shared['recovery_state'] if shared else None, max_checks=max_checks,
                    max_checkpoints=original['limits']['max_checkpoints'], max_restores=original['limits']['max_restores'])
    skip = len(shared['recovery_state']['events']) if shared else 0
    handles = {h: h for h in (shared['recovery_state']['checkpoints'] if shared else {})}
    count = restores = guarded = 0
    seed_trace_count = len(shared['state']['trace']) if shared else 0
    events, failure_frames, restore_frames, unfinished = [], [], [], []
    recorded = original['recovery_state']['events'][skip:]
    new_trace_count = len(original['trace']) - seed_trace_count
    for offset, event in enumerate(recorded):
        assert physical_state_key(sim.export_state()) == event['state_key_before'], ('before', event['event_index'])
        op = event['operation']
        error = None
        uncharged_error = event.get('status') == 'error' and event['checks_after'] == event['checks_before']
        is_guard = event.get('guard') in (GUARD_REASON, CACHE_REASON_TAG)
        if op in ('check', 'remove') and not is_guard and count >= new_trace_count and not uncharged_error:
            assert allow_incomplete and offset == len(recorded) - 1 and event.get('status') in ('started', 'error'), ('unrecorded tail', event)
            unfinished.append(event)
            if capture:
                sim._record_frame('검사 중 시간 종료 · 결과 없음 · 검사 비용 유지', advance=.3)
                sim.frames[-1].update(phase='unfinished_reserved_check', stage='planner', api_event_index=event['event_index'])
            break
        try:
            if op == 'checkpoint':
                h = api.checkpoint()
                handles[event['handle']] = h
                expected = original['recovery_state']['checkpoints'].get(event['handle'], {}).get('metadata')
                actual = api._recovery['checkpoints'][h]['metadata']
                if expected:
                    for key in ['state_key', 'remaining_parts', 'removed_count', 'support_edges', 'accepted_action_prefix']:
                        if key in expected:
                            equal(expected[key], actual[key], 'checkpoint.' + key)
            elif op == 'restore':
                api.restore(handles.get(event['handle'], event['handle']))
                restores += 1
                if capture:
                    sim._record_frame('Checkpoint 복원 · 비용 유지', advance=.3)
                    sim.frames[-1].update(phase='restore', stage='planner', api_event_index=event['event_index'])
                    restore_frames.append(len(sim.frames) - 1)
            elif op in ('check', 'remove'):
                before_frames, before_trace = len(sim.frames), len(sim.trace)
                result = getattr(api, op)(event['part_id'], event['direction'])
                if is_guard:
                    expected_reason = GUARD_REASON if event.get('guard') == GUARD_REASON else event.get('reason')
                    assert result['reason'] == expected_reason and len(sim.trace) == before_trace, ('guard replay', event['event_index'])
                    guarded += 1
                    if capture:
                        sim._record_frame(('막다른 자식 상태 재진입 차단' if event.get('guard') == GUARD_REASON else '같은 상태의 거부 결과 재사용') + ' · 물리 검사 없음 · ' + str(event['part_id']) + ' ' + str(event['direction']), advance=.2)
                        sim.frames[-1].update(phase='guarded_request', stage='planner', api_event_index=event['event_index'])
                else:
                    count += 1
                    expected = original['trace'][seed_trace_count + count - 1]
                    actual = sim.trace[-1]
                    for key in FIELDS:
                        if key in expected:
                            equal(expected[key], actual[key], 'trace.' + key)
                    if capture:
                        sim._record_frame(('제거 승인' if result['committed'] else '검사 통과' if result['valid'] else '검사 거절') + ' · ' + event['part_id'] + ' ' + event['direction'] + ' · ' + result['reason'], advance=.25)
                        for frame in sim.frames[before_frames:]:
                            frame.update(stage='planner', api_event_index=event['event_index'])
                        if not result['valid']:
                            failure_frames.append(len(sim.frames) - 1)
                            sim.frames[-1]['phase'] = 'rejected_check'
                        events.append(dict(frame=len(sim.frames) - 1, time=sim.clock, type=result['reason'], part_id=result['part_id'],
                                           direction=result['direction'], message=sim.frames[-1]['label']))
            else:
                raise ValueError('Unsupported recorded operation ' + op)
        except BaseException as exc:
            error = exc
            if event.get('status') != 'error':
                raise
        if event.get('status') == 'error':
            assert error is not None
            names = {event['error']['type'], type(error).__name__}
            assert len(names) == 1 or names == {'BudgetLimit', 'RecoveryBudgetLimit'}, ('API error type', names)
        else:
            assert error is None
        assert physical_state_key(sim.export_state()) == event['state_key_after'], ('after', event['event_index'])
        assert sim.checks == event['checks_after'], ('cost', event['event_index'])
    assert len(sim.trace) == len(original['trace'])
    equal(original['state']['remaining'], sim.remaining, 'final remaining')
    reserved = original['checker_calls'] - sim.checks
    assert reserved == 0 or (allow_incomplete and len(unfinished) == 1 and reserved == 1), ('cost', sim.checks, original['checker_calls'])
    receipt = dict(status='PASS_VERIFIED_PREFIX' if unfinished else 'PASS', created_utc=utc(), result_sha256=sha(result_path),
                   case_sha256=sha(cp), physical_queries_replayed=count, guarded_requests_replayed=guarded,
                   restores_verified=restores, final_physical_state_key=physical_state_key(sim.export_state()),
                   no_model_calls=True, unfinished_query_events=unfinished, charged_unfinished_checks=reserved)
    if output:
        write(output, receipt, exclusive=True)
    return receipt, sim, dict(events=events, failure_frames=failure_frames, restore_frames=restore_frames)

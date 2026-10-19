"""Common, budget-preserving simulator API for all recovery-study planners.

Checkpoint contents are host-owned and never enter generated code. A restore is
hypothetical search state restoration, not a physical reassembly command.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
import uuid


class SharedAPIError(RuntimeError):
    pass


class CheckpointError(SharedAPIError):
    pass


class RecoveryBudgetLimit(SharedAPIError):
    pass


class RecoveryGoalReached(BaseException):
    pass


def physical_state_key(state):
    content = {'remaining': sorted(state['remaining']),
               'poses': {pid: state['poses'][pid] for pid in sorted(state['remaining'])}}
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _case_digest(sim):
    return hashlib.sha256(json.dumps(sim.case, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def enriched_snapshot(sim):
    try:
        from disassembly_recovery.shared_observation import enrich_snapshot
    except ModuleNotFoundError as exc:
        if exc.name != 'disassembly_recovery.shared_observation':
            raise
        return sim.snapshot()
    return enrich_snapshot(sim)


class SharedAPI:
    """Trusted API shared by generated code and the host-managed DFS.

    ``callback`` receives operation_started (physics only) and operation_finished
    events. The latter fires after every state/registry mutation so workers can
    flush the authoritative physical and recovery state before the next action.
    ``raise_goal=False`` lets a host controller stop explicitly on sim.success.
    """
    def __init__(self, sim, recovery_state=None, *, max_checks=None,
                 max_checkpoints=128, max_restores=256, callback=None,
                 raise_goal=False, goal_exception=None, budget_exception=None,
                 observation_builder=None):
        self._sim = sim
        self._max_checks = sim.max_checks if max_checks is None else max_checks
        for label, value in [('max_checks', self._max_checks),
                             ('max_checkpoints', max_checkpoints), ('max_restores', max_restores)]:
            if type(value) is not int or value < 0:
                raise ValueError(label + ' must be a nonnegative integer')
        if self._max_checks > sim.max_checks:
            raise ValueError('API check cap cannot exceed simulator cap')
        self._max_checkpoints, self._max_restores = max_checkpoints, max_restores
        self._callback = callback
        self._raise_goal = bool(raise_goal)
        self._goal_exception = goal_exception or RecoveryGoalReached
        self._budget_exception = budget_exception or RecoveryBudgetLimit
        self._observation_builder = observation_builder or enriched_snapshot
        digest = _case_digest(sim)
        if recovery_state is None:
            self._recovery = {'version': 1, 'episode_id': uuid.uuid4().hex,
                              'case_sha256': digest, 'checkpoints': {}, 'events': [],
                              'restore_attempts': 0, 'restore_count': 0, 'next_event_index': 1}
        else:
            self._recovery = copy.deepcopy(recovery_state)
            r = self._recovery
            required = {'version','episode_id','case_sha256','checkpoints','events',
                        'restore_attempts','restore_count','next_event_index'}
            if not isinstance(r, dict) or not required <= set(r) or r['version'] != 1:
                raise CheckpointError('malformed recovery registry')
            if r['case_sha256'] != digest:
                raise CheckpointError('recovery registry belongs to a different case')
            if not isinstance(r['checkpoints'], dict) or not isinstance(r['events'], list):
                raise CheckpointError('malformed registry or operation log')
            if len(r['checkpoints']) > max_checkpoints or r['restore_attempts'] > max_restores:
                raise CheckpointError('recovery state already exceeds configured limits')
            if r['next_event_index'] != len(r['events']) + 1:
                raise CheckpointError('operation log sequence is inconsistent')
            if any(e.get('event_index') != i for i, e in enumerate(r['events'], 1)):
                raise CheckpointError('operation log event indices are inconsistent')
            for checkpoint in r['checkpoints'].values():
                if checkpoint.get('episode_id') != r['episode_id']:
                    raise CheckpointError('checkpoint belongs to a different episode')

    def export_recovery_state(self):
        """Host-only; absent from the restricted policy method allowlist."""
        return copy.deepcopy(self._recovery)

    def snapshot(self):
        value = copy.deepcopy(self._observation_builder(self._sim))
        value['recovery'] = {
            'checkpoint_count': len(self._recovery['checkpoints']),
            'checkpoints': self.checkpoints(),
            'checkpoint_limit': self._max_checkpoints,
            'restore_attempts_used': self._recovery['restore_attempts'],
            'restore_attempts_remaining': max(0, self._max_restores-self._recovery['restore_attempts']),
            'successful_restores': self._recovery['restore_count'],
            'physical_state_key': physical_state_key(self._sim.export_state()),
            'semantics': 'Hypothetical state restore; checks, trace, and operation history never refunded.',
        }
        return value

    observe = snapshot

    def _begin(self, operation, **details):
        event = {'event_index': self._recovery['next_event_index'],
                 'operation': operation,
                 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                 'state_key_before': physical_state_key(self._sim.export_state()),
                 'state_key_after': None, 'checks_before': self._sim.checks,
                 'checks_after': None, 'status': 'started', **copy.deepcopy(details)}
        self._recovery['events'].append(event)
        self._recovery['next_event_index'] += 1
        return event

    def _finish(self, event, *, error=None, **details):
        event.update(state_key_after=physical_state_key(self._sim.export_state()),
                     checks_after=self._sim.checks,
                     finished_at_utc=datetime.now(timezone.utc).isoformat(),
                     status='error' if error else 'completed', **copy.deepcopy(details))
        if error:
            event['error'] = {'type': type(error).__name__, 'message': str(error)[:1000]}
        if self._callback:
            self._callback({'event': 'operation_finished', 'operation_event': copy.deepcopy(event)})

    def checkpoint(self):
        event = self._begin('checkpoint')
        if len(self._recovery['checkpoints']) >= self._max_checkpoints:
            error = self._budget_exception('checkpoint limit reached')
            self._finish(event, error=error, valid=False)
            raise error
        state = self._sim.export_state()
        handle = uuid.uuid4().hex + uuid.uuid4().hex
        metadata = {'handle': handle, 'creation_event_index': event['event_index'],
                    'state_key': physical_state_key(state),
                    'remaining_parts': list(state['remaining']),
                    'removed_count': len(state['actions'])}
        self._recovery['checkpoints'][handle] = {
            'episode_id': self._recovery['episode_id'], 'metadata': metadata,
            'state': copy.deepcopy({key: state[key] for key in ('remaining','poses','actions')})}
        self._finish(event, handle=handle, valid=True)
        return handle

    def checkpoints(self):
        return [copy.deepcopy(cp['metadata']) for cp in self._recovery['checkpoints'].values()]

    def restore(self, handle=None):
        event = self._begin('restore', handle=handle if isinstance(handle, str) else '<invalid-type>')
        if self._recovery['restore_attempts'] >= self._max_restores:
            error = self._budget_exception('restore attempt limit reached')
            self._finish(event, error=error, valid=False, restored=False)
            raise error
        self._recovery['restore_attempts'] += 1
        if not isinstance(handle, str) or handle not in self._recovery['checkpoints']:
            error = CheckpointError('unknown checkpoint handle or handle from another episode')
            self._finish(event, error=error, valid=False, restored=False)
            raise error
        checkpoint = self._recovery['checkpoints'][handle]
        if checkpoint['episode_id'] != self._recovery['episode_id']:
            error = CheckpointError('checkpoint handle belongs to another episode')
            self._finish(event, error=error, valid=False, restored=False)
            raise error
        current = self._sim.export_state()
        saved = checkpoint['state']
        restored = {**current, **copy.deepcopy(saved)}
        self._sim.restore_state(restored)
        if self._sim.checks != current['checks'] or self._sim.trace != current['trace']:
            raise RuntimeError('restoration unexpectedly changed cumulative physics expenditure')
        self._recovery['restore_count'] += 1
        self._finish(event, valid=True, restored=True,
                     restored_checkpoint_event_index=checkpoint['metadata']['creation_event_index'])
        return self.snapshot()

    def check(self, part_id=None, direction=None):
        return self._operation('check', part_id, direction)

    def remove(self, part_id=None, direction=None):
        return self._operation('remove', part_id, direction)

    def _operation(self, kind, part_id, direction):
        event = self._begin(kind, part_id=part_id, direction=direction)
        if self._sim.checks >= self._max_checks:
            error = self._budget_exception('shared checker budget exhausted')
            self._finish(event, error=error, valid=False, committed=False)
            raise error
        if self._callback:
            self._callback({'event': 'operation_started', 'kind': kind,
                            'action': {'part_id': part_id, 'direction': direction},
                            'checker_call': self._sim.checks + 1,
                            'api_event_index': event['event_index'],
                            'physical_state_key_before': event['state_key_before']})
        try:
            result = getattr(self._sim, kind)(part_id, direction)
        except BaseException as exc:
            self._finish(event, error=exc, valid=False, committed=False)
            raise
        key_after = physical_state_key(self._sim.export_state())
        additions = {'api_event_index': event['event_index'],
                     'physical_state_key_before': event['state_key_before'],
                     'physical_state_key_after': key_after}
        result.update(additions)
        self._sim.trace[-1].update(additions)
        self._finish(event, valid=bool(result.get('valid')),
                     committed=bool(result.get('committed')),
                     reason=result.get('reason'), checker_call=result.get('checker_call'))
        if self._sim.success and self._raise_goal:
            raise self._goal_exception('verified target removal; stop at the goal prefix')
        return copy.deepcopy(result)

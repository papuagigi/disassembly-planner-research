"""Recorded-result oracle for offline regression (no model calls).

ReplaySim subclasses the unchanged evaluation simulator. A query whose exact
(state key, part, direction) appears in a preserved v6 trace of the same CAD is
answered from that record instead of re-running the path sweep. An accepted
recorded removal needs the child poses: they come from preserved checkpoint/
final states when available; otherwise the real simulator recomputes the
removal and the child state key is compared with the recorded one (a
determinism check). Unrecorded queries either raise OracleMiss (strict) or
run real physics (hybrid). Every answer is tagged in replay_log.
"""
from __future__ import annotations
import copy
import time

from disassembly_real_v3.simulator import FullDisassemblySim
from disassembly_recovery.shared_api import physical_state_key

from ..common import KNOWN_V6_CADS, read, v6_trial


class OracleMiss(RuntimeError):
    pass


def load_oracle(case_id, arms='ABC'):
    oracle, poses = {}, {}
    for arm in arms:
        r = read(v6_trial(case_id, arm))
        for t in r['trace']:
            key = (t['physical_state_key_before'], t['part_id'], t['direction'])
            if key in oracle and (oracle[key]['valid'], oracle[key].get('physical_state_key_after')) != (t['valid'], t.get('physical_state_key_after') if t.get('committed') else oracle[key].get('physical_state_key_after')):
                oracle[key]['conflict'] = True
            oracle.setdefault(key, copy.deepcopy(t))
        states = [cp['state'] for cp in r['recovery_state']['checkpoints'].values()] + [r['state']]
        for s in states:
            poses[physical_state_key(s)] = dict(remaining=list(s['remaining']), poses=copy.deepcopy(s['poses']))
    return oracle, poses


class ReplaySim(FullDisassemblySim):
    def __init__(self, case_path, oracle, pose_bank, mode='strict', **kw):
        super().__init__(case_path, **kw)
        assert mode in ('strict', 'hybrid')
        self.oracle, self.pose_bank, self.mode = oracle, pose_bank, mode
        self.replay_log = []
        self._build_cache = {}

    def _build(self, remaining=None, poses=None, gravity=None, friction=None):
        # Offline speed only: the current-state contact model used for support_edges is
        # cached per exact state. Explicit-argument builds (settling) are never cached.
        if remaining is None and poses is None and gravity is None and friction is None:
            key = physical_state_key(self.export_state())
            if key not in self._build_cache:
                self._build_cache[key] = super()._build()
            return self._build_cache[key]
        return super()._build(remaining, poses, gravity, friction)

    def _operation(self, pid, direction, commit):
        key = physical_state_key(self.export_state())
        record = self.oracle.get((key, pid, direction))
        if record is None or record.get('conflict'):
            if self.mode == 'strict':
                raise OracleMiss(f'unrecorded query {key[:8]} {pid} {direction}')
            result = super()._operation(pid, direction, commit)
            self.replay_log.append(dict(source='real_physics_unrecorded', state=key, part_id=pid, direction=direction,
                                        valid=result['valid'], reason=result['reason'], checker_call=result['checker_call']))
            return result
        if record['valid'] and commit:
            child_key = record['physical_state_key_after']
            if child_key in self.pose_bank:
                return self._replayed(record, key, commit, self.pose_bank[child_key], 'recorded_with_recorded_child_pose')
            result = super()._operation(pid, direction, commit)
            new_key = physical_state_key(self.export_state())
            self.replay_log.append(dict(source='real_physics_recorded_accept', state=key, part_id=pid, direction=direction,
                                        valid=result['valid'], recorded_child=child_key, recomputed_child=new_key,
                                        child_key_matches=new_key == child_key, checker_call=result['checker_call']))
            return result
        return self._replayed(record, key, commit, None, 'recorded')

    def _replayed(self, record, key, commit, child, source):
        if self.checks >= self.max_checks:
            raise RuntimeError('checker budget exhausted')
        self.checks += 1
        before = list(self.remaining)
        keep = ('valid', 'reason', 'blockers', 'stability', 'part_id', 'direction', 'path_samples', 'physics_steps',
                'path_mode', 'extraction_collision', 'collision_distance_m', 'extraction_distance_m',
                'resolved_direction_world', 'collision_details')
        result = {k: copy.deepcopy(record.get(k)) for k in keep if k in record}
        result.update(checker_call=self.checks, elapsed_seconds=0.0, replayed=True)
        if record['valid'] and commit:
            self.remaining = list(child['remaining'])
            self.poses = copy.deepcopy(child['poses'])
            self.actions.append(dict(part_id=record['part_id'], direction=record['direction'], stability=record.get('stability')))
        result['committed'] = bool(commit and record['valid'])
        self.trace.append({**copy.deepcopy(result), 'operation': 'remove' if commit else 'check',
                           'remaining_before': before, 'remaining_after': list(self.remaining)})
        self.replay_log.append(dict(source=source, state=key, part_id=record['part_id'], direction=record['direction'],
                                    valid=record['valid'], checker_call=self.checks))
        return copy.deepcopy(result)


def v6_case_path(case_id):
    assert case_id in KNOWN_V6_CADS
    return read(v6_trial(case_id, 'A'))['case_path']


def v6_shared(case_id):
    from ..common import V6
    return read(V6 / 'outputs/input_audit/evaluation' / case_id.split('_')[1] / 'shared.json')

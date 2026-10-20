"""Deterministic synthetic world with the simulator interface used by the APIs.

Physics is replaced by explicit rules, so tests isolate bookkeeping and
scheduling. Nothing here is evidence about real CAD physics.
"""
from __future__ import annotations
import copy
from types import SimpleNamespace

DIRS = ('+x', '-x', '+y', '-y', '+z', '-z')


class FakeSim:
    def __init__(self, parts, rule, max_checks=240, case_id='fake_trap'):
        # parts: {id: dict(mass, fixed, z)}
        self.parts = {pid: dict(id=pid, mass_kg=v['mass'], fixed=v.get('fixed', False),
                                allowed_directions=list(DIRS)) for pid, v in parts.items()}
        self._z = {pid: v.get('z', 0.) for pid, v in parts.items()}
        self.case = dict(id=case_id, target_id=next(p for p, v in parts.items() if not v.get('fixed')),
                         parts=[dict(id=p) for p in parts])
        self.rule = rule
        self.max_checks = max_checks
        self.checks = 0
        self.trace = []
        self.actions = []
        self.remaining = list(parts)
        self.poses = {pid: dict(position=[0., 0., self._z[pid]], quaternion=[1., 0., 0., 0.], velocity=[0.] * 6)
                      for pid in parts}
        self.physics = {}

    @property
    def success(self):
        return len(self.remaining) <= 1

    def export_state(self):
        return copy.deepcopy(dict(remaining=self.remaining, poses=self.poses, checks=self.checks,
                                  trace=self.trace, actions=self.actions))

    def restore_state(self, state):
        self.remaining = list(state['remaining'])
        self.poses = copy.deepcopy(state['poses'])
        self.checks = int(state.get('checks', 0))
        self.trace = copy.deepcopy(state.get('trace', []))
        self.actions = copy.deepcopy(state.get('actions', []))

    def task_progress(self, state=None):
        n = len(self.parts)
        return dict(goal_type='full_disassembly', total_part_count=n, required_removals=n - 1,
                    completed_removals=len(self.actions), remaining_part_count=len(self.remaining),
                    goal_reached=self.success)

    def _build(self, *args, **kwargs):
        return None, SimpleNamespace(contact=[]), {}, {}

    def snapshot(self):
        return dict(case_id=self.case['id'], target_id=self.case['target_id'],
                    remaining_parts=[dict(id=p, bounds=[[0, 0, 0], [1, 1, 1]], center=self.poses[p]['position'],
                                          mass=self.parts[p]['mass_kg'], fixed=self.parts[p]['fixed'],
                                          allowed_directions=list(DIRS)) for p in self.remaining],
                    direction_vectors_world={'+x': [1, 0, 0], '-x': [-1, 0, 0], '+y': [0, 1, 0], '-y': [0, -1, 0],
                                             '+z': [0, 0, 1], '-z': [0, 0, -1]},
                    remaining_checks=self.max_checks - self.checks, **self.task_progress())

    def check(self, pid, direction):
        return self._operation(pid, direction, False)

    def remove(self, pid, direction):
        return self._operation(pid, direction, True)

    def _operation(self, pid, direction, commit):
        if self.checks >= self.max_checks:
            raise RuntimeError('checker budget exhausted')
        self.checks += 1
        before = list(self.remaining)
        valid, reason, blockers = self.rule(frozenset(self.remaining), pid, direction)
        result = dict(valid=valid, reason=reason, blockers=list(blockers), stability=None, part_id=pid,
                      direction=direction, checker_call=self.checks)
        if valid and commit:
            self.remaining = [p for p in self.remaining if p != pid]
            self.actions.append(dict(part_id=pid, direction=direction))
        result['committed'] = bool(valid and commit)
        self.trace.append({**copy.deepcopy(result), 'operation': 'remove' if commit else 'check',
                           'remaining_before': before, 'remaining_after': list(self.remaining)})
        return copy.deepcopy(result)


def trap_world(max_checks=240):
    """base fixed; solution a+z, b+z, t+x. Removing t first makes b impossible."""
    parts = dict(base=dict(mass=5., fixed=True), t=dict(mass=.1, z=.1), a=dict(mass=.2, z=.3), b=dict(mass=.3, z=.2))

    def rule(remaining, pid, d):
        if pid not in remaining or pid == 'base':
            return False, 'unknown_or_removed_part', []
        if pid == 't':
            return (d == '+x'), ('ok' if d == '+x' else 'path_collision'), ([] if d == '+x' else ['base'])
        if pid == 'a':
            return (d == '+z'), ('ok' if d == '+z' else 'path_collision'), ([] if d == '+z' else ['base'])
        if pid == 'b':
            if 't' not in remaining:
                return False, 'unstable_remainder', []
            if 'a' in remaining:
                return False, 'path_collision', ['a']
            return (d == '+z'), ('ok' if d == '+z' else 'path_collision'), ([] if d == '+z' else ['t'])
        return False, 'invalid_arguments', []
    return FakeSim(parts, rule, max_checks=max_checks)


def wide_world(n_parts=12, good=('p07', '+y'), max_checks=120):
    """Many parts; at the root only `good` is removable, later every part leaves by +z."""
    parts = dict(base=dict(mass=9., fixed=True))
    for i in range(n_parts):
        parts['p%02d' % i] = dict(mass=1. + i, z=float(i))

    def rule(remaining, pid, d):
        if pid not in remaining or pid == 'base':
            return False, 'unknown_or_removed_part', []
        if good[0] in remaining:
            ok = (pid, d) == good
        else:
            ok = d == '+z'
        return ok, ('ok' if ok else 'path_collision'), ([] if ok else ['base'])
    return FakeSim(parts, rule, max_checks=max_checks, case_id='fake_wide')

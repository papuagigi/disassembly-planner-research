"""Full-sequence task adapter over the unchanged MuJoCo physical simulator.

Only the task endpoint and public observation change. ``target_id`` is a
deterministic compatibility focus for the frozen target-oriented S5 procedures;
it never denotes an early success condition, a subepisode, or an oracle plan.
The source case and physical state remain unchanged when the focus changes.
"""
from disassembly_mujoco.simulator import DisassemblySim


class FullDisassemblySim(DisassemblySim):
    goal_type = 'full_disassembly'

    @property
    def success(self):
        """A full sequence ends with at most one product part remaining."""
        return len(self.remaining) <= 1

    @property
    def initial_focus_removed(self):
        return self.case['target_id'] not in self.remaining

    @property
    def target_removed(self):
        """Legacy diagnostic: initial focus removed, NOT full-task success."""
        return self.initial_focus_removed

    def focus_target(self, state=None):
        remaining = self.remaining if state is None else state['remaining']
        movable = sorted(pid for pid in remaining if not self.parts[pid].get('fixed', False))
        initial = self.case['target_id']
        return initial if initial in movable else (movable[0] if movable else None)

    def task_progress(self, state=None):
        remaining = self.remaining if state is None else state['remaining']
        total = len(self.parts)
        return {
            'goal_type': self.goal_type,
            'total_part_count': total,
            'required_removals': max(0, total - 1),
            'completed_removals': total - len(remaining),
            'remaining_part_count': len(remaining),
            'terminal_remaining_count': 1,
            'goal_reached': len(remaining) <= 1,
            'initial_focus_id': self.case['target_id'],
            'focus_target_id': self.focus_target(state),
            'initial_focus_removed': self.case['target_id'] not in remaining,
            'fixed_part_ids': sorted(pid for pid, part in self.parts.items() if part.get('fixed', False)),
        }

    def snapshot(self):
        value = super().snapshot()
        value.update(self.task_progress())
        value['target_id'] = self.focus_target()
        value['focus_semantics'] = (
            'Compatibility focus only: initial focus while present, otherwise the '
            'lexicographically first remaining nonfixed string ID. No physical '
            'query, task reset, bank reset, or early success occurs at a focus change.'
        )
        value['goal_semantics'] = (
            'Remove n-1 product parts through verified stable operations, leaving '
            'at most one part. When a single base is anchored, that base remains. '
            'Removing the current focus alone is not success.'
        )
        return value

    observe = snapshot


# Existing orchestrators may request the conventional factory name. It must
# resolve to this task adapter, including independent restricted workers.
DisassemblySim = FullDisassemblySim

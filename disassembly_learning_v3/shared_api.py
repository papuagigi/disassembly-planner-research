"""Same physical/recovery operations, with public past observations on checkpoints.

No reference roles, plans, certification results or future states are exposed.
The extra metadata lets a pure learned procedure identify a removed support and
distinguish an ancestor before its removal from a later equilibrium-stable trap.
"""
import copy

from disassembly_recovery.shared_api import SharedAPI as OriginalAPI, enriched_snapshot


class SharedAPI(OriginalAPI):
    def snapshot(self):
        value = super().snapshot()
        value['accepted_action_prefix'] = [
            {'part_id': a['part_id'], 'direction': a['direction']} for a in self._sim.actions
        ]
        return value

    observe = snapshot

    def checkpoint(self):
        handle = super().checkpoint()
        metadata = self._recovery['checkpoints'][handle]['metadata']
        observation = enriched_snapshot(self._sim)
        metadata['context_schema'] = 'observed_checkpoint_context_v1'
        metadata['support_edges'] = copy.deepcopy(observation.get('support_edges', []))
        metadata['accepted_action_prefix'] = [
            {'part_id': a['part_id'], 'direction': a['direction']} for a in self._sim.actions
        ]
        measured = next((r for r in reversed(self._sim.trace)
                         if r.get('committed') and r.get('physical_state_key_after') == metadata['state_key']), None)
        metadata['last_committed_stability'] = copy.deepcopy(measured.get('stability')) if measured else None
        metadata['stability_scope'] = 'Observed equilibrium after accepted removals; not a future target-removal guarantee.'
        return handle

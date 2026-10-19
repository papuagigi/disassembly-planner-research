"""Role-separated executable memory built on the frozen v1 skill executor.

The host composes order and restore proposals. The generated restore procedure
chooses its checkpoint from observed registry metadata; this module never chooses
a nearest checkpoint or introduces a physical check outside the common API.
"""
from __future__ import annotations

import copy

from disassembly_learning_v1.memory import (
    FEATURES, SkillBank as PreviousSkillBank, create_bank, digest, execute,
    features, validate_skill, write,
)


RUNTIME_SEMANTICS = 'v3_role_composition_1'
ROLES = ('order', 'restore')


def normalize_actions(proposal, previous):
    """Complete a soft ordering, preserving every previously legal candidate."""
    allowed = {(a['part_id'], a['direction']): a for a in previous}
    accepted, seen, dropped = [], set(), []
    malformed = not isinstance(proposal, list)
    for action in proposal if isinstance(proposal, list) else []:
        if (not isinstance(action, dict) or set(action) != {'part_id', 'direction'}
                or not all(isinstance(v, str) for v in action.values())):
            dropped.append({'action': copy.deepcopy(action), 'reason': 'malformed'})
            continue
        key = (action['part_id'], action['direction'])
        if key not in allowed:
            dropped.append({'action': copy.deepcopy(action), 'reason': 'unavailable'})
        elif key in seen:
            dropped.append({'action': copy.deepcopy(action), 'reason': 'duplicate'})
        else:
            accepted.append(copy.deepcopy(allowed[key]))
            seen.add(key)
    appended = len(allowed) - len(seen)
    for action in previous:
        key = (action['part_id'], action['direction'])
        if key not in seen:
            accepted.append(copy.deepcopy(allowed[key]))
            seen.add(key)
    return accepted, {'dropped': dropped, 'malformed_list': malformed,
                      'appended_candidates': appended, 'hard_pruning': False}


class SkillBank(PreviousSkillBank):
    """Select independently by role, then execute base -> order -> restore.

    ``skill_roles`` is bank metadata so retained skill records, including their
    original generated source, can remain byte-for-byte equivalent as JSON data.
    The optional per-record ``role`` field is not authoritative.
    """

    runtime_semantics = RUNTIME_SEMANTICS

    def __init__(self, path_or_bank):
        super().__init__(path_or_bank)
        ids = [skill['id'] for skill in self.bank['skills']]
        roles = self.bank.get('skill_roles')
        if len(ids) != len(set(ids)):
            raise ValueError('Skill IDs must be unique')
        if not isinstance(roles, dict) or set(roles) != set(ids):
            raise ValueError('skill_roles must assign exactly one role to every stored skill')
        if any(role not in ROLES for role in roles.values()):
            raise ValueError('skill_roles values must be order or restore')
        if self.bank.get('runtime_semantics', RUNTIME_SEMANTICS) != RUNTIME_SEMANTICS:
            raise ValueError('Unsupported runtime_semantics')
        self.skill_roles = dict(roles)

    def retrieve_stages(self, observation, history):
        """Recompute applicability for this call; select one procedure per role."""
        tags = set(features(observation, history))
        selected = {role: None for role in ROLES}
        scores = {}
        for index, skill in enumerate(self.bank['skills']):
            if not set(skill['triggers']) <= tags:
                continue
            role = self.skill_roles[skill['id']]
            score = (len(set(skill['triggers'])), index)
            if role not in scores or score > scores[role]:
                scores[role] = score
                selected[role] = skill
        return selected, sorted(tags)

    def apply(self, observation, candidates, history, checkpoints, model_order):
        selected, tags = self.retrieve_stages(observation, history)
        ordered, handle, base_steps, base_error = self.baseline(
            observation, candidates, history, checkpoints, model_order)
        ordered, base_normalization = normalize_actions(ordered, candidates)
        stages = [{
            'role': 'base', 'skill_id': None, 'features': tags,
            'source_sha256': self.bank['base_source_sha256'],
            'execution_steps': base_steps, 'error': copy.deepcopy(base_error),
            'applied': not bool(base_error),
            'input_ordered_actions': copy.deepcopy(candidates),
            'ordered_actions': copy.deepcopy(ordered), 'restore_handle': handle,
            'normalization': base_normalization,
        }]
        retrieval = {
            'runtime_semantics': RUNTIME_SEMANTICS,
            'bank_version': self.version, 'bank_sha256': self.sha256,
            'state_key': observation['state_key'], 'checks_before': len(history),
            'features': tags,
            'selected_skill_ids': {role: skill['id'] if skill else None
                                   for role, skill in selected.items()},
            'applied_skill_id': None, 'applied_skill_ids': [],
            'matched_triggers': [], 'source_sha256': None,
            'error': copy.deepcopy(base_error), 'execution_steps': base_steps,
            'base_execution_steps': base_steps, 'learned_execution_steps': 0,
            'applied': False, 'stages': stages,
        }
        output = {
            'ordered_actions': ordered, 'restore_handle': handle,
            'skill_id': None, 'retrieval': retrieval,
            'execution_steps': base_steps, 'error': copy.deepcopy(base_error),
        }
        if base_error:
            return output

        for role in ROLES:
            skill = selected[role]
            if skill is None:
                continue
            before_order = copy.deepcopy(output['ordered_actions'])
            run = execute(
                skill, observation, before_order, history, checkpoints, model_order,
                max_steps=min(150000, max(0, self.remaining_steps - output['execution_steps'])),
            )
            output['execution_steps'] += run['execution_steps']
            output['skill_id'] = skill['id']
            stage = {
                'role': role, 'skill_id': skill['id'], 'features': tags,
                'matched_triggers': list(skill['triggers']),
                'source_sha256': run['source_sha256'],
                'execution_steps': run['execution_steps'],
                'input_ordered_actions': before_order,
                'proposal': copy.deepcopy(run['output']),
                'error': copy.deepcopy(run['error']), 'applied': False,
            }
            stages.append(stage)
            retrieval.update(
                applied_skill_id=skill['id'], matched_triggers=list(skill['triggers']),
                source_sha256=run['source_sha256'], execution_steps=output['execution_steps'],
                learned_execution_steps=output['execution_steps'] - base_steps,
            )
            if run['error']:
                output['error'] = copy.deepcopy(run['error'])
                retrieval['error'] = copy.deepcopy(run['error'])
                break

            proposal = run['output']
            if role == 'order':
                output['ordered_actions'], normalization = normalize_actions(
                    proposal.get('ordered_actions', []), before_order)
                stage['normalization'] = normalization
                stage['ignored_restore_handle'] = proposal.get('restore_handle', '')
            else:
                # A restore procedure receives the established order as input.
                # Its ordering output cannot replace the ordering procedure.
                stage['ordering_output_ignored'] = True
                stage['ordering_change_ignored'] = proposal.get('ordered_actions', []) != before_order
                proposed_handle = proposal.get('restore_handle', '')
                if proposed_handle and not any(
                        cp.get('handle') == proposed_handle for cp in checkpoints):
                    error = {'type': 'InvalidCheckpoint',
                             'message': 'skill suggested an unavailable checkpoint'}
                    stage['error'] = error
                    output['error'] = copy.deepcopy(error)
                    retrieval['error'] = copy.deepcopy(error)
                    break
                output['restore_handle'] = proposed_handle or output['restore_handle']
            stage.update(applied=True, ordered_actions=copy.deepcopy(output['ordered_actions']),
                         restore_handle=output['restore_handle'])
            retrieval['applied_skill_ids'].append(skill['id'])
            retrieval['applied'] = True
        return output

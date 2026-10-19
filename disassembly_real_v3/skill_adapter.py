"""B's optional callable facade over C's identical frozen v3 skill bank.

No search or physical operation lives here. The generated policy supplies its
candidates and decides whether to execute a returned action or restore hint.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

from disassembly_real_v3.memory import SkillBank

DIRECTIONS = ('+x', '-x', '+y', '-y', '+z', '-z')


def load_bank(value):
    return copy.deepcopy(value) if isinstance(value, dict) else json.loads(Path(value).read_text())


def describe_bank(value):
    bank = SkillBank(load_bank(value))
    return {
        'available': True, 'exports': ['recommend','next_step'],
        'usage': 'step = skills.next_step(candidates, model_order=[]). Explicitly execute step.operation with api; no physical calls occur in the skill.',
        'bank_version': bank.version, 'bank_sha256': bank.sha256,
        'runtime_semantics': bank.runtime_semantics,
        'skill_roles': bank.bank['skill_roles'], 'skills': copy.deepcopy(bank.bank['skills']),
        'active_frontier_id': bank.frontier['id'],
        'semantics': 'Same frozen executable bank as C. Explicit next_step runs reusable frontier bookkeeping and returns a proposal. No automatic search or physical calls.',
    }


class SkillAdapter:
    """A single recommendation recomputes public feedback and charges bank work."""

    def __init__(self, bank, api, sim, execution, max_steps, callback, limit_exception):
        self._bank = SkillBank(load_bank(bank), frontier_state=execution.get("skill_state"))
        self._api, self._sim, self._execution = api, sim, execution
        self._max_steps, self._callback = max_steps, callback
        self._limit_exception = limit_exception

    def recommend(self, candidates, model_order=None):
        return self._call(candidates, model_order, False)

    def next_step(self, candidates, model_order=None):
        result = self._call(candidates, model_order, True)
        if result.get("error"):
            return {"operation":"error", "error":result["error"], "action":{}, "handle":""}
        return copy.deepcopy(result["next_step"])

    def _call(self, candidates, model_order, frontier):
        if len(self._execution['skill_calls']) >= 1000:
            raise self._limit_exception('skill-call log limit exceeded')
        observation = self._api.snapshot()
        known = {p['id'] for p in observation['remaining_parts'] if not p.get('fixed')}
        if not isinstance(candidates, list) or len(candidates) > 50000:
            raise ValueError('candidates must be a bounded list of public part/direction actions')
        seen = set()
        for action in candidates:
            if (not isinstance(action, dict) or set(action) != {'part_id', 'direction'} or
                    not isinstance(action['part_id'], str) or not isinstance(action['direction'], str) or
                    action['part_id'] not in known or action['direction'] not in DIRECTIONS):
                raise ValueError('candidate must name a remaining movable part and one of six directions')
            key = (action['part_id'], action['direction'])
            if key in seen:
                raise ValueError('candidate actions must be unique')
            seen.add(key)
        if model_order is None:
            model_order = []
        if not isinstance(model_order, list):
            raise ValueError('model_order must be a list')
        record = {'name': 'next_step' if frontier else 'recommend', 'application_index': len(self._execution['skill_calls']) + 1,
                  'activation': 'generated_policy',
                  'selected_by_model': True, 'checks_before': self._sim.checks,
                  'checks_after': self._sim.checks, 'state_key': observation['state_key'],
                  'api_event_index_before': len(self._api.export_recovery_state()['events']),
                  'candidate_count': len(candidates), 'input_candidates': copy.deepcopy(candidates),
                  'model_order': copy.deepcopy(model_order), 'restore_applied': False,
                  'bank_sha256': self._bank.sha256, 'execution_steps': 0, 'error': None}
        self._execution['skill_calls'].append(record)
        index = len(self._execution['skill_calls']) - 1
        self._callback({'event': 'skill_start', 'index': index, 'call': copy.deepcopy(record)})
        remaining = max(0, self._max_steps - self._execution['policy_steps'] - self._execution['bank_steps'])
        self._bank.set_execution_budget(remaining)
        previous = sys.gettrace()
        # SkillBank has its own opcode meters. Count those returned steps once;
        # the outer policy meter must not also count the generated <skills> code.
        try:
            sys.settrace(None)
            method = self._bank.plan if frontier else self._bank.apply
            result = method(copy.deepcopy(observation), copy.deepcopy(candidates),
                                      copy.deepcopy(self._sim.trace), self._api.checkpoints(),
                                      copy.deepcopy(model_order))
        finally:
            sys.settrace(previous)
        self._execution['skill_state'] = self._bank.export_state()
        count = result.get('execution_steps', 0)
        if type(count) is not int or count < 0 or count > remaining:
            raise ValueError('bank exceeded its accounted remaining execution allowance')
        self._execution['bank_steps'] += count
        self._execution['steps'] = self._execution['policy_steps'] + self._execution['bank_steps']
        record.update(execution_steps=count, result=copy.deepcopy(result),
                      retrieval=copy.deepcopy(result.get('retrieval', {})),
                      skill_id=result.get('skill_id'), returned_handle=(result.get('next_step',{}).get('handle','') if frontier else result.get('restore_handle', '')),
                      error=copy.deepcopy(result.get('error')),
                      next_step=copy.deepcopy(result.get('next_step')),
                      frontier_state=copy.deepcopy(self._execution['skill_state']),
                      skill_applied=bool(result.get('retrieval', {}).get('applied')))
        self._callback({'event': 'skill_end', 'index': index, 'call': copy.deepcopy(record),
                        'steps': self._execution['steps'], 'bank_steps': self._execution['bank_steps'],
                        'policy_steps': self._execution['policy_steps'], 'skill_state':copy.deepcopy(self._execution['skill_state'])})
        message = str((result.get('error') or {}).get('message', '')).lower()
        if self._execution['steps'] >= self._max_steps:
            raise self._limit_exception('aggregate generated policy and skill instruction budget exhausted')
        if 'opcode limit' in message:
            raise self._limit_exception('bank per-application opcode limit reached: '+str(result['error'].get('message','')))
        return copy.deepcopy(result)

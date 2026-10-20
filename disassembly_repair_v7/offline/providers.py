"""Model-free providers for offline tests. They never contact a model service."""
from __future__ import annotations
import copy


class ReplayProvider:
    """Returns preserved v6 responses in their original call order (not re-conditioned on v7 prompts)."""
    name = 'offline_replay_of_preserved_v6_responses'

    def __init__(self, responses):
        self.responses = [copy.deepcopy(r) for r in responses]
        self.prompts = []
        self.timeout = 120

    def complete(self, prompt, schema, call_index):
        self.prompts.append(prompt)
        if call_index > len(self.responses):
            raise RuntimeError('no preserved response for call %d' % call_index)
        return copy.deepcopy(self.responses[call_index - 1]), dict(provider=self.name, usage={}, offline=True)


class FunctionProvider:
    """Synthetic responses from a Python function of (prompt, schema, call_index)."""
    name = 'offline_synthetic_function_provider'

    def __init__(self, fn):
        self.fn = fn
        self.prompts = []
        self.timeout = 120

    def complete(self, prompt, schema, call_index):
        self.prompts.append(prompt)
        return self.fn(prompt, schema, call_index), dict(provider=self.name, usage={}, offline=True)


def read_then(execute, skill_ids):
    """First call reads the catalog documents; later calls delegate to execute(prompt, call_index)."""
    def fn(prompt, schema, call_index):
        if schema['properties']['operation']['enum'] == ['read_skills']:
            return dict(operation='read_skills', skill_ids=list(skill_ids), code='', ordered_actions=[],
                        applied_skill_ids=[], document_plan=[], summary='read')
        return execute(prompt, call_index)
    return fn

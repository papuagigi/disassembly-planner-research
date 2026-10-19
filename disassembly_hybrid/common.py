"""Shared inputs and charged initial observations for all three arms."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from disassembly_mujoco.simulator import DisassemblySim, DIRECTIONS

MODEL = 'gpt-6-luna'
EFFORT = 'low'
LIMITS = {'max_calls': 4, 'max_checks': 24, 'max_steps': 1000000,
          'timeout_seconds': 480.0}
METHODS = ('code_no_library', 'code_with_library', 'graph_llm_dfs_library')

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def write(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def physical_key(state):
    return digest({'remaining': sorted(state['remaining']),
                   'poses': {p: state['poses'][p] for p in sorted(state['remaining'])}})

def public_evidence(state):
    """Code arms are monotone: one remaining set maps to one reached pose state.

    Only feedback at the CURRENT physical state is called a hard exclusion.
    Earlier failed directions are not promoted to permanent precedence edges.
    """
    key = physical_key(state)
    remaining = set(state['remaining'])
    records = [t for t in state['trace'] if set(t.get('remaining_before', [])) == remaining]
    edges, rejected = [], []
    for t in records:
        if not t.get('valid', False):
            rejected.append({'part_id': t['part_id'], 'direction': t['direction'],
                             'reason': t['reason'], 'state_key': key})
        if t.get('reason') == 'path_collision':
            for blocker in t.get('blockers', []):
                edges.append({'from': blocker, 'to': t['part_id'],
                              'direction': t['direction'], 'state_key': key})
    return {'state_key': key, 'nodes': sorted(remaining), 'edges': edges,
            'rejected_actions': rejected,
            'semantics': 'An edge blocker -> moving part forbids only the observed direction at this exact pose state. Unknown directions remain candidates. These are not universal precedence constraints.'}

def prepare_shared(case_path, max_checks=24):
    """Six target-direction probes, all charged. No accepted removal, no oracle."""
    sim = DisassemblySim(case_path, max_checks=max_checks, capture=False)
    initial = sim.snapshot()
    target = next(p for p in initial['remaining_parts'] if p['id'] == initial['target_id'])
    for direction in DIRECTIONS:
        if direction in target['allowed_directions'] and sim.checks < max_checks:
            sim.check(target['id'], direction)
    state = sim.export_state()
    observation = sim.snapshot()
    observation['directed_blocking_graph'] = public_evidence(state)
    observation['common_probe_feedback'] = copy.deepcopy(state['trace'])
    for record in observation['common_probe_feedback']:
        record.pop('elapsed_seconds', None)
    return state, observation, initial

def neutral_observation_hash(observation):
    """Timing is measured per trial, not a semantic difference in planner input."""
    def scrub(v):
        if isinstance(v, dict):
            return {k: scrub(x) for k, x in v.items() if k not in ('elapsed_seconds',)}
        if isinstance(v, list):
            return [scrub(x) for x in v]
        return v
    return digest(scrub(observation))

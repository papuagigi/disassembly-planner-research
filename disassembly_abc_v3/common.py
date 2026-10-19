"""Matched task state/API/resource upper bounds for the S5 architecture study."""
import copy
import json
from pathlib import Path

from disassembly_mujoco.simulator import DisassemblySim, DIRECTIONS
from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_learning_v3.memory import digest, write
from disassembly_hybrid.common import neutral_observation_hash

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
MODEL = 'gpt-6-luna'
EFFORT = 'low'
LIMITS = dict(max_calls=8, max_checks=240, max_steps=10000000,
              timeout_seconds=480., max_checkpoints=128, max_restores=256)
CONDITIONS = ('A_code_no_library', 'B_code_with_library', 'C_graph_llm_dfs_library')

def read(path):
    return json.loads(Path(path).read_text())

def prepare(case, track):
    assert track in ('normal', 'seeded')
    sim = DisassemblySim(case['case_path'], max_checks=LIMITS['max_checks'])
    api = SharedAPI(sim, max_checks=LIMITS['max_checks'],
                    max_checkpoints=LIMITS['max_checkpoints'], max_restores=LIMITS['max_restores'])
    api.checkpoint()
    if track == 'seeded':
        for action in case['seed_setup']['prefix_actions']:
            assert api.remove(**action).get('committed')
            api.checkpoint()
        assert api.remove(**case['seed_setup']['wrong_action']).get('committed')
    for direction in DIRECTIONS:
        api.check(sim.case['target_id'], direction)
    observation = api.snapshot()
    observation['common_probe_feedback'] = copy.deepcopy(observation['current_state_feedback'])
    return dict(state=sim.export_state(), observation=observation,
                recovery_state=api.export_recovery_state())

def solve(case, condition, provider, shared, bank_path=None):
    assert condition in CONDITIONS
    kwargs = dict(initial_state=shared['state'], initial_observation=shared['observation'],
                  recovery_state=shared['recovery_state'], **LIMITS)
    if condition == 'C_graph_llm_dfs_library':
        from .memory import SkillBank
        from .controller import solve as fixed_solve
        return fixed_solve(case['case_path'], provider, SkillBank(bank_path), llm_rank=True, **kwargs)
    from .code_actor import solve_code
    return solve_code(case['case_path'], provider,
                      library=bank_path if condition == 'B_code_with_library' else None, **kwargs)

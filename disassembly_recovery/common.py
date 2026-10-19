import copy
from pathlib import Path
from disassembly_hybrid.common import digest, write, neutral_observation_hash
from disassembly_mujoco.simulator import DisassemblySim, DIRECTIONS
from .shared_api import SharedAPI

MODEL = 'gpt-6-luna'
EFFORT = 'low'
LIMITS = {'max_calls':8,'max_checks':120,'max_steps':10000000,'timeout_seconds':480.0,
          'max_checkpoints':128,'max_restores':256}
METHODS = ('code_no_library','code_with_library','graph_llm_dfs_library')


def prepare_shared(case_path, max_checks=120, seed_action=None):
    sim = DisassemblySim(case_path,max_checks=max_checks)
    api = SharedAPI(sim)
    root = api.checkpoint()
    if seed_action:
        result = api.remove(seed_action['part_id'],seed_action['direction'])
        if not result['valid'] or not result['committed']:
            raise ValueError('Seed action is not an accepted physical removal')
    for direction in DIRECTIONS:
        api.check(sim.case['target_id'],direction)
    obs = api.snapshot()
    obs['common_probe_feedback'] = copy.deepcopy(obs['current_state_feedback'])
    return sim.export_state(), obs, api.export_recovery_state()

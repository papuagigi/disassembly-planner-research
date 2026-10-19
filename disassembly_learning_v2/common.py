"""Matched initial states and caps. No certificate is sent to the planner."""
import copy
import json
from pathlib import Path
from disassembly_mujoco.simulator import DisassemblySim, DIRECTIONS
from disassembly_recovery.shared_api import SharedAPI
from disassembly_learning_v1.memory import SkillBank, digest, write

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
MODEL = 'gpt-6-luna'
EFFORT = 'low'
LIMITS = dict(max_calls=8, max_checks=240, max_steps=10000000,
              timeout_seconds=480., max_checkpoints=128, max_restores=256)
CONDITIONS = ('S1_off', 'S1_on', 'S3_off', 'S3_on')

def read(path):
    return json.loads(Path(path).read_text())

def prepare(case, track):
    assert track in ('normal', 'seeded')
    sim = DisassemblySim(case['case_path'], max_checks=LIMITS['max_checks'])
    api = SharedAPI(sim, max_checks=LIMITS['max_checks'],
                    max_checkpoints=LIMITS['max_checkpoints'], max_restores=LIMITS['max_restores'])
    api.checkpoint()
    if track == 'seeded':
        for action in case['seed_setup'].get('prefix_actions', []):
            result = api.remove(**action)
            assert result.get('committed'), ('Invalid seeded prefix', result)
            api.checkpoint()
        result = api.remove(**case['seed_setup']['wrong_action'])
        assert result.get('committed'), ('Wrong branch must be a physically accepted removal', result)
    for direction in DIRECTIONS:
        api.check(sim.case['target_id'], direction)
    observation = api.snapshot()
    observation['common_probe_feedback'] = copy.deepcopy(observation['current_state_feedback'])
    return dict(state=sim.export_state(), observation=observation, recovery_state=api.export_recovery_state())

def solve_case(case, bank, track, folder, provider=None, llm_rank=False, prepared=None):
    from disassembly_learning_v1.controller import solve
    shared = prepared or prepare(case, track)
    result = solve(case['case_path'], provider, SkillBank(bank), llm_rank=llm_rank,
        initial_state=shared['state'], initial_observation=shared['observation'],
        recovery_state=shared['recovery_state'], **LIMITS)
    result.update(track=track, preparation_checks=shared['state']['checks'])
    if folder is not None:
        write(Path(folder)/'result.json', result)
    return result

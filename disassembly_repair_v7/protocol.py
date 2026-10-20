"""v7 pilot freeze: code, contract, bank, selection rule and metrics before pilot geometry.

freeze() must run after the regression stage and before pilot_inputs.select().
verify() re-hashes every frozen file before each pilot episode.
"""
from __future__ import annotations
from .common import ROOT, WORKSPACE, V6, read, sha, utc, write

P0_FREEZE = ROOT / 'outputs/protocol/freeze.json'  # superseded before any pilot episode
FREEZE = ROOT / 'outputs/protocol/freeze_v7.1_P2.json'
PHYSICS = 'P2_persist_up_to_stable_penetration'
V7_FILES = ['__init__.py', 'common.py', 'contracts.py', 'shared_api.py', 'runtime.py', 'controller.py', 'actors.py', 'driver.py',
            'campaign.py', 'metrics.py', 'protocol.py', 'pilot_inputs.py', 'physics_audit.py', 'feasibility.py', 'physics_variants.py', 'replay_verify.py',
            'data_tools/convert_cad.py', 'outputs/protocol/conversion_pilot.json', 'outputs/protocol/pilot_candidates.json',
            'outputs/protocol/pilot_backup_candidates.json', 'analysis/PHYSICS_DECISION.md', 'analysis/physics/p2_adoption_checks.json']
DEPENDENCIES = ['disassembly_final_v6/contracts.py', 'disassembly_final_v6/controller.py', 'disassembly_final_v6/documents.py',
                'disassembly_final_v6/native_health.py', 'disassembly_final_v6/common.py',
                'disassembly_real_v3/simulator.py', 'disassembly_real_v3/source_collision.py', 'disassembly_real_v3/code_actor.py',
                'disassembly_real_v2/simulator.py', 'disassembly_real_v1/simulator.py', 'disassembly_mujoco/simulator.py',
                'disassembly_learning_v3/shared_api.py', 'disassembly_recovery/shared_api.py', 'disassembly_recovery/shared_observation.py',
                'disassembly_hybrid/graph.py', 'disassembly_planner_2d/planner2d/code_runtime.py',
                'disassembly_planner_2d/planner2d/code_worker.py', 'disassembly_planner_2d/planner2d/llm.py',
                'disassembly_docskills_v1/data_tools/inventory_sources.py']
ARM_ORDER_RULE = 'case index i (selection order) runs arms ABC rotated by i mod 3: ABC, BCA, CAB (v6 rule)'


def freeze(regression_summary_paths):
    if FREEZE.exists():
        return verify()
    from .contracts import LIMITS, MODEL, EFFORT, ARMS, VERSION, NO_PROGRESS_LIMIT
    from disassembly_final_v6.documents import DocumentBank
    bank = DocumentBank(V6 / 'memory/S3.json')
    v6_freeze = read(V6 / 'outputs/protocol/freeze.json')
    assert bank.sha256 == v6_freeze['bank_sha256'] and bank.content_sha256 == v6_freeze['bank_content_sha256']
    assert LIMITS == v6_freeze['limits'] and MODEL == v6_freeze['model'] and EFFORT == v6_freeze['reasoning_effort']
    paths = [ROOT / p for p in V7_FILES] + [WORKSPACE / p for p in DEPENDENCIES]
    paths += [V6 / 'memory/S0.json', V6 / 'memory/S3.json']
    for row in bank.manifest['skills']:
        q = V6 / 'memory' / row['path']
        paths.append(q)
        if (q.parent / 'references/admission.json').exists():
            paths.append(q.parent / 'references/admission.json')
    value = dict(status='FROZEN_BEFORE_ANY_PILOT_EPISODE', utc=utc(), v7_version=VERSION + '.1-P2', physics_variant=PHYSICS,
                 supersedes=dict(path=str(P0_FREEZE), sha256=sha(P0_FREEZE), reason='Physics decision (analysis/PHYSICS_DECISION.md) made before any pilot episode; P0 freeze never used for an episode.'),
                 pilot_inputs_opened_before_this_freeze='20 primary candidates were converted under the P0 freeze; only exclusion statuses and one P0 reference/lock record (03107) were inspected; no planner ran.',
                 model=MODEL, reasoning_effort=EFFORT,
                 limits=LIMITS, arms=ARMS, bank_sha256=bank.sha256, bank_content_sha256=bank.content_sha256,
                 bank_identical_to_v6_S3=True, no_progress_limit=NO_PROGRESS_LIMIT,
                 sha256={str(p.resolve()): sha(p) for p in paths},
                 regression_summaries={str(p): sha(p) for p in regression_summary_paths},
                 pilot=dict(target_cases=3, arms_per_case=3, planned_episodes=9, arm_order_rule=ARM_ORDER_RULE,
                            physics=PHYSICS, backup_pool='official test, never opened, 5-10 parts, used only if primary yields < 3',
                            one_planner_at_a_time=True, no_reruns=True, no_outcome_driven_changes=True,
                            no_reference_given_to_planners=True, selection='pilot_inputs.py docstring; candidates frozen in outputs/protocol/pilot_candidates.json',
                            background_heavy_processes_during_episodes=False,
                            stop_rule='Run each selected case once per arm; report all outcomes; no favorable-result loop.'),
                 metrics='metrics.py summarize/classify', interpretation_limits=[
                     'v6->v7 changes several mechanisms at once; a v7 result is not a causal estimate of SKILL.md alone.',
                     'B-C differs in search architecture and scheduling, not only memory.',
                     'Three CADs x one episode per arm is a small pilot, not industrial validation.'])
    write(FREEZE, value, exclusive=True)
    return value


def verify():
    value = read(FREEZE)
    for name, expected in value['sha256'].items():
        assert sha(name) == expected, ('Frozen file changed', name)
    return value

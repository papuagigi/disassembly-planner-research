"""A/B share the same observations, restore API and cumulative resource caps."""
import copy
import hashlib
import json
import time
from pathlib import Path
from disassembly_mujoco.agent import CodexCLIProvider, ProviderError, CODE_SCHEMA, API_SPEC
from disassembly_mujoco.simulator import DisassemblySim
from disassembly_hybrid.common import neutral_observation_hash, digest
from .runtime import run_code, validate_source
from .shared_api import SharedAPI

# Retain the restricted-language contract, replace obsolete API/budget guidance.
SPEC = API_SPEC.replace('same shared 24 checker calls','same shared checker calls')
SPEC = SPEC.replace('shared 24 checker calls','shared checker calls')
SPEC = SPEC.replace('A stability rejection may require removing a supported part first.',
    'A stability rejection means a required support may have been removed. Preserve alternate supports of target-supported loads. Removing a falling load is not automatically the right repair.')
SPEC = SPEC.replace('50000-opcode episode budget','cumulative opcode episode budget shown in limits')
SPEC += '''\nAdditional API, IDENTICAL in A/B/C:
api.checkpoint() -> opaque string handle, saves remaining parts, exact poses/velocities and current path.
api.checkpoints() -> metadata list: handle,state_key,remaining_parts,removed_count,creation_event_index.
api.restore(handle) -> snapshot, restores saved physical state/path. NEVER refunds checks or failures.
Checkpoint handles persist across model turns; generated variables do not. Obtain handles via checkpoints().
The host does NOT implement search or automatically restore in the code conditions. You must call these APIs.
An accepted removal can lead to a dead end. Keep checkpoints before removals and backtrack when needed.
Every accepted removal must remain stable, including target removal. All parts left behind still matter.
snapshot includes state_key, exact-state rejection graph, current_state_feedback and history_feedback.
Hard-filter only exact-state failed directions. Old state failures can inform priorities, not prove impossibility.
support_edges are current vertical MuJoCo contact relations, not a solved order or future physics oracle.
If the target supports a load, other supporters of that load can be needed for the eventual target removal.
If a previous move leaves target the sole support, consider restoring an earlier checkpoint; this is a heuristic,
not proof of impossibility. Checkpoints describe all saved branches. No seed action is labelled for you.
All three conditions have identical observations and resource UPPER BOUNDS listed below. A has no external
reusable skill library; it can still write functions/search, use feedback and memory within this episode.
When reusable_library contains exports, a REAL skills object is bound in your execution environment.
Its functions are already defined; do not import or paste the library source. Call the exported function,
for example skills.recover_target(api), directly at the top level. Prefer reusing an applicable tested
procedure over writing a replacement, but you choose whether to call it. Its internal operations use
exactly the same public API and budgets. A no-library episode has no skills object or reusable code.
No model weights change during the experiment, and no episode learns from another evaluation episode.
'''


def load_library():
    source = Path(__file__).with_name('library_functions.py').read_text()
    exports = ['support_profile','recovery_hint','rank_candidates','recover_target']
    validate_source(source,exports=exports,library=True)
    return {'library_source':source,'exports':exports,
        'skills':[{'name':'recover_target','usage':'skills.recover_target(api)',
          'description':'Executable DFS with exact-state feedback cache, checkpoints, soft support/dependency ranking and early goal-support risk recovery. All checks/removals use the shared API budget.'}],
        'development':'Previous three failed designed cases only; human-agent-authored adaptation, not autonomous ASPIRE discovery or model fine-tuning.'}


def solve_code(case_path, provider, library=None, initial_state=None, initial_observation=None,
               recovery_state=None,max_calls=8,max_checks=120,max_steps=10000000,
               timeout_seconds=480.0,max_checkpoints=128,max_restores=256):
    started=time.monotonic()
    sim=DisassemblySim(case_path,max_checks=max_checks,state=initial_state)
    api=SharedAPI(sim,recovery_state,max_checkpoints=max_checkpoints,max_restores=max_restores)
    state=sim.export_state(); registry=api.export_recovery_state()
    observation=copy.deepcopy(initial_observation or api.snapshot())
    initial=copy.deepcopy(observation)
    decisions=[]; skill_calls=[]; usage={}; steps=0; calls=0
    termination='call_budget_exhausted'; success=sim.success; checks=state['checks']
    limits=dict(max_calls=max_calls,max_checks=max_checks,max_steps=max_steps,
                timeout_seconds=timeout_seconds,max_checkpoints=max_checkpoints,max_restores=max_restores)
    while not success and calls<max_calls and checks<max_checks and steps<max_steps:
        left=timeout_seconds-(time.monotonic()-started)
        if left<=0:
            termination='wall_budget_exhausted'; break
        history=[{'call':d['call'],'response':d.get('response'),
                  'execution':{k:d.get('execution',{}).get(k) for k in ('error','steps','halt_reason')}} for d in decisions]
        prompt=SPEC+'\nTASK:\n'+json.dumps({'observation':observation,'limits':limits,
            'checks_remaining':max_checks-checks,'model_calls_remaining_including_this':max_calls-calls,
            'opcodes_remaining':max_steps-steps,'history':history,
            'reusable_library':library or {'available':False}},ensure_ascii=False)
        calls+=1
        old_timeout=provider.timeout; provider.timeout=min(old_timeout,left)
        try:
            value,meta=provider.complete(prompt,CODE_SCHEMA,calls)
        except (ProviderError,OSError) as exc:
            decisions.append({'call':calls,'provider_error':str(exc)})
            termination='provider_error'; break
        finally:
            provider.timeout=old_timeout
        for key,n in meta.get('usage',{}).items():
            if isinstance(n,(int,float)): usage[key]=usage.get(key,0)+n
        left=timeout_seconds-(time.monotonic()-started)
        if left<=0:
            decisions.append({'call':calls,'response':value,'metadata':meta})
            termination='wall_budget_exhausted'; break
        result=run_code(case_path,value['code'],state=state,recovery_state=registry,
            library_source=library['library_source'] if library else '',exports=library['exports'] if library else [],
            max_checks=max_checks,max_steps=max_steps-steps,timeout_seconds=min(120,left),
            max_checkpoints=max_checkpoints,max_restores=max_restores)
        state=result['state']; registry=result['recovery_state']; observation=result['observation'] or observation
        steps+=result['steps']; checks=max(checks,result['checker_calls'],state['checks'])
        success=result['success']
        skill_calls.extend({**s,'llm_call':calls} for s in result['skill_calls'])
        # Full registry retained once in final result; avoid duplicating huge checkpoint histories.
        decisions.append({'call':calls,'response':value,'metadata':meta,
            'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
            'execution':{k:v for k,v in result.items() if k not in ('state','recovery_state','observation','trace')}})
        if (result.get('error') or {}).get('type') in ('WorkerError','WallTimeLimit'):
            termination='execution_worker_failure'; break
    if time.monotonic()-started>=timeout_seconds:
        success=False; termination='wall_budget_exhausted'
    elif success: termination='goal_reached'
    elif checks>=max_checks: termination='check_budget_exhausted'
    elif steps>=max_steps: termination='execution_step_budget_exhausted'
    committed=[e for e in registry['events'] if e.get('committed')]
    return {'case_id':sim.case['id'],'method':'code_with_library' if library else 'code_no_library',
        'success':bool(success),'termination':termination,'state':state,'trace':state['trace'],'actions':state['actions'],
        'recovery_state':registry,'backtracks':registry['restore_count'],'decisions':decisions,'skill_calls':skill_calls,
        'initial_observation':initial,'initial_observation_sha256':neutral_observation_hash(initial),
        'observation':observation,'checker_calls':checks,'completed_checker_calls':state['checks'],
        'llm_calls':calls,'execution_steps':steps,'token_usage':usage,'elapsed_seconds':time.monotonic()-started,
        'removed_count':len(state['actions']) if success else None,'accepted_removals':len(committed),
        'library_sha256':digest(library) if library else None}

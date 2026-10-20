"""v7.2 episode actor: copy of disassembly_repair_v7/actors.py with the HardenedAPI, v7.2 runtime,
API-level deadline and v7.2 contract (8 GiB guard). v7 file unchanged.

Original v7 docstring: v7 episode actor. Adapted copy of disassembly_final_v6/actors.py (unchanged file).

Same: model request/schema validation, mandatory document read phase, budgets,
RSS guard, wall deadline, prompt/response byte caps, progress persistence.
Changed (recorded in CHANGELOG.md):
  * common API = v7 LedgerAPI (search ledger, dead-end guard, state checkpoints);
  * A/B: per-turn progress facts, turn_progress_feedback in the next prompt,
    termination no_progress_stop after NO_PROGRESS_LIMIT consecutive turns
    without a new charged physics check;
  * C: DFS7 per-state orders and paced ranking with call_reason audit.
"""
from __future__ import annotations
import copy
import hashlib
import json
import resource
import sys
import time

from disassembly_final_v6.documents import DocumentBank
from disassembly_real_v3.simulator import FullDisassemblySim
from disassembly_recovery.shared_api import physical_state_key

from .common import write, digest
from .contracts import COMMON, CODE_SPEC, C_SPEC, SCHEMA, LIMITS, NO_PROGRESS_LIMIT, VERSION, PHYSICS_NOTES
from .controller import DFS72 as DFS7  # C7.2: rank when stuck (see controller.py)
from .shared_api import HardenedAPI as LedgerAPI, SearchLedger
from . import runtime


class LimitError(RuntimeError):
    pass


def rss_guard(cap):
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != 'darwin':
        rss *= 1024
    if rss > cap:
        raise LimitError(f'same {cap/1024**3:g} GiB resident-memory ceiling exceeded')


FEEDBACK_KEEP = ('operation', 'part_id', 'direction', 'valid', 'reason', 'committed', 'blockers', 'checker_call',
                 'collision_distance_m', 'extraction_distance_m', 'collision_details', 'stability', 'physical_state_key_after',
                 'charged_physics_check')
DETAIL_KEEP = ('kind', 'other_part', 'signed_depth_m', 'initial_signed_depth_m', 'permitted_depth_m', 'depth_m')
CHECKPOINT_KEEP = ('handle', 'state_key', 'removed_count', 'creation_event_index')
PROMPT_VIEW_NOTE = ('Prompt view (identical for A/B/C): current_state_feedback rows omit repeated per-check collision_policy '
                    'boilerplate, elapsed time, remaining lists, resolved direction vectors, before-state keys and sample '
                    'coordinates (at most two collision_details with kind/other_part/depths); history_feedback rows omit remaining lists; '
                    'recovery.checkpoints rows keep handle/state_key/removed_count/creation_event_index. '
                    'At runtime api.snapshot() and api.checkpoints() return the full objects.')


def prompt_view(observation):
    """Compact copy for the model prompt only (v6 prompts grew ~5.5 KB per failed check at a state)."""
    view = copy.deepcopy(observation)
    rows = []
    for r in view.get('current_state_feedback', []):
        row = {k: r[k] for k in FEEDBACK_KEEP if k in r}
        if isinstance(row.get('collision_details'), list):
            row['collision_details'] = [{k: d[k] for k in DETAIL_KEEP if k in d} for d in row['collision_details'][:2] if isinstance(d, dict)]
        rows.append(row)
    view['current_state_feedback'] = rows
    view['history_feedback'] = [{k: v for k, v in r.items() if k not in ('remaining_before', 'remaining_after')}
                                for r in view.get('history_feedback', [])]
    rec = view.get('recovery')
    if isinstance(rec, dict) and isinstance(rec.get('checkpoints'), list):
        rec['checkpoints'] = [{k: c[k] for k in CHECKPOINT_KEEP if k in c} for c in rec['checkpoints']]
    view['prompt_view_note'] = PROMPT_VIEW_NOTE
    return view


def context_view(context):
    """C prompt copy: graph edges keep from/to/direction; the shared state_key and semantics are stated once."""
    view = copy.deepcopy(context)
    graph = view.get('directed_graph')
    if isinstance(graph, dict) and isinstance(graph.get('edges'), list):
        graph['edge_semantics'] = 'Each edge: blocker `from` blocks sampled straight extraction of `to` in `direction` at state_key.'
        graph['edges'] = [{k: e[k] for k in ('from', 'to', 'direction') if k in e} for e in graph['edges']]
    return view


def solve(case_path, provider, bank_path, architecture, shared=None, limits=None, progress_path=None,
          public_task_note=None, sim_factory=None, physics_variant=None):
    limits = {**LIMITS, **(limits or {})}
    started = time.monotonic()
    deadline = started + limits['timeout_seconds']
    bank = DocumentBank(bank_path)
    make_sim = sim_factory or (lambda: FullDisassemblySim(case_path, max_checks=limits['max_checks'],
                                                           state=shared['state'] if shared else None))
    from disassembly_repair_v7.physics_variants import apply as apply_physics, DESCRIPTIONS
    apply_physics(physics_variant)  # in-process; identical for every arm of a condition
    sim = make_sim()
    if physics_variant:
        sim.physics['initial_interference_rule'] = DESCRIPTIONS[physics_variant]
    api = LedgerAPI(sim, recovery_state=shared['recovery_state'] if shared else None, max_checks=limits['max_checks'],
                    max_checkpoints=limits['max_checkpoints'], max_restores=limits['max_restores'])
    api.deadline, api.deadline_exception = deadline, LimitError   # H1 (C arm and host-side calls)
    initial = api.snapshot()
    loaded, loaded_references, reads, decisions, usage = {}, {}, [], [], {}
    calls = steps = 0
    timeline = [dict(elapsed_seconds=time.monotonic() - started, checks=sim.checks, removed=len(sim.actions),
                     success=bool(sim.success), event='initial')]
    dfs = DFS7() if architecture == 'graph_dfs' else None
    termination = 'call_budget_exhausted'
    error = None
    turn_progress = []
    no_progress_streak = 0

    def check():
        rss_guard(limits['max_rss_bytes'])
        if time.monotonic() >= deadline:
            raise LimitError('wall_time_budget_exhausted')
        if steps >= limits['max_steps']:
            raise LimitError('instruction_budget_exhausted')

    runtime.guards.memory_check = lambda: rss_guard(limits['max_rss_bytes'])

    def state_result():
        return dict(case_id=sim.case['id'], case_path=str(case_path), architecture=architecture, v7_version=VERSION,
                    bank_sha256=bank.sha256, bank_content_sha256=bank.content_sha256, bank_version=bank.manifest['version'],
                    success=bool(sim.success), termination=termination, state=sim.export_state(),
                    recovery_state=api.export_recovery_state(), trace=sim.trace, actions=sim.actions,
                    initial_observation=initial, initial_observation_sha256=digest(initial), observation=api.snapshot(),
                    decisions=decisions, document_reads=reads, loaded_skill_ids=list(loaded), llm_calls=calls,
                    token_usage=usage, checker_calls=sim.checks, execution_steps=steps,
                    elapsed_seconds=time.monotonic() - started, limits=limits, error=error,
                    max_rss_bytes_observed=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)),
                    learning_updates=0, timeline=timeline, turn_progress=turn_progress, physics_variant=physics_variant,
                    rank_history=dfs.rank_history if dfs else [],
                    retrieval_policy='mandatory_initial_document_review_counted_in_budget', **sim.task_progress())

    def flush():
        if progress_path:
            write(progress_path, state_result())

    def live_progress(event):
        rss_guard(limits['max_rss_bytes'])
        if event.get('event') in ('operation_finished', 'progress', 'final'):
            point = dict(elapsed_seconds=time.monotonic() - started, checks=sim.checks, removed=len(sim.actions),
                         success=bool(sim.success), event=event['event'])
            if (point['checks'], point['removed'], point['success']) != (timeline[-1]['checks'], timeline[-1]['removed'], timeline[-1]['success']):
                timeline.append(point)
        if not progress_path:
            return
        row = state_result()
        if event.get('event') in ('progress', 'final') and event.get('result'):
            result = event['result']
            for key in ['state', 'recovery_state', 'observation', 'trace', 'actions', 'checker_calls', 'success']:
                row[key] = result[key]
            row['execution_steps'] = steps + result['steps']
        elif event.get('event') == 'operation_started':
            row['unfinished_operation'] = copy.deepcopy(event)
            if event.get('recovery_state'):
                row['recovery_state'] = copy.deepcopy(event['recovery_state'])
            row['checker_calls'] = max(row['checker_calls'], event['checker_call'])
            row['state']['checks'] = row['checker_calls']
        write(progress_path, row)

    api._callback = live_progress

    def metered(call):
        nonlocal steps
        paths = ('/disassembly_repair_v7/controller.py', '/disassembly_final_v6/controller.py', '/disassembly_hybrid/graph.py')
        sys._getframe().f_trace_opcodes = True

        def trace(frame, event, arg):
            nonlocal steps
            if not frame.f_code.co_filename.endswith(paths):
                return None
            if event == 'call':
                frame.f_trace_opcodes = True
                frame.f_trace_lines = False
            elif event == 'opcode':
                steps += 1
                if steps % 256 == 0:
                    check()
            return trace
        sys.settrace(trace)
        try:
            return call()
        finally:
            sys.settrace(None)

    def model_request(context, call_reason):
        nonlocal calls, error
        check()
        observation = api.snapshot()
        pending = [r['skill_id'] for r in bank.catalog() if r['skill_id'] not in loaded]
        phase_note = ('DOCUMENT READ PHASE: return ONLY the schema JSON with operation=read_skills and skill_ids=' + json.dumps(pending) + '. This JSON is the read request; the host supplies the document next. Do NOT use tools, list_mcp_resources, list_mcp_resource_templates, filesystem or browser. Do not execute/rank in this response.'
                      if pending else 'EXECUTION PHASE: supplied documents are already in PUBLIC INPUT. No external tools. Return only the response JSON.')
        payload = dict(observation=prompt_view(observation), limits=limits, checks_remaining=limits['max_checks'] - sim.checks,
                       model_calls_remaining_including_this=limits['max_calls'] - calls,
                       instructions_remaining=limits['max_steps'] - steps, wall_seconds_remaining=deadline - time.monotonic(),
                       reusable_skill_catalog=bank.catalog(), loaded_skill_documents=loaded,
                       loaded_skill_validation_references=loaded_references, architecture_context=context_view(context),
                       public_task_note=public_task_note,
                       recent_decisions=[dict(call=d['call'], operation=d.get('response', {}).get('operation'),
                                              summary=d.get('response', {}).get('summary'), error=d.get('execution_error'),
                                              call_reason=d.get('call_reason'), checks_before=d.get('checks_before'),
                                              checks_after=d.get('checks_after')) for d in decisions[-10:]])
        if architecture == 'code':
            payload['turn_progress_feedback'] = turn_progress[-6:]
            payload['consecutive_execute_turns_without_progress'] = no_progress_streak
            payload['no_progress_stop_after'] = NO_PROGRESS_LIMIT
        prompt = COMMON + (PHYSICS_NOTES.get(physics_variant, '')) + (CODE_SPEC if architecture == 'code' else C_SPEC) + '\nCURRENT RESPONSE PHASE:\n' + phase_note + '\nPUBLIC INPUT:\n' + json.dumps(payload, ensure_ascii=False)
        if len(prompt.encode()) > limits['max_prompt_bytes']:
            raise LimitError('prompt_byte_budget_exhausted; documents were not truncated')
        calls += 1
        decision = dict(call=calls, call_reason=('document_read_phase' if pending else call_reason), checks_before=sim.checks,
                        removed_before=len(sim.actions), state_key=observation['state_key'],
                        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), prompt_bytes=len(prompt.encode()),
                        loaded_before=list(loaded), elapsed_before=time.monotonic() - started)
        decisions.append(decision)
        flush()
        provider.timeout = min(120., max(.1, deadline - time.monotonic()))
        request_schema = copy.deepcopy(SCHEMA)
        if pending:
            request_schema['properties']['operation']['enum'] = ['read_skills']
            request_schema['properties']['skill_ids'].update(minItems=len(pending), maxItems=len(pending))
            request_schema['properties']['skill_ids']['items'] = {'type': 'string', 'enum': pending}
        elif not bank.catalog():
            request_schema['properties']['operation']['enum'] = ['execute']
        response, metadata = provider.complete(prompt, request_schema, calls)
        decision.update(response=response, metadata=metadata)
        for key, n in metadata.get('usage', {}).items():
            if isinstance(n, (int, float)):
                usage[key] = usage.get(key, 0) + n
        if len(json.dumps(response, ensure_ascii=False).encode()) > limits['max_response_bytes']:
            raise LimitError('response_byte_budget_exhausted')
        if set(response) != set(SCHEMA['required']):
            raise ValueError('response schema mismatch')
        if pending and response['operation'] != 'read_skills':
            raise ValueError('physical procedure must be read before execution')
        if response['operation'] == 'read_skills':
            docs = bank.load(response['skill_ids'])
            loaded_references.update(bank.load_references(response['skill_ids']))
            for sid, text in docs.items():
                loaded[sid] = text
                reads.append(dict(call=calls, skill_id=sid, document_sha256=hashlib.sha256(text.encode()).hexdigest(),
                                  validation_reference_sha256=loaded_references.get(sid, {}).get('sha256'),
                                  bytes=len(text.encode()), checks_at_read=sim.checks, read_by='explicit_model_request'))
            decision['document_load_status'] = 'loaded_for_next_model_context'
            return None
        if any(sid not in loaded for sid in response['applied_skill_ids']):
            raise ValueError('model claimed an unread skill')
        if loaded and not response['document_plan']:
            raise ValueError('loaded physical procedure requires an explicit applicability/action plan')
        if any(p['skill_id'] not in loaded for p in response['document_plan']):
            raise ValueError('document plan cites an unread skill')
        if loaded and set(response['applied_skill_ids']) != set(loaded):
            raise ValueError('required physical procedure review was omitted')
        decision['claimed_application_ids'] = list(response['applied_skill_ids'])
        decision['document_plan'] = copy.deepcopy(response['document_plan'])
        return response

    def recovery_counts():
        r = api.export_recovery_state()
        return r['restore_count'], len(r.get('guarded_requests', [])), len(r['checkpoints'])

    try:
        while not sim.success and sim.checks < limits['max_checks']:
            check()
            if architecture == 'code':
                if calls >= limits['max_calls']:
                    break
                response = model_request({}, 'execute_turn')
                if response is None:
                    continue
                checks0, removed0, key0 = sim.checks, len(sim.actions), physical_state_key(sim.export_state())
                restores0, guarded0, cps0 = recovery_counts()
                payload = dict(code=response['code'], max_checks=limits['max_checks'],
                               max_steps=limits['max_steps'] - steps, timeout_seconds=max(.1, deadline - time.monotonic()),
                               recovery_state=api.export_recovery_state(), max_checkpoints=limits['max_checkpoints'],
                               max_restores=limits['max_restores'], deadline_monotonic=deadline)
                result = runtime.execute_payload(payload, sim, callback=live_progress)
                steps += result['steps']
                api = LedgerAPI(sim, recovery_state=result['recovery_state'], max_checks=limits['max_checks'],
                                max_checkpoints=limits['max_checkpoints'], max_restores=limits['max_restores'],
                                callback=live_progress)
                api.deadline, api.deadline_exception = deadline, LimitError
                restores1, guarded1, cps1 = recovery_counts()
                key1 = physical_state_key(sim.export_state())
                ledger = SearchLedger(sim.parts, sim.trace, len(sim.parts))
                progress = sim.checks > checks0
                no_progress_streak = 0 if progress else no_progress_streak + 1
                row = dict(call=calls, checks_before=checks0, checks_after=sim.checks, new_physics_checks=sim.checks - checks0,
                           removed_before=removed0, removed_after=len(sim.actions), restores=restores1 - restores0,
                           guarded_requests=guarded1 - guarded0, checkpoints_after=cps1, state_changed=key0 != key1,
                           ended_at_known_dead_end=ledger.dead_end(key1), progress=progress,
                           execution_error=result['error'], consecutive_without_progress=no_progress_streak)
                turn_progress.append(row)
                decisions[-1].update(execution_error=result['error'], checks_after=sim.checks, turn_progress=row)
                if result['error'] and result['error']['type'] in ('InstructionLimit', 'WallTimeLimit', 'MemoryLimit', 'LimitError'):
                    termination = 'execution_budget_exhausted'
                    error = result['error']
                    break
                if no_progress_streak >= NO_PROGRESS_LIMIT and not sim.success:
                    termination = 'no_progress_stop'
                    break
            else:
                context = metered(lambda: dfs.context(sim, api))
                if not context['candidate_actions']:
                    status = metered(lambda: dfs.step(sim, api))
                    flush()
                    if status == 'exhausted':
                        termination = 'search_exhausted'
                        break
                    continue
                if calls >= limits['max_calls'] and not any(d.get('response', {}).get('operation') == 'execute' for d in decisions):
                    break
                key = dfs.current_key()
                reason = dfs.ranking_reason(key)
                if calls < limits['max_calls'] and reason:
                    if loaded or not bank.catalog():
                        calls_after = limits['max_calls'] - calls - 1
                        window = dfs.window(limits['max_checks'] - sim.checks, calls_after)
                    else:
                        window = None  # read phase comes first; window is set at the ranking call
                    context = dict(context, call_reason=reason, committed_window=window)
                    response = model_request(context, reason)
                    if response is None:
                        continue
                    calls_after = limits['max_calls'] - calls
                    window = dfs.window(limits['max_checks'] - sim.checks, calls_after)
                    row = metered(lambda: dfs.set_state_order(key, response['ordered_actions'], context['candidate_actions'],
                                                              window, calls, reason))
                    decisions[-1].update(committed_window=window, rank_audit={k: v for k, v in row.items() if k != 'effective_order'})
                metered(lambda: dfs.step(sim, api))
            flush()
        if sim.success:
            termination = 'goal_reached'
        elif sim.checks >= limits['max_checks']:
            termination = 'check_budget_exhausted'
        if time.monotonic() >= deadline:
            termination = 'wall_time_budget_exhausted'
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        error = dict(type=type(exc).__name__, message=str(exc)[:1500])
        termination = 'limit' if isinstance(exc, LimitError) else 'execution_or_provider_error'
    result = state_result()
    if time.monotonic() >= deadline:
        result.update(success=False, termination='wall_time_budget_exhausted')
    flush()
    return result

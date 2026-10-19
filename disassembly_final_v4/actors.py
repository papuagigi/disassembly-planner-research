"""Shared document selection plus generated-code or graph/DFS execution.

The bank changes model context only. Both architectures use identical simulator,
restoration API, RSS limit and whole-episode wall/call/check ceilings.
"""
from __future__ import annotations
import copy
import hashlib
import json
import resource
import sys
import time
from .common import write,digest
from .contracts import COMMON,CODE_SPEC,C_SPEC,SCHEMA,LIMITS
from .documents import DocumentBank
from .controller import DFS
from disassembly_real_v3.simulator import FullDisassemblySim
from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_real_v3 import runtime

class LimitError(RuntimeError):pass

def rss_guard(cap):
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform!='darwin':rss*=1024
    if rss>cap:raise LimitError('same 1 GiB resident-memory ceiling exceeded')

def solve(case_path,provider,bank_path,architecture,shared=None,limits=None,progress_path=None,public_task_note=None):
    limits={**LIMITS,**(limits or {})};started=time.monotonic();deadline=started+limits['timeout_seconds']
    bank=DocumentBank(bank_path);sim=FullDisassemblySim(case_path,max_checks=limits['max_checks'],state=shared['state'] if shared else None)
    api=SharedAPI(sim,recovery_state=shared['recovery_state'] if shared else None,max_checks=limits['max_checks'],
        max_checkpoints=limits['max_checkpoints'],max_restores=limits['max_restores'])
    initial=api.snapshot();loaded={};loaded_references={};reads=[];decisions=[];usage={};calls=steps=0
    timeline=[dict(elapsed_seconds=time.monotonic()-started,checks=sim.checks,removed=len(sim.actions),success=bool(sim.success),event='initial')]
    dfs=DFS() if architecture=='graph_dfs' else None
    termination='call_budget_exhausted';error=None;last_rank_epoch=-1
    def check():
        rss_guard(limits['max_rss_bytes'])
        if time.monotonic()>=deadline:raise LimitError('wall_time_budget_exhausted')
        if steps>=limits['max_steps']:raise LimitError('instruction_budget_exhausted')
    # Same legacy restricted grammar, not its executable bank. Its budget checks
    # resolve this process-local guard; no previous source/module file is edited.
    runtime.memory_check=lambda:rss_guard(limits['max_rss_bytes'])
    runtime.guards.memory_check=runtime.memory_check
    def state_result():
        return dict(case_id=sim.case['id'],case_path=str(case_path),architecture=architecture,
            bank_sha256=bank.sha256,bank_content_sha256=bank.content_sha256,bank_version=bank.manifest['version'],success=bool(sim.success),termination=termination,
            state=sim.export_state(),recovery_state=api.export_recovery_state(),trace=sim.trace,actions=sim.actions,
            initial_observation=initial,initial_observation_sha256=digest(initial),observation=api.snapshot(),
            decisions=decisions,document_reads=reads,loaded_skill_ids=list(loaded),llm_calls=calls,token_usage=usage,
            checker_calls=sim.checks,execution_steps=steps,elapsed_seconds=time.monotonic()-started,limits=limits,error=error,
            max_rss_bytes_observed=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)),
            learning_updates=0,timeline=timeline,retrieval_policy='mandatory_initial_document_review_counted_in_budget',**sim.task_progress())
    def flush():
        if progress_path:write(progress_path,state_result())
    def live_progress(event):
        """Persist both architectures at the same API boundary, including starts.

        A killed native operation remains an explicitly unfinished reserved check,
        never a fabricated completed trace. It still consumes the trial allowance.
        """
        rss_guard(limits['max_rss_bytes'])
        if event.get('event') in ('operation_finished','progress','final'):
            point=dict(elapsed_seconds=time.monotonic()-started,checks=sim.checks,removed=len(sim.actions),success=bool(sim.success),event=event['event'])
            if (point['checks'],point['removed'],point['success'])!=(timeline[-1]['checks'],timeline[-1]['removed'],timeline[-1]['success']):timeline.append(point)
        if not progress_path:return
        row=state_result()
        if event.get('event') in ('progress','final') and event.get('result'):
            result=event['result']
            for key in ['state','recovery_state','observation','trace','actions','checker_calls','success']:
                row[key]=result[key]
            row['execution_steps']=steps+result['steps']
        elif event.get('event')=='operation_started':
            row['unfinished_operation']=copy.deepcopy(event)
            if event.get('recovery_state'):
                row['recovery_state']=copy.deepcopy(event['recovery_state'])
            row['checker_calls']=max(row['checker_calls'],event['checker_call'])
            row['state']['checks']=row['checker_calls']
        write(progress_path,row)
    api._callback=live_progress
    def metered(call):
        nonlocal steps
        paths=('/disassembly_final_v4/controller.py','/disassembly_hybrid/graph.py')
        sys._getframe().f_trace_opcodes=True
        def trace(frame,event,arg):
            nonlocal steps
            if not frame.f_code.co_filename.endswith(paths):return None
            if event=='call':frame.f_trace_opcodes=True;frame.f_trace_lines=False
            elif event=='opcode':
                steps+=1
                if steps%256==0:check()
            return trace
        sys.settrace(trace)
        try:return call()
        finally:sys.settrace(None)
    def model_request(context):
        nonlocal calls,error
        check()
        observation=api.snapshot()
        pending=[r['skill_id'] for r in bank.catalog() if r['skill_id'] not in loaded]
        phase_note=('DOCUMENT READ PHASE: return ONLY the schema JSON with operation=read_skills and skill_ids='+json.dumps(pending)+'. This JSON is the read request; the host supplies the document next. Do NOT use tools, list_mcp_resources, list_mcp_resource_templates, filesystem or browser. Do not execute/rank in this response.'
            if pending else 'EXECUTION PHASE: supplied documents are already in PUBLIC INPUT. No external tools. Return only the response JSON.')
        payload=dict(observation=observation,limits=limits,checks_remaining=limits['max_checks']-sim.checks,
            model_calls_remaining_including_this=limits['max_calls']-calls,
            instructions_remaining=limits['max_steps']-steps,wall_seconds_remaining=deadline-time.monotonic(),
            reusable_skill_catalog=bank.catalog(),loaded_skill_documents=loaded,loaded_skill_validation_references=loaded_references,architecture_context=context,public_task_note=public_task_note,
            recent_decisions=[dict(call=d['call'],operation=d.get('response',{}).get('operation'),summary=d.get('response',{}).get('summary'),error=d.get('execution_error')) for d in decisions[-10:]])
        prompt=COMMON+(CODE_SPEC if architecture=='code' else C_SPEC)+'\nCURRENT RESPONSE PHASE:\n'+phase_note+'\nPUBLIC INPUT:\n'+json.dumps(payload,ensure_ascii=False)
        if len(prompt.encode())>limits['max_prompt_bytes']:raise LimitError('prompt_byte_budget_exhausted; documents were not truncated')
        calls+=1;decision=dict(call=calls,checks_before=sim.checks,state_key=observation['state_key'],prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),prompt_bytes=len(prompt.encode()),loaded_before=list(loaded))
        decisions.append(decision);flush()
        provider.timeout=min(120.,max(.1,deadline-time.monotonic()))
        request_schema=copy.deepcopy(SCHEMA)
        if pending:
            request_schema['properties']['operation']['enum']=['read_skills']
            request_schema['properties']['skill_ids'].update(minItems=len(pending),maxItems=len(pending))
            request_schema['properties']['skill_ids']['items']={'type':'string','enum':pending}
        elif not bank.catalog():
            request_schema['properties']['operation']['enum']=['execute']
        response,metadata=provider.complete(prompt,request_schema,calls)
        decision.update(response=response,metadata=metadata)
        for key,n in metadata.get('usage',{}).items():
            if isinstance(n,(int,float)):usage[key]=usage.get(key,0)+n
        if len(json.dumps(response,ensure_ascii=False).encode())>limits['max_response_bytes']:raise LimitError('response_byte_budget_exhausted')
        if set(response)!=set(SCHEMA['required']):raise ValueError('response schema mismatch')
        if pending and response['operation']!='read_skills':raise ValueError('physical procedure must be read before execution')
        if response['operation']=='read_skills':
            docs=bank.load(response['skill_ids'])
            loaded_references.update(bank.load_references(response['skill_ids']))
            for sid,text in docs.items():
                loaded[sid]=text
                reads.append(dict(call=calls,skill_id=sid,document_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    validation_reference_sha256=loaded_references.get(sid,{}).get('sha256'),bytes=len(text.encode()),checks_at_read=sim.checks,read_by='explicit_model_request'))
            decision['document_load_status']='loaded_for_next_model_context'
            return None
        if any(sid not in loaded for sid in response['applied_skill_ids']):raise ValueError('model claimed an unread skill')
        if loaded and not response['document_plan']:raise ValueError('loaded physical procedure requires an explicit applicability/action plan')
        if any(p['skill_id'] not in loaded for p in response['document_plan']):raise ValueError('document plan cites an unread skill')
        if loaded and set(response['applied_skill_ids'])!=set(loaded):raise ValueError('required physical procedure review was omitted')
        decision['claimed_application_ids']=list(response['applied_skill_ids'])
        decision['document_plan']=copy.deepcopy(response['document_plan'])
        return response
    try:
        while not sim.success and sim.checks<limits['max_checks']:
            check()
            if architecture=='code':
                if calls>=limits['max_calls']:break
                response=model_request({})
                if response is None:continue
                payload=dict(code=response['code'],exports=[],library_bank=None,max_checks=limits['max_checks'],
                    max_steps=limits['max_steps']-steps,timeout_seconds=max(.1,deadline-time.monotonic()),
                    recovery_state=api.export_recovery_state(),max_checkpoints=limits['max_checkpoints'],max_restores=limits['max_restores'])
                result=runtime.execute_payload(payload,sim,callback=live_progress)
                steps+=result['steps']
                api=SharedAPI(sim,recovery_state=result['recovery_state'],max_checks=limits['max_checks'],
                    max_checkpoints=limits['max_checkpoints'],max_restores=limits['max_restores'],callback=live_progress)
                decisions[-1]['execution_error']=result['error'];decisions[-1]['checks_after']=sim.checks
                if result['error'] and result['error']['type'] in ('InstructionLimit','WallTimeLimit','MemoryLimit','LimitError'):
                    termination='execution_budget_exhausted';error=result['error'];break
            else:
                context=metered(lambda:dfs.context(sim,api))
                # Recovery/exhaustion is deterministic and precedes every model call.
                if not context['candidate_actions']:
                    status=metered(lambda:dfs.step(sim,api));flush()
                    if status=='exhausted':termination='search_exhausted';break
                    continue
                if calls>=limits['max_calls'] and not any(d.get('response',{}).get('operation')=='execute' for d in decisions):break
                # Ask on a new state as before, and immediately on a newly
                # observed instability so the physical repair is not postponed
                # until six unrelated failures. Same call cap still applies.
                last_checks=decisions[-1].get('checks_before',-1) if decisions else -1
                new_instability=bool(sim.trace and sim.trace[-1].get('reason')=='unstable_remainder' and sim.checks>last_checks)
                if calls<limits['max_calls'] and (last_rank_epoch!=dfs.epoch or dfs.failures_since_rank>=6 or new_instability):
                    response=model_request(context)
                    if response is None:continue
                    metered(lambda:dfs.set_order(response['ordered_actions'],context['candidate_actions']))
                    last_rank_epoch=dfs.epoch
                metered(lambda:dfs.step(sim,api))
            flush()
        if sim.success:termination='goal_reached'
        elif sim.checks>=limits['max_checks']:termination='check_budget_exhausted'
        if time.monotonic()>=deadline:termination='wall_time_budget_exhausted'
    except BaseException as exc:
        if isinstance(exc,(KeyboardInterrupt,SystemExit)):raise
        error=dict(type=type(exc).__name__,message=str(exc)[:1500]);termination='limit' if isinstance(exc,LimitError) else 'execution_or_provider_error'
    result=state_result()
    if time.monotonic()>=deadline:result.update(success=False,termination='wall_time_budget_exhausted')
    flush();return result

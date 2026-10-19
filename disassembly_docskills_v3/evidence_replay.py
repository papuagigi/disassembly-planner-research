"""Independent execution of recorded API events, without any actor/model call."""
from __future__ import annotations
import copy
import math
from pathlib import Path
from .common import read,write,sha,utc
from disassembly_real_v3.simulator import FullDisassemblySim
from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_hybrid.graph import physical_state_key

FIELDS=('valid','reason','part_id','direction','committed','blockers','stability','remaining_before','remaining_after','physical_state_key_before','physical_state_key_after','path_samples','physics_steps')

def equal(a,b,path='root'):
    if isinstance(a,dict):
        assert isinstance(b,dict) and set(a)==set(b),(path,'keys')
        for k in a:equal(a[k],b[k],path+'.'+k)
    elif isinstance(a,list):
        assert isinstance(b,list) and len(a)==len(b),(path,'length')
        for i,(x,y) in enumerate(zip(a,b)):equal(x,y,path+f'[{i}]')
    elif isinstance(a,float):assert isinstance(b,(int,float)) and math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-10),(path,a,b)
    else:assert a==b,(path,a,b)

def replay_result(result_path,*,shared_path=None,output=None,capture=False,allow_incomplete=False):
    original=read(result_path);cp=original['case_path'];shared=read(shared_path) if shared_path else None
    max_checks=original['limits']['max_checks']
    sim=FullDisassemblySim(cp,max_checks=max_checks,state=shared['state'] if shared else None,capture=capture)
    api=SharedAPI(sim,recovery_state=shared['recovery_state'] if shared else None,max_checks=max_checks,
        max_checkpoints=original['limits']['max_checkpoints'],max_restores=original['limits']['max_restores'])
    skip=len(shared['recovery_state']['events']) if shared else 0
    handles={h:h for h in (shared['recovery_state']['checkpoints'] if shared else {})}
    count=restores=0;seed_trace_count=len(shared['state']['trace']) if shared else 0
    events=[];failure_frames=[];restore_frames=[];unfinished=[]
    recorded_events=original['recovery_state']['events'][skip:]
    new_trace_count=len(original['trace'])-seed_trace_count
    for event_offset,event in enumerate(recorded_events):
        assert physical_state_key(sim.export_state())==event['state_key_before'],('before',event['event_index'])
        operation=event['operation'];error=None
        if operation in ('check','remove') and count>=new_trace_count:
            assert allow_incomplete and event_offset==len(recorded_events)-1 and event.get('status') in ('started','error'),('unrecorded query is not an allowed interrupted tail',event)
            unfinished.append(event)
            if capture:
                sim._record_frame('검사 중 시간 종료 · 결과 없음 · 검사 비용 유지',advance=.3)
                sim.frames[-1].update(phase='unfinished_reserved_check',stage='planner',api_event_index=event['event_index'])
            break
        try:
            if operation=='checkpoint':
                h=api.checkpoint();handles[event['handle']]=h
                expected=original['recovery_state']['checkpoints'][event['handle']]['metadata']
                actual=api.checkpoints()[-1]
                for key in ['state_key','remaining_parts','removed_count','support_edges','accepted_action_prefix']:
                    if key in expected:equal(expected[key],actual[key],'checkpoint.'+key)
            elif operation=='restore':
                api.restore(handles.get(event['handle'],event['handle']));restores+=1
                if capture:
                    sim._record_frame('Checkpoint 복원 · 비용 유지',advance=.3);sim.frames[-1].update(phase='restore',stage='planner',api_event_index=event['event_index'])
                    restore_frames.append(len(sim.frames)-1)
            elif operation in ('check','remove'):
                before=len(sim.frames)
                result=getattr(api,operation)(event['part_id'],event['direction']);count+=1
                expected=original['trace'][seed_trace_count+count-1]
                actual=sim.trace[-1]
                for key in FIELDS:
                    if key in expected:equal(expected[key],actual[key],'trace.'+key)
                if capture:
                    sim._record_frame(('제거 승인' if result['committed'] else '검사 통과' if result['valid'] else '검사 거절')+' · '+event['part_id']+' '+event['direction']+' · '+result['reason'],advance=.25)
                    for frame in sim.frames[before:]:frame.update(stage='planner',api_event_index=event['event_index'])
                    if not result['valid']:
                        failure_frames.append(len(sim.frames)-1);sim.frames[-1]['phase']='rejected_check'
                    events.append(dict(frame=len(sim.frames)-1,time=sim.clock,type=result['reason'],part_id=result['part_id'],direction=result['direction'],message=sim.frames[-1]['label']))
            else:raise ValueError('Unsupported recorded operation '+operation)
        except BaseException as exc:
            error=exc
            if event.get('status')!='error':raise
        if event.get('status')=='error':assert error is not None
        else:assert error is None
        assert physical_state_key(sim.export_state())==event['state_key_after'],('after',event['event_index'])
        assert sim.checks==event['checks_after'],('cost',event['event_index'])
    assert len(sim.trace)==len(original['trace'])
    equal(original['state']['remaining'],sim.remaining,'final remaining')
    equal({p:original['state']['poses'][p] for p in sim.remaining},{p:sim.poses[p] for p in sim.remaining},'final poses')
    reserved=original['checker_calls']-sim.checks
    assert reserved==0 or (allow_incomplete and len(unfinished)==1 and reserved==1),('cost',sim.checks,original['checker_calls'])
    receipt=dict(status='PASS_VERIFIED_PREFIX' if unfinished else 'PASS',created_utc=utc(),result_sha256=sha(result_path),case_sha256=sha(cp),physical_queries_replayed=count,
        restores_verified=restores,final_physical_state_key=physical_state_key(sim.export_state()),no_model_calls=True,
        checkpoint_context_verified=True,accepted_state_and_cost_exact=not unfinished,
        finished_event_prefix_verified=True,unfinished_query_events=unfinished,charged_unfinished_checks=reserved,
        original_score_preserved=True,unfinished_result_invented=False)
    if output:write(output,receipt,exclusive=True)
    return receipt,sim,dict(events=events,failure_frames=failure_frames,restore_frames=restore_frames)

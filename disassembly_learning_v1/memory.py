"""Versioned procedural memory; no test-time writes, oracle data, or weight updates.

Learned repair code is pure restricted Python. It can reorder legal candidates or
suggest an existing opaque checkpoint; the common controller/physics API executes
and accounts for every physical operation. This is not a general OS sandbox.
"""
from __future__ import annotations
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

from disassembly_recovery import library_functions as base
from disassembly_recovery.runtime import compile_restricted, _safe_builtins, guards

FEATURES = ('path_collision','unstable_remainder','target_supports_load',
            'alternate_support_available','target_is_sole_support','prior_checkpoint_available',
            'multiple_target_exit_blockers','movable_blocker_observed','accepted_branch',
            'recent_rejected_direction','initial_goal_blocked')

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()

def write(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))

def features(observation,history):
    tags=set();target=observation['target_id']
    records=observation.get('current_state_feedback',[])+list(history[-100:])
    ids={p['id']:p for p in observation['remaining_parts']}
    target_failures=[r for r in records if r.get('part_id')==target and not r.get('valid')]
    if target_failures:tags.add('initial_goal_blocked')
    for reason in ('path_collision','unstable_remainder'):
        if any(r.get('reason')==reason for r in records):tags.add(reason)
    blockers=[]
    for r in target_failures:
        if r.get('reason')=='path_collision':blockers.extend(p for p in r.get('blockers',[]) if p in ids)
    if len(set(blockers))>1:tags.add('multiple_target_exit_blockers')
    if any(not ids[p].get('fixed') for p in blockers):tags.add('movable_blocker_observed')
    profile=base.support_profile(observation)
    if profile['loads']:tags.add('target_supports_load')
    if profile['alternatives']:tags.add('alternate_support_available')
    if profile['sole_loads']:tags.add('target_is_sole_support')
    current=set(ids)
    cps=observation.get('recovery',{}).get('checkpoints',[])
    if any(current < set(c['remaining_parts']) for c in cps):tags.add('prior_checkpoint_available')
    if any(r.get('committed') for r in history):tags.add('accepted_branch')
    if history and not history[-1].get('valid'):tags.add('recent_rejected_direction')
    return sorted(tags)

def validate_skill(skill):
    required={'id','name','failure_signature','when_to_apply','strategy','triggers','source'}
    if not isinstance(skill,dict) or not required<=set(skill):raise ValueError('Incomplete skill record')
    if not isinstance(skill['triggers'],list) or not skill['triggers'] or not set(skill['triggers'])<=set(FEATURES):
        raise ValueError('Skill trigger must use observed generic features')
    source=skill['source']
    if not isinstance(source,str) or len(source)>20000:raise ValueError('Invalid or oversized source')
    tree=ast.parse(source)
    defs=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
    entry=next((n for n in defs if n.name=='repair'),None)
    if entry is None or [a.arg for a in entry.args.args]!=['observation','candidates','history','checkpoints','model_order']:
        raise ValueError('Required repair(observation,candidates,history,checkpoints,model_order) function missing')
    for n in ast.walk(tree):
        if isinstance(n,ast.Constant) and isinstance(n.value,str):
            if n.value.isdigit() or 'eval_' in n.value or 'development_' in n.value:
                raise ValueError('Case/part identifiers must be read from observations, never hard-coded')
    compile_restricted(source,['repair'],True)
    return hashlib.sha256(source.encode()).hexdigest()

def execute(skill,observation,candidates,history,checkpoints,model_order,max_steps=150000,timeout=0.3):
    source_sha=validate_skill(skill)
    scope={'__builtins__':_safe_builtins(),'_binary':guards.safe_binary,'_attribute':guards.safe_attribute}
    code=compile_restricted(skill['source'],['repair'],True)
    count=0;deadline=time.monotonic()+timeout
    previous=sys.gettrace()
    sys._getframe().f_trace_opcodes=True
    def trace(frame,event,arg):
        nonlocal count
        if frame.f_code.co_filename!='<skills>':return None
        if event=='call':frame.f_trace_opcodes=True;frame.f_trace_lines=False
        elif event=='opcode':
            if count>=max_steps:raise RuntimeError('skill opcode limit exceeded')
            count+=1
            if count%256==0 and time.monotonic()>deadline:raise RuntimeError('skill deadline exceeded')
        return trace
    result=None;error=None
    try:
        sys.settrace(trace);exec(code,scope,scope)
        result=scope['repair'](*copy.deepcopy((observation,candidates,history,checkpoints,model_order)))
        result=guards.plain(result)
        if not isinstance(result,dict):raise ValueError('repair must return a dictionary')
        if not isinstance(result.get('ordered_actions',[]),list) or not isinstance(result.get('restore_handle',''),str):
            raise ValueError('Malformed repair output')
    except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)[:600]}
    finally:sys.settrace(previous)
    return {'output':result,'error':error,'execution_steps':count,'source_sha256':source_sha}

def create_bank(path,version,skills=(),parent=None,provenance=None):
    path=Path(path)
    if path.exists():raise FileExistsError('Skill bank versions are append-only: '+str(path))
    entries=[]
    for s in skills:
        s=copy.deepcopy(s);s['source_sha256']=validate_skill(s);entries.append(s)
    bank={'schema_version':1,'version':version,'created_utc':datetime.now(timezone.utc).isoformat(),
          'parent_sha256':parent,'base_source_sha256':hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest(),
          'skills':entries,'provenance':provenance or {},
          'semantics':'Persistent validated executable memory; immutable during held-out evaluation.'}
    bank['bank_sha256']=digest(bank);write(path,bank);return bank

class SkillBank:
    def __init__(self,path_or_bank):
        self.bank=copy.deepcopy(path_or_bank) if isinstance(path_or_bank,dict) else json.loads(Path(path_or_bank).read_text())
        assert digest({k:v for k,v in self.bank.items() if k!='bank_sha256'})==self.bank['bank_sha256']
        assert hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()==self.bank['base_source_sha256']
        for s in self.bank['skills']:assert validate_skill(s)==s['source_sha256']
        self.version=self.bank['version'];self.sha256=self.bank['bank_sha256']
        self.remaining_steps=10000000

    def set_execution_budget(self,remaining_steps):
        self.remaining_steps=max(0,int(remaining_steps))

    def baseline(self,observation,candidates,history,checkpoints,model_order):
        count=0;previous=sys.gettrace();deadline=time.monotonic()+0.3
        source=str(Path(base.__file__).resolve());limit=min(150000,self.remaining_steps)
        sys._getframe().f_trace_opcodes=True
        def trace(frame,event,arg):
            nonlocal count
            if frame.f_code.co_filename!=source:return None
            if event=='call':frame.f_trace_opcodes=True;frame.f_trace_lines=False
            elif event=='opcode':
                if count>=limit:raise RuntimeError('base skill opcode limit exceeded')
                count+=1
                if count%256==0 and time.monotonic()>deadline:raise RuntimeError('base skill deadline exceeded')
            return trace
        ordered=list(candidates);handle='';error=None
        try:
            sys.settrace(trace)
            ordered=base.rank_candidates(observation,candidates,history,model_order)
            handle=base.recovery_hint(observation,checkpoints)
        except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)[:600]}
        finally:sys.settrace(previous)
        return ordered,handle,count,error

    def retrieve(self,observation,history):
        tags=set(features(observation,history));scored=[]
        for index,s in enumerate(self.bank['skills']):
            matched=tags.intersection(s['triggers'])
            # Every stored applicability feature is required; no case identity.
            if set(s['triggers'])<=tags:scored.append((len(matched),index,s))
        return (max(scored,key=lambda x:(x[0],x[1]))[2] if scored else None),sorted(tags)

    def apply(self,observation,candidates,history,checkpoints,model_order):
        ordered,handle,base_steps,base_error=self.baseline(observation,candidates,history,checkpoints,model_order)
        skill,tags=self.retrieve(observation,history)
        retrieval={'bank_version':self.version,'bank_sha256':self.sha256,'state_key':observation['state_key'],
             'checks_before':len(history),'features':tags,
             'applied_skill_id':None,'matched_triggers':[],'source_sha256':None,'error':base_error,
             'execution_steps':base_steps,'base_execution_steps':base_steps,'applied':False}
        output={'ordered_actions':ordered,'restore_handle':handle,'skill_id':None,
                'retrieval':retrieval,'execution_steps':base_steps,'error':base_error}
        if not skill or base_error:return output
        run=execute(skill,observation,ordered,history,checkpoints,model_order,
                    max_steps=min(150000,max(0,self.remaining_steps-base_steps)))
        retrieval.update(applied_skill_id=skill['id'],matched_triggers=skill['triggers'],
            source_sha256=run['source_sha256'],error=run['error'],execution_steps=base_steps+run['execution_steps'],
            learned_execution_steps=run['execution_steps'])
        output.update(skill_id=skill['id'],execution_steps=base_steps+run['execution_steps'],error=run['error'])
        if run['error']:return output
        proposal=run['output'];allowed={(a['part_id'],a['direction']):a for a in candidates}
        kept=[];seen=set()
        for a in proposal.get('ordered_actions',[]):
            if not isinstance(a,dict):continue
            key=(a.get('part_id'),a.get('direction'))
            if key in allowed and key not in seen:kept.append(allowed[key]);seen.add(key)
        kept.extend(a for a in ordered if (a['part_id'],a['direction']) not in seen)
        proposed=proposal.get('restore_handle','')
        if proposed and not any(c['handle']==proposed for c in checkpoints):
            output['error']={'type':'InvalidCheckpoint','message':'skill suggested an unavailable checkpoint'}
            retrieval['error']=output['error'];return output
        output.update(ordered_actions=kept,restore_handle=proposed or handle)
        retrieval['applied']=True
        return output

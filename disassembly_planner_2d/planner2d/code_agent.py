"""Code-as-policy actor with identical primitive and execution budgets in both arms."""
from __future__ import annotations

import hashlib
import json
import time

from .geometry import initial_state, validate_scene
from .llm import ProviderError
from .code_runtime import run_code

CODE_SCHEMA = {'type':'object','properties':{'code':{'type':'string'},'summary':{'type':'string'}},
               'required':['code','summary'],'additionalProperties':False}

API_SPEC = '''Write Python code for the supplied removal-only 2D environment. The host executes your returned code.
Public API, identical in both conditions:
  api.observe() -> {workspace:[xmin,ymin,xmax,ymax], target_id:str, remaining_parts:[{id,rects,allowed_directions,fixed}]}
  api.check(part_id, direction, remaining=None) -> {valid,reason,blockers,distance,swept_rects}
  api.remove(part_id, direction) -> the same checker result; commits removal ONLY when valid.
Every check and remove consumes ONE trusted-checker call, even failed, repeated or hypothetical checks.
check then remove costs TWO calls. remove alone checks and commits in ONE call. There is no cache.
observe is free. remaining in check is an optional subset of currently present IDs that must retain all fixed parts, for hypothetical inspection only.
Parts are unions of [x,y,width,height] rectangles. Up is +y. A removal translates the entire part straight outside the workspace.
Any positive-area overlap anywhere in the complete swept path is a collision; touching boundaries is permitted.
Fixed parts cannot move. Only their allowed_directions are legal. Removed parts disappear.
The objective is checker-confirmed target removal with as few removed parts as possible, including the target.
The host stops execution successfully immediately when the target is removed; no later statements run.
Use execution feedback to repair your program. You can write functions, loops, recursion, conditionals and ordinary arithmetic.
No imports, files, network, reflection, private attributes, classes, exceptions, or external tools. Use only public API and safe Python builtins.
Do not use type annotations, f-strings, try/except, slice assignment, or subscript augmented assignment. Function defaults must be literals. Use x[i] = x[i] + 1 instead of x[i] += 1.
Basic list/dict/set methods, sorted, min, max, len, range, enumerate, zip, sum, abs, any, all, tuple, list, dict, set, str, int, float, bool, round and print are available.
All API calls, including inside skills, share the same remaining checker budget. Code execution steps are bounded.
Variables reset each model turn; accepted physical state and all prior traces persist. Return plain code, without markdown fences.
Do NOT run code through your own tools: return it in the JSON code field for the host execution engine.
'''

def public_scene(scene, remaining):
    return {'workspace':scene['workspace'],'target_id':scene['target_id'],
            'remaining_parts':[{k:p[k] for k in ('id','rects','allowed_directions','fixed')}
                               for p in scene['parts'] if p['id'] in remaining]}

def build_code_prompt(scene, remaining, decisions, checks_left, steps_left, library=None):
    data={'observation':public_scene(scene,remaining), 'remaining_checker_calls':checks_left,
          'remaining_execution_steps':steps_left,
          'execution_history':[{'code':d['response']['code'],'execution':d['execution']} for d in decisions]}
    guidance={'available':False,'exports':[]}
    if library is not None:
        guidance={'available':True,'exports':library['skills'],
                  'source':library['library_source'],
                  'usage':'Call skills.<exported_name>(api, ...). These are real Python functions executed by the host. You choose whether and how to call them.'}
    return API_SPEC+'\nTASK AND EXECUTION FEEDBACK:\n'+json.dumps(data,ensure_ascii=False)+'\nREUSABLE LIBRARY:\n'+json.dumps(guidance,ensure_ascii=False)

def solve_code(scene,provider,library=None,max_calls=4,max_checks=24,max_steps=50000,execution_timeout=5.0):
    validate_scene(scene)
    start=time.monotonic();remaining=initial_state(scene);decisions=[];trace=[];actions=[];skill_calls=[];usage={}
    calls=checks=steps=0;provider_error=None;termination='call_budget_exhausted'
    while scene['target_id'] in remaining and calls<max_calls and checks<max_checks and steps<max_steps:
        prompt=build_code_prompt(scene,remaining,decisions,max_checks-checks,max_steps-steps,library)
        calls+=1
        try:
            value,meta=provider.complete(prompt,CODE_SCHEMA,calls)
            if not isinstance(value,dict) or set(value)!={'code','summary'} or not all(isinstance(value[k],str) for k in value):
                raise ProviderError('Expected code and summary strings')
        except (ProviderError,OSError) as exc:
            provider_error=str(exc);termination='provider_error';break
        run=run_code(scene,value['code'],remaining=sorted(remaining),
                     library_source=library['library_source'] if library else '',
                     exports=library['exports'] if library else [],
                     max_checks=max_checks-checks,max_steps=max_steps-steps,timeout_seconds=execution_timeout)
        for t in run['trace']:
            trace.append({**t,'llm_call':calls,'global_checker_call':checks+t['checker_call']})
        for s in run['skill_calls']:skill_calls.append({**s,'llm_call':calls})
        actions.extend(run['actions']);remaining=frozenset(run['remaining']);checks+=run['checker_calls'];steps+=run['steps']
        decisions.append({'call':calls,'response':value,'metadata':meta,'execution':run,
                          'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()})
        for k,v in meta.get('usage',{}).items():
            if isinstance(v,(int,float)):usage[k]=usage.get(k,0)+v
    success=scene['target_id'] not in remaining
    if success:termination='goal_reached'
    elif provider_error is None:
        if checks>=max_checks:termination='check_budget_exhausted'
        elif steps>=max_steps:termination='execution_step_budget_exhausted'
    return {'scene_id':scene['id'],'method':'with_library' if library else 'no_library',
            'success':success,'termination':termination,'remaining':sorted(remaining),
            'actions':actions,'trace':trace,'skill_calls':skill_calls,'decisions':decisions,
            'checker_calls':checks,'execution_steps':steps,'llm_calls':calls,'token_usage':usage,
            'removed_count':len(actions) if success else None,'provider_error':provider_error,
            'elapsed_seconds':time.monotonic()-start,'library_sha256':library['sha256'] if library else None,
            'limits':{'max_calls':max_calls,'max_checks':max_checks,'max_steps':max_steps,'execution_timeout':execution_timeout},
            'scope':'Actual generated Python execution; trusted API budget includes skill internals. Synthetic 2D only.'}

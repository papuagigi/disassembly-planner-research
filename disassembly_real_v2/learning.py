"""Trace-conditioned code proposals; exact-source admission, never hidden hand edits."""
import argparse,copy,hashlib,json,time
from pathlib import Path
from .common import ROOT,read,write,digest,CONDITIONS,MODEL,EFFORT,prepare,LIMITS
from .memory import SkillBank,run_frontier,validate_record
from .study import sha
SCHEMA={'type':'object','properties':{'source':{'type':'string'},'failure_signature':{'type':'string'},'when_to_apply':{'type':'string'},'repair_strategy':{'type':'string'}},'required':['source','failure_signature','when_to_apply','repair_strategy'],'additionalProperties':False}

def proposed_bank(response,provenance):
 bank=read(ROOT/'memory/S5.json');source=response['source'];h=hashlib.sha256(source.encode()).hexdigest();sid='repair_'+h[:12]
 record={'id':sid,'source':source,'source_sha256':h,'triggers':[], 'failure_signature':response['failure_signature'],'when_to_apply':response['when_to_apply'],'repair_strategy':response['repair_strategy'],'provenance':provenance,'validation_status':'candidate'}
 validate_record(record,'frontier');bank['skills'].append(record);bank['skill_roles'][sid]='frontier';bank.update(version='S6',active_frontier_id=sid,parent_bank_sha256=bank['bank_sha256']);bank['bank_sha256']=digest({k:v for k,v in bank.items() if k!='bank_sha256'});return bank

def generate(number):
 from disassembly_mujoco.agent import CodexCLIProvider
 folder=ROOT/f'outputs/learning/candidate_{number:02d}';assert not (folder/'response.json').exists()
 base=read(ROOT/'memory/S5.json');old=next(s for s in base['skills'] if base['skill_roles'][s['id']]=='frontier')
 report=read(ROOT/'outputs/development/S5/asap_00431/result.json')
 failures={'case_role':'debug_only','trace':report['trace'],'checkpoint_metadata':[x['metadata'] for x in report['recovery_state']['checkpoints'].values()],
   'calls':[{'call':d['call'],'checks_before':d['checks_before'],'response':d.get('response'),'error':d.get('execution',{}).get('error')} for d in report['decisions']],
   'skill_calls':[{k:r.get(k) for k in ['state_key','checks_before','input_candidates','next_step','returned_handle','error']} for r in report['skill_calls'][:4]]}
 prior={}
 if number>1:
  p=ROOT/f'outputs/learning/candidate_{number-1:02d}';prior={'response':read(p/'response.json'),'validation':read(p/'validation.json')}
 prompt='''Return a reusable executable next_step skill learned from the attached real-CAD debug execution. No tools, filesystem, imports or execution yourself. This is a code-generation experiment. Return JSON matching schema. All part IDs/states/handles must be data-driven, no case-specific branches.
The existing procedure can abandon a successful child when a soft restore hint is acted on before checkpointing it, and can incorrectly declare global exhaustion once root edges are spent, without resuming unfinished deferred checkpoints. Repair this procedural failure. Keep existing ordering from candidates verbatim (first available). Keep exact-state attempted-edge tracking for committed/rejected REMOVE and rejected CHECK; a valid check or unexecuted proposal must not spend an edge. Consume history incrementally. The single target is a compatibility focus and can change: full task success is at most one remaining part, NOT focus removal.
Function signature EXACT: def next_step(observation,candidates,history,checkpoints,model_order,memory,restore_hint). Output dict keys operation (remove/restore/checkpoint/exhausted),action,handle,memory,evidence. No API calls; caller explicitly dispatches. Save unfinished current child BEFORE obeying a soft ancestor hint. Track deferred reachable checkpoint states, including branches outside current ancestor chain. On local exhaustion restore nearest unfinished ancestor; if none, resume a saved unfinished deferred checkpoint before global exhausted. Do not revisit exhausted branches. A confirmed soft restore should not be endlessly proposed when resuming its child; only confirm executed restore when actual observation reaches destination. Ignored proposals must remain available. Checkpoint and restore operations themselves do not consume an action edge. A checkpoint budget is caller's constraint. Preserve existing semantic priority/order/restore stages; implement only frontier repair. In particular do not hard-code a full sequence, do not restore arbitrary unvisited incompatible states, do not synthesize checkpoint handles.
Inputs observation has state_key, target_id, remaining_parts, accepted_action_prefix, goal_type, remaining_part_count; checkpoints is LIST of dict(handle,state_key,remaining_parts,accepted_action_prefix); history is full physical trace with operation,part_id,direction,valid,committed,physical_state_key_before/after. memory persists exact JSON across calls; initially {}. Pure returned memory needs no fixed old key layout. Our stage permits 150000 opcodes and .3s, so don't repeatedly scan long old history; process suffix since cursor. Avoid copying all candidate ledgers into each frame. Long memory must survive.
Restricted Python: ordinary functions/lists/dicts/sets, loops/comprehensions, sort with lambda, sum/min/max/len/range/sorted/reversed/int/str/bool allowed. No imports, classes, exceptions, type,isinstance,getattr,reflection,private attributes,with, while True unbounded. No literal numeric-string part IDs. Helper functions allowed. Keep code compact. Include failure signature, apply guard and repair strategy.
'''+json.dumps({'old_source':old['source'],'real_debug_failure':failures,'prior_candidate_feedback':prior},ensure_ascii=False)
 write(folder/'input.json',{'prompt':prompt,'debug_result_sha256':sha(ROOT/'outputs/development/S5/asap_00431/result.json'),'validation_product_not_in_prompt':'00494'})
 response,meta=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=180).complete(prompt,SCHEMA,1)
 write(folder/'response.json',response);write(folder/'metadata.json',meta)
 try:
  bank=proposed_bank(response,dict(generator_model=MODEL,reasoning_effort=EFFORT,source='live trace-conditioned LLM response; unedited',response_path=str(folder/'response.json'),response_sha256=sha(folder/'response.json'),debug_case='asap_00431'))
  write(folder/'bank.json',bank)
 except Exception as exc:
  write(folder/'validation.json',{'status':'FAIL','compile_error':repr(exc)});raise
 print(json.dumps({'candidate':number,'source_sha256':bank['skills'][-1]['source_sha256'],'usage':meta.get('usage')}),flush=True)

def unit_gate(bank):
 tests=[];record=SkillBank(bank).frontier
 def call(obs,actions,history,cps,memory,hint=''):
  r=run_frontier(record,obs,actions,history,cps,[],memory,hint,150000)
  if r['error']:raise AssertionError(r['error'])
  return r['output']
 def check(name,fn):
  try:fn();tests.append({'name':name,'pass':True})
  except Exception as e:tests.append({'name':name,'pass':False,'error':repr(e)})
 a={'part_id':'bolt','direction':'+z'};b={'part_id':'shaft','direction':'+x'}
 root={'state_key':'root-state','target_id':'shaft','remaining_parts':[{'id':'bolt'},{'id':'shaft'},{'id':'base','fixed':True}],'accepted_action_prefix':[],'remaining_part_count':3,'goal_type':'full_disassembly'}
 child={**root,'state_key':'child-state','remaining_parts':[{'id':'shaft'},{'id':'base','fixed':True}],'accepted_action_prefix':[a],'remaining_part_count':2}
 cp0={'handle':'cp-root','state_key':root['state_key'],'remaining_parts':['bolt','shaft','base'],'accepted_action_prefix':[]}
 cp1={'handle':'cp-child','state_key':child['state_key'],'remaining_parts':['shaft','base'],'accepted_action_prefix':[a]}
 h=[dict(operation='remove',part_id='bolt',direction='+z',valid=True,committed=True,physical_state_key_before='root-state',physical_state_key_after='child-state')]
 def checkpoint_before_hint():
  r=call(child,[b],h,[cp0],{},'cp-root');assert r['operation']=='checkpoint',r
 check('unfinished_child_checkpoint_before_soft_restore',checkpoint_before_hint)
 def ignored():
  r=call(child,[b],h,[cp0,cp1],{},'cp-root');assert r['operation']=='restore',r
  s=call(child,[b],h,[cp0,cp1],r['memory'],'cp-root');assert s['operation']=='restore' and s['handle']=='cp-root',s
 check('ignored_restore_not_counted_as_executed',ignored)
 def resume():
  r=call(child,[b],h,[cp0,cp1],{},'cp-root');assert r['operation']=='restore',r
  r=call(root,[a],h,[cp0,cp1],r['memory']);assert r['operation']=='restore' and r['handle']=='cp-child',r
  r=call(child,[b],h,[cp0,cp1],r['memory'],'cp-root');assert r['operation']=='remove' and r['action']==b,r
  r=call(child,[b],h,[cp0,cp1],r['memory'],'cp-root');assert r['operation']=='remove' and r['action']==b,r
 check('resume_deferred_child_after_root_exhaustion_and_keep_unexecuted_edge',resume)
 def end():
  r=call(child,[b],h,[cp0,cp1],{},'cp-root');r=call(root,[a],h,[cp0,cp1],r['memory']);r=call(child,[b],h,[cp0,cp1],r['memory'])
  h2=h+[dict(operation='remove',part_id='shaft',direction='+x',valid=False,committed=False,physical_state_key_before='child-state',physical_state_key_after='child-state')]
  r=call(child,[b],h2,[cp0,cp1],r['memory']);assert r['operation']=='exhausted',r
 check('true_global_exhaustion_no_checkpoint_cycle',end)
 def exact():
  h2=[dict(operation='remove',part_id='shaft',direction='+x',valid=False,committed=False,physical_state_key_before='different-state',physical_state_key_after='different-state')]
  r=call(child,[b],h2,[cp0,cp1],{});assert r['operation']=='remove' and r['action']==b,r
 check('exact_state_failures_do_not_prune_new_state',exact)
 def order():
  r=call(root,[b,a],[],[cp0],{});assert r['operation']=='remove' and r['action']==b,r
 check('input_skill_order_retained',order)
 def long():
  hist=[dict(operation='remove',part_id='pin',direction='+z',valid=False,physical_state_key_before='old-state',physical_state_key_after='old-state') for i in range(300)]
  r=call(child,[b],hist,[cp0,cp1],{});assert r['operation']=='remove',r
  r['memory']['large_retained_marker']=['entry-'+str(i) for i in range(400)]
  r=call(child,[b],hist,[cp0,cp1],r['memory']);assert r['memory']['large_retained_marker'][-1]=='entry-399'
 check('long_trace_incremental_and_memory_not_truncated',long)
 return tests

def physical_gate(bank,case):
 from .runtime import run_code
 shared_path=ROOT/'outputs/development/shared'/f"{case['case_id']}.json";shared=read(shared_path)
 # Harness intentionally dispatches exactly the skill proposal. It is not a model score.
 code="""for tick in range(300):
    obs=api.snapshot()
    if obs.get('remaining_part_count',99)<=1:
        break
    candidates=[]
    for part in obs['remaining_parts']:
        if not part.get('fixed',False):
            for direction in part.get('allowed_directions',['+x','-x','+y','-y','+z','-z']):
                candidates.append({'part_id':part['id'],'direction':direction})
    step=skills.next_step(candidates)
    if step['operation']=='remove':
        api.remove(step['action']['part_id'],step['action']['direction'])
    elif step['operation']=='restore':
        api.restore(step['handle'])
    elif step['operation']=='checkpoint':
        api.checkpoint()
    else:
        break
"""
 result=run_code(case['case_path'],code,state=shared['state'],recovery_state=shared['recovery_state'],library_bank=bank,max_checks=LIMITS['max_checks'],max_steps=LIMITS['max_steps'],timeout_seconds=480,max_checkpoints=128,max_restores=256)
 result.update(case_id=case['case_id'],harness_only=True,model_calls=0)
 return result

def validate(number):
 folder=ROOT/f'outputs/learning/candidate_{number:02d}';bank=read(folder/'bank.json');units=unit_gate(bank)
 oldunits=unit_gate(read(ROOT/'memory/S5.json'));rows=[]
 if all(t['pass'] for t in units):
  for case in read(ROOT/'outputs/development/selection.json')['cases']:
   result=physical_gate(bank,case);write(folder/f"physical_{case['case_id']}.json",result)
   rows.append({'case_id':case['case_id'],'role':case['development_role'],'success':result['success'],'error':result['error'],'checks':result['checker_calls'],'bank_steps':result.get('bank_steps'),'final_removals':len(result['state']['actions']),'skill_errors':[r.get('error') for r in result['skill_calls'] if r.get('error')]})
 # Debug geometry need not become solvable: it must explore the dropped child; independent validation keeps full success.
 debug=next((r for r in rows if r['role']=='debug'),{});valid=next((r for r in rows if r['role']=='validation'),{})
 passed=all(t['pass'] for t in units) and bool(rows) and all(not r['error'] and not r['skill_errors'] for r in rows) and debug.get('checks',0)>24 and valid.get('success',False)
 report=dict(status='PASS' if passed else 'FAIL',candidate=number,unit_tests=units,S5_unit_tests=oldunits,physical_validation=rows,
  admission_rule='All behavioral invariants; debug explores beyond old 24-check root-only frontier; independent development validation retains full success; no skill/runtime error.',generated_source_exact=sha(folder/'response.json')==bank['skills'][-1]['provenance']['response_sha256'])
 write(folder/'validation.json',report);print(json.dumps(report),flush=True)
 if passed:
  dst=ROOT/'memory/S6.json';assert not dst.exists();bank['skills'][-1]['validation_status']='validated';bank['skills'][-1]['validation_receipt']=str(folder/'validation.json');bank['bank_sha256']=digest({k:v for k,v in bank.items() if k!='bank_sha256'});write(dst,bank)
  assert bank['skills'][-1]['source']==read(folder/'response.json')['source']
  write(ROOT/'outputs/learning/admission.json',dict(status='PASS',candidate=number,validation_sha256=sha(folder/'validation.json'),bank_file_sha256=sha(dst),bank_sha256=bank['bank_sha256'],active_frontier_id=bank['active_frontier_id'],retained_parent_skill_ids=[s['id'] for s in read(ROOT/'memory/S5.json')['skills']],source_unedited=True,generated_source_sha256=bank['skills'][-1]['source_sha256']))
 return passed

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['generate','validate']);p.add_argument('--candidate',type=int,default=1);a=p.parse_args()
 if a.command=='generate':generate(a.candidate)
 else:validate(a.candidate)

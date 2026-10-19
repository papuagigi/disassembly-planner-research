"""Post-evaluation feasible reference sequences. Not an optimality oracle."""
import copy,json,time,os
from pathlib import Path
from .common import ROOT,read,write
from .study import manifest,sha
from .simulator import FullDisassemblySim
from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_recovery.shared_api import physical_state_key
from .analysis.progress_evidence import annotate_frames

CHECKS=2400
SECONDS=180

def offline_search(case,shared):
 start=time.monotonic();sim=FullDisassemblySim(case['case_path'],max_checks=CHECKS,state=shared['state'])
 api=SharedAPI(sim,recovery_state=shared['recovery_state'],max_checks=CHECKS,max_checkpoints=4096,max_restores=4096)
 tried={};best=[];limit=False
 def dfs():
  nonlocal best,limit
  if sim.success:return True
  if sim.checks>=CHECKS or time.monotonic()-start>=SECONDS:limit=True;return False
  key=physical_state_key(sim.export_state());spent=tried.setdefault(key,set());h=api.checkpoint()
  obs=api.snapshot();parts=sorted([p for p in obs['remaining_parts'] if not p.get('fixed')],key=lambda p:(-p['center'][2],p['id']))
  for p in parts:
   for d in ['+z','+x','-x','+y','-y','-z']:
    if (p['id'],d) in spent or d not in p['allowed_directions']:continue
    if sim.checks>=CHECKS or time.monotonic()-start>=SECONDS:limit=True;return False
    spent.add((p['id'],d));r=api.remove(p['id'],d)
    if r.get('valid'):
     if len(sim.actions)>len(best):best=copy.deepcopy(sim.actions)
     if dfs():return True
     api.restore(h)
     if limit:return False
  return False
 success=dfs()
 return dict(success=success,actions=copy.deepcopy(sim.actions) if success else [],best_partial=best,trace=sim.trace,
  recovery_state=api.export_recovery_state(),state=sim.export_state(),checks=sim.checks,elapsed_seconds=time.monotonic()-start,
  termination='feasible_sequence_found' if success else 'offline_bound_reached' if limit else 'enumerated_frontier_exhausted',
  limits={'checks':CHECKS,'seconds':SECONDS},method='deterministic height-first DFS; six directions; exact-state visited edges',new_llm_calls=0)

def verify_sequence(case,actions,folder,reference,return_url):
 sim=FullDisassemblySim(case['case_path'],max_checks=max(1,len(actions)),capture=True);api=SharedAPI(sim,max_checks=max(1,len(actions)))
 steps=[];events=[]
 for ordinal,a in enumerate(actions,1):
  r=api.remove(a['part_id'],a['direction']);assert r['valid'] and r['committed']
  sim._record_frame(f"참고 순서 {ordinal}: 부품 {a['part_id']} {a['direction']}",advance=.8)
  frame=len(sim.frames)-1;sim.frames[-1].update(phase='commit',checks_spent=sim.checks,run_stage='offline_reference')
  steps.append(dict(step=ordinal,part_id=a['part_id'],direction=a['direction'],frame=frame,reason=r['reason'],stability=r.get('stability')))
  events.append(dict(frame=frame,time=sim.frames[-1]['time'],type='commit',message=f"참고 {ordinal} · 부품 {a['part_id']} {a['direction']}",detail='동일 물리 설정에서 다시 검증한 가능한 순서',checks_spent=sim.checks))
 assert sim.success
 receipt=dict(status='VERIFIED_FEASIBLE',source=reference,steps=steps,unique=False,optimality_proven=False,
  same_case_sha256=sha(case['case_path']),final_state_key=physical_state_key(sim.export_state()),trace=sim.trace,
  note='A valid order under this simulator/action/fixture model; not a unique ground truth or manufacturing instruction.')
 write(folder/'verified_sequence.json',receipt)
 summary=dict(success=True,reference=True,termination='reference_feasible',description='평가 후 별도로 검증한 가능한 순서 · A/B/C 점수와 무관',
  model='LLM 사용 안 함',reasoning_effort='offline',method='offline_reference',track='reference',repeat=0,library_enabled=False,
  bank_version=None,physics_checks=sim.checks,failed_attempts=0,planner_failed_attempts=0,preparation_checks=0,llm_calls=0,restores=0,
  required_removals=len(sim.parts)-1,final_completed_removals=len(actions),best_completed_removals=len(actions),budget={'max_calls':0,'max_checks':len(actions),'timeout_seconds':SECONDS},
  physics=sim.case['physics'],replay_audit='PASS')
 sim.events=events;target=folder/'episode.json';sim.dump_demo(target,title='검증된 참고 분해 순서 · 평가 외',summary=summary)
 ep=read(target);ep.update(schema='abc_actual_replay_v2',case_id=case['case_id'],assembly_display_name=f"ASAP {case['source_assembly_id']} · 검증된 참고 순서",assembly_source_note='평가 후 검증 · 유일한 정답/최적 순서 아님',
  reference_sequence={'status':'VERIFIED_FEASIBLE','steps':steps,'source':reference,'episode_url':'episode.json','optimality_proven':False},
  planner_start_frame=0,restore_frames=[],failure_frames=[],diagnostics=[],learning={'library_enabled':False,'retrievals':[]},return_episode_url=return_url,
  actual_source={'result_url':'verified_sequence.json','result_sha256':sha(folder/'verified_sequence.json')})
 annotate_frames(ep);write(target,ep);return receipt

def main():
 assert (ROOT/'outputs/evaluation/complete.json').exists(),'Reference work must follow frozen scores'
 v=manifest();index=read(ROOT/'replay/index.json');results=[]
 for case in v['cases']:
  folder=ROOT/'replay/reference'/case['case_id'];folder.mkdir(parents=True,exist_ok=True)
  if (folder/'summary.json').exists():raise FileExistsError('Reference already computed; do not rerun to pick a nicer order')
  found=[]
  for p in (ROOT/'outputs/evaluation/trials'/case['case_id']).rglob('result.json'):
   r=read(p)
   if r['success']:found.append((r['checker_calls'],str(p),r))
  first=next(e for e in index['episodes'] if e['case_id']==case['case_id'] and e['available'])
  return_url=first['url']
  if found:
   _,path,run=sorted(found,key=lambda x:(x[0],x[1]))[0];actions=run['actions'];source={'type':'retained_successful_evaluation_path','result_path':path,'sha256':sha(path),'selection':'fewest checks, then path name; post-evaluation only'}
  else:
   search=offline_search(case,read(case['tracks']['normal']['path']));write(folder/'search.json',search)
   actions=search['actions'];source={'type':'offline_deterministic_search','checks':search['checks'],'elapsed_seconds':search['elapsed_seconds'],'termination':search['termination'],'new_llm_calls':0,'limits':search['limits']}
  if actions:
   receipt=verify_sequence(case,actions,folder,source,return_url)
   info={'status':'VERIFIED_FEASIBLE','steps':receipt['steps'],'source':source,'optimality_proven':False,'unique':False,'episode_path':str((folder/'episode.json').resolve())}
  else:info={'status':'NOT_FOUND_WITHIN_DECLARED_MODEL_AND_BOUND','steps':[],'source':source,'note':'No impossibility or unique-ground-truth claim.'}
  write(folder/'summary.json',info);results.append({'case_id':case['case_id'],**info})
  for entry in index['episodes']:
   if entry['case_id']!=case['case_id'] or not entry['available']:continue
   path=(ROOT/'viewer'/entry['url']).resolve();ep=read(path);item=copy.deepcopy(info)
   if item.get('episode_path'):item['episode_url']=os.path.relpath(item.pop('episode_path'),path.parent)
   ep['reference_sequence']=item;ep['verified_final_sequence']=[dict(step=i+1,part_id=a['part_id'],direction=a['direction']) for i,a in enumerate(read(ROOT/'outputs/evaluation/trials'/case['case_id']/'normal/repeat_01'/entry['method']/'result.json')['actions'])]
   write(path,ep);entry['episode_sha256']=sha(path)
  print(json.dumps({'case_id':case['case_id'],'reference':info['status'],'steps':len(actions)}),flush=True)
 write(ROOT/'replay/reference/index.json',{'scope':'Offline post-evaluation, not supplied to planners','cases':results})
 write(ROOT/'replay/index.json',index);manifest()

if __name__=='__main__':main()

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
 assert (ROOT/'outputs/evaluation/complete.json').exists(), 'Reference UI attachment follows scored episodes'
 v=manifest();index=read(ROOT/'replay/index.json');rows=[]
 for case in v['cases']:
  folder=ROOT/'replay/reference'/case['case_id'];folder.mkdir(parents=True,exist_ok=True)
  assert not (folder/'verified_sequence.json').exists(), 'Do not replace a verified replay'
  witness=read(case['reference']['local_validation_path'])
  actions=witness['actions'];assert witness['success']
  first=next(e for e in index['episodes'] if e['case_id']==case['case_id'] and e['available'])
  source={'type':'withheld_evaluator_qualification_witness',
   'source_certificate_path':case['reference']['source_certificate_path'],
   'local_validation_path':case['reference']['local_validation_path'],
   'never_supplied_to_actors':True,'unique':False,'optimality_proven':False}
  receipt=verify_sequence(case,actions,folder,source,first['url'])
  info={'status':'VERIFIED_FEASIBLE','steps':receipt['steps'],'source':source,
   'optimality_proven':False,'unique':False,'episode_path':str((folder/'episode.json').resolve())}
  write(folder/'summary.json',info);rows.append({'case_id':case['case_id'],**info})
  for entry in index['episodes']:
   if entry['case_id']!=case['case_id'] or not entry['available']:continue
   ep_path=(ROOT/'viewer'/entry['url']).resolve();ep=read(ep_path)
   ep['reference_sequence']={**info,'episode_url':os.path.relpath(folder/'episode.json',ep_path.parent)}
   write(ep_path,ep)
 write(ROOT/'replay/reference/index.json',{'status':'PASS','cases':rows,'new_llm_calls':0})
 print(json.dumps({'status':'PASS','verified_full_sequences':len(rows)}),flush=True)
if __name__=='__main__':main()

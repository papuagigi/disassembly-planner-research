"""Append-only real CAD development and first-encounter study."""
import argparse, hashlib, json, time, sys, subprocess
from datetime import datetime, timezone
from pathlib import Path
from .common import ROOT, WORKSPACE, MODEL, EFFORT, LIMITS, CONDITIONS, read, write, digest, prepare, solve, neutral_observation_hash
from .memory import SkillBank

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
def progress(phase,**details):
 row=dict(phase=phase,updated_utc=now(),owner='Codex',claude_assigned=False,**details)
 write(ROOT/'outputs/progress.json',row)
 with (ROOT/'outputs/journal.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
def sources():
 old=read(WORKSPACE/'disassembly_real_v1/outputs/protocol/freeze.json')['source_sha256']
 return sorted(set(map(Path,old))|set(ROOT.glob('*.py'))|set((ROOT/'data_tools').glob('*.py')),key=str)
def verify_pre():
 v=read(ROOT/'outputs/protocol/before_fresh_source_freeze.json')
 for p,h in v['source_sha256'].items():assert sha(p)==h,('Code changed after freeze',p)
 for b in v['banks'].values():assert sha(b['path'])==b['file_sha256']
 return v

def freeze():
 out=ROOT/'outputs/protocol/before_fresh_source_freeze.json';assert not out.exists()
 admission=read(ROOT/'outputs/learning/admission.json');assert admission['status']=='PASS'
 old=read(WORKSPACE/'disassembly_real_v1/outputs/protocol/before_fresh_source_freeze.json')
 forbidden=set(old['forbidden_source_ids'])
 forbidden.update(p.name for p in (WORKSPACE/'disassembly_real_v1/data/source/asap_training').iterdir() if p.is_dir())
 forbidden.update(['00503','00525','00568','00614'])
 banks={name:dict(path=str((ROOT/f'memory/{name}.json').resolve()),file_sha256=sha(ROOT/f'memory/{name}.json'),bank_sha256=SkillBank(ROOT/f'memory/{name}.json').sha256) for name in ['S5','S6']}
 value=dict(status='FROZEN_BEFORE_SOURCE_FETCH',created_utc=now(),model=MODEL,reasoning_effort=EFFORT,limits=LIMITS,
  source_sha256={str(p.resolve()):sha(p) for p in sources()},banks=banks,forbidden_source_ids=sorted(forbidden),
  development_ids=['00431','00494','00503','00525','00568','00614'],admission_sha256=sha(ROOT/'outputs/learning/admission.json'),
  fresh_rule=dict(min_parts=5,max_parts=12,min_obj_bytes=100000,max_obj_bytes=1000000,after_id='00614',source_count=8,requested_cases=3,order='ascending original ID; mechanical source review and fixed physical gate only'),
  conditions=list(CONDITIONS),supplemental=['B_S5','C_S5'],tracks=['normal'],track_repetitions={'normal':1},
  interpretation='First budgeted episode per case/arm; no test bank update; A/B/C architecture comparison, S5/S6 within-method learning ablation; no desired winner',
  task='full_disassembly',skill_stage_limits={'opcodes':150000,'wall_seconds':.3},
  physical_scope='six-axis kinematic extraction; MuJoCo residual gravity/contact/friction; one original fixed anchor at most; initial whole assembly stable')
 write(out,value)
 for p in sources():
  dst=ROOT/'outputs/protocol/source_snapshot'/p.relative_to(WORKSPACE);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(p.read_bytes())
 progress('frozen_before_fresh_source',source_files=len(value['source_sha256']))
 print(json.dumps({'status':value['status'],'sources':len(value['source_sha256'])}),flush=True)

def run_one(case,arm,shared,folder,bank_version='S6',first=False,protocol=None):
 from disassembly_mujoco.agent import CodexCLIProvider
 assert not (folder/'started.json').exists(), 'Never repeat an already started episode'
 write(folder/'started.json',dict(utc=now(),arm=arm,bank=bank_version,first_encounter=first))
 method=CONDITIONS[1] if arm=='B_S5' else CONDITIONS[2] if arm=='C_S5' else arm
 bank_name='S5' if arm.endswith('_S5') else bank_version
 bank=ROOT/f'memory/{bank_name}.json'
 provider=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
 started=time.monotonic()
 result=solve(case,method,provider,shared,bank_path=bank if method!=CONDITIONS[0] else None)
 result.update(case_id=case['case_id'],case_path=case['case_path'],source_assembly_id=case['source_assembly_id'],condition=arm,method=arm,
  base_method=method,track='normal',repeat=1,model=MODEL,reasoning_effort=EFFORT,limits=LIMITS,
  first_encounter=first,preparation_checks=shared['state']['checks'],preparation_seconds=shared['preparation_seconds'],
  expected_initial_observation_sha256=neutral_observation_hash(shared['observation']),elapsed_seconds_total=time.monotonic()-started,
  goal_type='full_disassembly',library_available=method!=CONDITIONS[0],bank_version=bank_name if method!=CONDITIONS[0] else None,
  bank_sha256=SkillBank(bank).sha256 if method!=CONDITIONS[0] else None,protocol_sha256=protocol)
 write(folder/'result.json',result)
 print(json.dumps({k:result.get(k) for k in ['case_id','condition','success','termination','checker_calls','llm_calls','elapsed_seconds_total']}),flush=True)
 return result

def development(bank='S5',method=None):
 method=method or CONDITIONS[1]
 selection=read(ROOT/'outputs/development/selection.json')
 for i,case in enumerate(selection['cases']):
  folder=ROOT/f'outputs/development/{bank if method==CONDITIONS[1] else bank+"_C"}'/case['case_id']
  if (folder/'result.json').exists():continue
  shared_path=ROOT/'outputs/development/shared'/f"{case['case_id']}.json"
  if not shared_path.exists():write(shared_path,prepare(case))
  progress('development_B',case=case['case_id'],bank=bank,role='debug' if i==0 else 'validation')
  run_one(case,method,read(shared_path),folder,bank_version=bank)

def bind_inputs():
 pre=verify_pre();dst=ROOT/'outputs/evaluation/manifest.json';assert not dst.exists()
 selection=read(ROOT/'outputs/input_audit/selected_cases.json');assert selection['cases']
 cases=[];assets={}
 for row in selection['cases']:
  cp=Path(row['case_path']);case=read(cp);paths={cp}
  for p in case['parts']:
   paths.add((cp.parent/p['visual_mesh']).resolve());paths.update((cp.parent/s).resolve() for s in p['collision_meshes'])
  assets.update({str(p.resolve()):sha(p) for p in paths})
  shared=prepare(row);p=ROOT/'outputs/evaluation/shared_inputs'/row['case_id']/'normal.json';write(p,shared)
  cases.append({**row,'tracks':{'normal':{'path':str(p),'sha256':sha(p),'observation_sha256':neutral_observation_hash(shared['observation']),'preparation_checks':shared['state']['checks'],'preparation_seconds':shared['preparation_seconds']}},'reference':{'scope':'not used for selection or evaluation','minimum_removals':None}})
 value={**pre,'source_catalog_path':selection['source_catalog_path'],'source_catalog_sha256':selection['source_catalog_sha256'],'cases':cases,'asset_sha256':assets,'planned_cases':len(cases),'planned_trials':len(cases)*5,'selected_cases_sha256':sha(ROOT/'outputs/input_audit/selected_cases.json')}
 value['manifest_sha256']=digest(value);write(dst,value);progress('inputs_bound',planned_trials=value['planned_trials'])

def manifest():
 verify_pre();v=read(ROOT/'outputs/evaluation/manifest.json');assert digest({k:x for k,x in v.items() if k!='manifest_sha256'})==v['manifest_sha256']
 for p,h in v['asset_sha256'].items():assert sha(p)==h
 for c in v['cases']:assert sha(c['tracks']['normal']['path'])==c['tracks']['normal']['sha256']
 return v

def worker(i,arm):
 v=manifest();c=v['cases'][i];folder=ROOT/'outputs/evaluation/trials'/c['case_id']/'normal/repeat_01'/arm
 run_one(c,arm,read(c['tracks']['normal']['path']),folder,first=True,protocol=v['manifest_sha256'])

def evaluate():
 v=manifest();arms=list(CONDITIONS)+['B_S5','C_S5'];schedule=[]
 for i,c in enumerate(v['cases']):
  order=arms[i%len(arms):]+arms[:i%len(arms)]
  for a in order:schedule.append((i,c['case_id'],a))
 schedule_path=ROOT/'outputs/evaluation/schedule.json'
 if not schedule_path.exists():write(schedule_path,dict(schedule=schedule,created_utc=now()))
 for i,c,a in schedule:
  folder=ROOT/'outputs/evaluation/trials'/c/'normal/repeat_01'/a
  if (folder/'result.json').exists():continue
  if (folder/'started.json').exists():raise RuntimeError('Interrupted first episode requires retained failure, not rerun: '+str(folder))
  progress('first_encounter_evaluation',case=c,arm=a)
  p=subprocess.run([sys.executable,'-B','-m','disassembly_real_v2.study','worker','--index',str(i),'--arm',a])
  if p.returncode:raise RuntimeError('Episode subprocess failed; retain logs')
 manifest();write(ROOT/'outputs/evaluation/complete.json',dict(status='COMPLETE',utc=now(),trials=len(schedule)))
 progress('evaluation_complete',trials=len(schedule))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['development','freeze','bind','evaluate','worker']);p.add_argument('--bank',default='S5');p.add_argument('--index',type=int);p.add_argument('--arm');a=p.parse_args()
 if a.command=='development':development(a.bank,a.arm)
 elif a.command=='freeze':freeze()
 elif a.command=='bind':bind_inputs()
 elif a.command=='evaluate':evaluate()
 else:worker(a.index,a.arm)

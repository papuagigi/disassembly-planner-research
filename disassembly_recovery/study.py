"""Predeclared same-budget comparison, retaining all scheduled outcomes."""
import argparse,copy,hashlib,importlib.metadata,json,os,signal,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
from .common import MODEL,EFFORT,LIMITS,METHODS,prepare_shared,write,digest,neutral_observation_hash
ROOT=Path(__file__).resolve().parent; WORKSPACE=ROOT.parent

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
 return [ROOT/n for n in ['common.py','shared_api.py','shared_observation.py','runtime.py','library_functions.py','code_actor.py','hybrid_actor.py','study.py']]+[WORKSPACE/n for n in ['disassembly_mujoco/simulator.py','disassembly_mujoco/agent.py','disassembly_hybrid/graph.py','disassembly_hybrid/common.py','disassembly_planner_2d/planner2d/llm.py','disassembly_planner_2d/planner2d/code_runtime.py','disassembly_planner_2d/planner2d/code_worker.py']]
def actor_freeze():
 from .code_actor import load_library
 p=ROOT/'outputs/protocol/actor_freeze.json'
 if p.exists():raise RuntimeError('Already frozen')
 m={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'model':MODEL,'reasoning_effort':EFFORT,'limits':LIMITS,
 'repetitions':3,'tracks':['normal','seeded'],'methods':METHODS,'planned_trials':54,
 'source_sha256':{str(p):sha(p)for p in sources()},'library_sha256':digest(load_library()),
 'generator_sha256':sha(ROOT/'data_tools/build_recovery_family.py'),
 'development':'Old eval_design_01/02/03 are development only. New geometry generated after this freeze. Model probe is exploratory development evidence only.',
 'primary_model_choice':'Retain prior Luna to separate structure improvement from model upgrade. Stronger-model code-arm pilots are reported separately, never pooled with primary held-out evaluation.',
 'fairness':'All arms receive identical frozen track-specific state, observation, checkpoint registry and same public API. Caps equal, actual calls and tokens measured. Within-episode feedback memory allowed to all; no cross-evaluation learning. B/C receive same executable skill source. B-C is a systems comparison, not an isolated single-factor effect.',
 'budget':'120 physics calls include 6 initial probes and seeded preparation removal (1 if seeded). 8 model calls, 480 seconds total, 10M planner opcodes as safety bound (not identical FLOPs),128 checkpoints,256 restores. Code turn maximum120seconds. Restores never refund any cost.',
 'physics_scope':'Actual designed 3D OBJ, six-axis sampled straight extraction with unchanged MuJoCo gravity/friction residual-stability checker. Not real product CAD, force-driven extraction, grasping or robot dynamics.',
 'tracks':'normal begins fully assembled. seeded begins after same certified valid wrong support removal with original checkpoint, not a spontaneous model mistake. No privileged roles/paths/certificates enter model inputs.',
 'failure_policy':'All scheduled trials retained, no silent retry or heuristic substitute. Budget failure UNKNOWN, not physical impossibility.',
 'sampling':'Three geometry variants of one designed family, each repeated3times. Repeats are not independent products; model backend seed/temperature/snapshot not exposed.'}
 m['manifest_sha256']=digest(m);write(p,m);write(ROOT/'outputs/protocol/library.json',load_library())
 for source in sources():
  dest=ROOT/'outputs/protocol/source_snapshot'/source.relative_to(WORKSPACE);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read_bytes())
 print(json.dumps({'actor_freeze':str(p),'sha256':sha(p),'manifest_sha256':m['manifest_sha256']}),flush=True)

def verify():
 m=read(ROOT/'outputs/protocol/actor_freeze.json')
 assert digest({k:v for k,v in m.items()if k!='manifest_sha256'})==m['manifest_sha256']
 for p,h in m['source_sha256'].items():assert sha(p)==h,('Frozen source changed',p)
 return m

def prepare():
 frozen=verify();index=read(ROOT/'outputs/input_audit/selected_cases.json')
 assert index['all_three_variants_certified']
 p=ROOT/'outputs/evaluation/manifest.json'
 if p.exists():raise RuntimeError('Already prepared')
 cases=[];assets={}
 for row in index['cases']:
  case=Path(row['case_path']);case_data=read(case)
  paths={case}
  for part in case_data['parts']:
   paths.add((case.parent/part['visual_mesh']).resolve())
   paths.update((case.parent/x).resolve()for x in part['collision_meshes'])
  assets.update({str(x):sha(x)for x in paths})
  cert=read(row['selection_report']);wrong={k:cert['wrong_action'][k]for k in ['part_id','direction']}
  entry={k:row[k]for k in ('case_id','case_path','part_count','target_id','selection_report','reference','parameters')};entry['tracks']={}
  for track in ['normal','seeded']:
   state,obs,reg=prepare_shared(case,LIMITS['max_checks'],wrong if track=='seeded' else None)
   path=ROOT/'outputs/evaluation/shared_inputs'/row['case_id']/(track+'.json')
   write(path,{'state':state,'observation':obs,'recovery_state':reg})
   entry['tracks'][track]={'path':str(path),'sha256':sha(path),'observation_sha256':neutral_observation_hash(obs),'preparation_checks':state['checks']}
  cases.append(entry)
 m={**frozen,'cases':cases,'asset_sha256':assets,'runtime':{k:importlib.metadata.version(k)for k in ['mujoco','numpy','scipy','trimesh']},'actor_freeze_file_sha256':sha(ROOT/'outputs/protocol/actor_freeze.json')}
 m.pop('manifest_sha256');m['manifest_sha256']=digest(m);write(p,m)
 print(json.dumps({'prepared':len(cases),'trials':m['planned_trials'],'manifest_sha256':m['manifest_sha256']}),flush=True)

def manifest():
 verify();m=read(ROOT/'outputs/evaluation/manifest.json')
 assert digest({k:v for k,v in m.items()if k!='manifest_sha256'})==m['manifest_sha256']
 for p,h in m['asset_sha256'].items():assert sha(p)==h,('Asset changed',p)
 for c in m['cases']:
  for t in c['tracks'].values():assert sha(t['path'])==t['sha256']
 return m

def worker(ci,repeat,method,track):
 m=manifest();c=m['cases'][ci];folder=ROOT/'outputs/evaluation/trials'/c['case_id']/track/('repeat_%02d'%repeat)/method
 write(folder/'started.json',{'timestamp_utc':datetime.now(timezone.utc).isoformat(),'model':m['model']})
 v=read(c['tracks'][track]['path'])
 from .code_actor import CodexCLIProvider,solve_code
 p=CodexCLIProvider(folder/'llm_calls',model=m['model'],reasoning_effort=m['reasoning_effort'],timeout=120)
 start=time.monotonic();kwargs=dict(initial_state=v['state'],initial_observation=v['observation'],recovery_state=v['recovery_state'],**m['limits'])
 if method=='graph_llm_dfs_library':
  from .hybrid_actor import solve_hybrid
  r=solve_hybrid(c['case_path'],p,**kwargs)
 else:r=solve_code(c['case_path'],p,library=read(ROOT/'outputs/protocol/library.json')if method=='code_with_library'else None,**kwargs)
 r.update(case_id=c['case_id'],case_path=c['case_path'],method=method,track=track,repeat=repeat,model=m['model'],reasoning_effort=m['reasoning_effort'],
          limits=m['limits'],protocol_sha256=m['manifest_sha256'],elapsed_seconds_total=time.monotonic()-start,
          initial_observation_sha256=neutral_observation_hash(v['observation']),preparation_checks=v['state']['checks'],
          minimum_removals=c['reference']['minimum_removals'])
 r['successful_restores']=r.get('recovery_state',{}).get('restore_count',0)
 write(folder/'result.json',r)
 print(json.dumps({k:r.get(k)for k in ['case_id','method','track','repeat','success','termination','checker_calls','llm_calls','successful_restores','elapsed_seconds_total']}),flush=True)

def evaluate():
 m=manifest();schedule=[]
 for ci,c in enumerate(m['cases']):
  for repeat in range(1,4):
   for ti,track in enumerate(['normal','seeded']):
    offset=(ci+repeat+ti-1)%3
    for method in METHODS[offset:]+METHODS[:offset]:schedule.append((ci,repeat,method,track))
 write(ROOT/'outputs/evaluation/schedule.json',[dict(ordinal=i+1,case_index=ci,repeat=rep,method=meth,track=t)for i,(ci,rep,meth,t)in enumerate(schedule)])
 for ordinal,(ci,rep,meth,track)in enumerate(schedule,1):
  folder=ROOT/'outputs/evaluation/trials'/m['cases'][ci]['case_id']/track/('repeat_%02d'%rep)/meth
  if(folder/'result.json').exists():continue
  if(folder/'started.json').exists():raise RuntimeError('Interrupted trial requires audit: '+str(folder))
  folder.mkdir(parents=True,exist_ok=True)
  command=[sys.executable,'-B','-m','disassembly_recovery.study','worker','--case-index',str(ci),'--repeat',str(rep),'--method',meth,'--track',track]
  start=time.monotonic();proc=subprocess.Popen(command,cwd=WORKSPACE,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
  timeout=False
  try:out,err=proc.communicate(timeout=m['limits']['timeout_seconds']+10)
  except subprocess.TimeoutExpired:timeout=True;os.killpg(proc.pid,signal.SIGKILL);out,err=proc.communicate()
  (folder/'worker.stdout').write_text(out);(folder/'worker.stderr').write_text(err)
  if out.strip():print(out.strip(),flush=True)
  if not(folder/'result.json').exists():
   write(folder/'result.json',dict(case_id=m['cases'][ci]['case_id'],case_path=m['cases'][ci]['case_path'],method=meth,repeat=rep,track=track,success=False,termination='wall_budget_exhausted'if timeout else'worker_error',error=err[-3000:],checker_calls=None,llm_calls=len(list((folder/'llm_calls').glob('call_*'))),trace=[],actions=[],elapsed_seconds_total=time.monotonic()-start))
  write(ROOT/'outputs/evaluation/progress.json',{'completed':ordinal,'expected':len(schedule),'latest':str(folder/'result.json')})
 manifest();write(ROOT/'outputs/evaluation/complete.json',{'trials':len(schedule),'source_verification':'PASS'})

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['actor-freeze','prepare','evaluate','worker']);p.add_argument('--case-index',type=int);p.add_argument('--repeat',type=int);p.add_argument('--method',choices=METHODS);p.add_argument('--track',choices=['normal','seeded']);a=p.parse_args()
 if a.command=='actor-freeze':actor_freeze()
 elif a.command=='prepare':prepare()
 elif a.command=='evaluate':evaluate()
 else:worker(a.case_index,a.repeat,a.method,a.track)

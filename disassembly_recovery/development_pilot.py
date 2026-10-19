"""Development-only model probe using wholly self-designed synthetic geometry."""
import argparse,json
from pathlib import Path
from disassembly_recovery.code_actor import solve_code,CodexCLIProvider
from disassembly_recovery.common import prepare_shared,LIMITS,write
p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--track',choices=['normal','seeded'],required=True)
a=p.parse_args();folder=Path('disassembly_recovery/outputs/development/model_probe')/a.model/a.track
if (folder/'result.json').exists():raise RuntimeError('Already executed')
case=Path('disassembly_backtracking/cases/eval_design_01.json').resolve()
shared=Path('disassembly_recovery/outputs/development/model_probe/shared_'+a.track+'.json')
if not shared.exists():
 state,obs,reg=prepare_shared(case,120,{'part_id':'6','direction':'-x'} if a.track=='seeded' else None)
 write(shared,{'state':state,'observation':obs,'recovery_state':reg})
v=json.loads(shared.read_text());provider=CodexCLIProvider(folder/'llm_calls',model=a.model,reasoning_effort='low',timeout=120)
r=solve_code(case,provider,initial_state=v['state'],initial_observation=v['observation'],recovery_state=v['recovery_state'],**LIMITS)
r.update(model=a.model,track=a.track,development_only=True);write(folder/'result.json',r)
print(json.dumps({k:r.get(k) for k in ('model','track','success','termination','checker_calls','llm_calls','backtracks','elapsed_seconds')}),flush=True)

import argparse
from pathlib import Path
from disassembly_recovery.common import prepare_shared,LIMITS,write
from disassembly_recovery.code_actor import solve_code,load_library,CodexCLIProvider
from disassembly_recovery.hybrid_actor import solve_hybrid
p=argparse.ArgumentParser();p.add_argument('--method',choices=['B','C'],required=True);p.add_argument('--track',choices=['normal','seeded'],required=True);p.add_argument('--revision',default='v0');a=p.parse_args()
folder=Path('disassembly_recovery/outputs/development/library_model_probe')/a.revision/a.method/a.track
if(folder/'result.json').exists():raise RuntimeError('Already done')
case=Path('disassembly_backtracking/cases/eval_design_01.json').resolve();state,obs,reg=prepare_shared(case,120,{'part_id':'6','direction':'-x'}if a.track=='seeded'else None)
provider=CodexCLIProvider(folder/'llm_calls',model='gpt-6-luna',reasoning_effort='low',timeout=120)
args=dict(initial_state=state,initial_observation=obs,recovery_state=reg,**LIMITS)
r=solve_hybrid(case,provider,**args)if a.method=='C'else solve_code(case,provider,library=load_library(),**args)
write(folder/'result.json',r);print({k:r[k]for k in ['success','termination','checker_calls','llm_calls']},flush=True)

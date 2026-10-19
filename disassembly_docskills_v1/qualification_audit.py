"""Read-only numerical audit of input exclusions, separate from actor outcomes."""
from collections import Counter
from pathlib import Path
import numpy as np
from .common import ROOT,read,write,utc

def main():
    records=[]
    for path in sorted((ROOT/'outputs/input_audit/qualification').glob('*/qualification.json')):
        data=read(path);status=data['status_record'];aid=status['id'];folder=path.parent
        row=dict(id=aid,status=status['status'],elapsed_seconds=status['elapsed_seconds'],
            source_inventory_path=str(folder/'source_inventory.json'),actor_outcome=False)
        search_path=folder/'search.json'
        if search_path.exists():
            search=read(search_path);trace=search['trace']
            row.update(reference_checks=search['checks'],reference_seconds=search['elapsed_seconds'],
                reference_best_removed=search['best_removed'],reference_capacity_limit=search['capacity'],
                reference_failure_causes=dict(Counter(t['reason'] for t in trace if not t['valid'])),
                collision_detail_kinds=dict(Counter(d.get('kind','unknown') for t in trace for d in t.get('collision_details',[]))),
                zero_distance_collision_queries=sum(t['reason']=='path_collision' and t.get('collision_distance_m')==0 for t in trace))
            cp=ROOT/'cases/final_01'/('asap_'+aid+'.json')
            if cp.exists():
                case=read(cp);initial=case.get('initial_poses',{});parts=case['parts']
                expected={(p['id'],d) for p in parts if not p.get('fixed') for d in p.get('allowed_directions',['+x','-x','+y','-y','+z','-z'])}
                roots=[t for t in trace if len(t.get('remaining_before',[]))==len(parts)]
                tested={(t['part_id'],t['direction']) for t in roots}
                row.update(root_action_count=len(expected),root_actions_tested=len(tested),
                    all_root_actions_rejected=expected<=tested and not any(t['valid'] for t in roots),
                    max_nominal_to_equilibrated_translation_m=max([float(np.linalg.norm(np.asarray(initial[p['id']]['position'])-p['position'])) for p in parts if p['id'] in initial]+[0.]))
        records.append(row)
    result=dict(created_utc=utc(),stage='final' if (ROOT/'outputs/input_audit/selected_cases.json').exists() else 'in_progress',
        records=records,counts=dict(Counter(r['status'] for r in records)),
        distinction='Input representability/qualification outcomes; not model or planner success/failure.',
        interpretation='All six source-axis root actions rejected is a local checker/action-space result for the selected fixture/setup. It does not prove the source CAD is physically impossible or that official ASAP cannot solve it.',
        no_physics_or_model_runs_in_this_audit=True)
    write(ROOT/'analysis/qualification_audit.json',result)
    print(result['counts'])

if __name__=='__main__':main()

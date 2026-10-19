"""Development-only audit of official ASAP rejection branches and local dynamics.

Official imports are delayed: run `official` with the separate RedMax interpreter.
No source cache is saved. All new evidence is written inside this study.
"""
from __future__ import annotations
import argparse
import copy
import time
from pathlib import Path
import numpy as np
from .common import ROOT, WORKSPACE, read, write, sha

OLD = WORKSPACE/'disassembly_real_v3'
VENDOR = OLD/'vendor/ASAP'

def setup(aid):
    folder = OLD/'outputs/input_audit/qualification'/aid
    certificate = read(folder/'official_ASAP_certificate/certificate.json')
    case_path = OLD/'cases/fresh_01'/f'asap_{aid}.json'
    failed = next(r for r in certificate['steps'] if not r.get('stability_success', False))
    return certificate, case_path, failed

def official(aid):
    from plan_sequence.physics_planner import MultiPartStabilityPlanner, StabilityChecker, CHECK_FREQ
    certificate, cp, step = setup(aid)
    pose = np.asarray(certificate['pose_source_units'])
    source = OLD/'data/source/asap_training'/aid
    start = time.monotonic()
    planner = MultiPartStabilityPlanner(str(VENDOR/'assets'), str(source),
        step['fixed_parts'], step['dynamic_parts'], pose=pose, save_sdf=False)
    planner.sim.reset()
    checker = StabilityChecker(False)
    checker.update_sim(planner.sim, step['dynamic_parts'], step['fixed_parts'])
    disconnected = checker.check_disconnected_parts()
    initial = {p:checker.get_part_pos(p).copy() for p in step['dynamic_parts']}
    result = dict(case_id=f'asap_{aid}', step=step['step'], removed=step['part_id'],
        nominal_setup=True, official_commit='3727e716b57e0b508c4e9ecd9fefa6953e8f72da',
        cache_writes=False, source_units_to_m=certificate['normalization_scale'],
        initial_edges=list(checker.G.edges()), disconnected_at_reset=disconnected,
        ground_is_contact_graph_node=False, completed_steps=0,
        rejection_branch='initial_disconnected' if disconnected else None,
        reported_parts=disconnected, records=[])
    if not disconnected:
        for i in range(1000):
            planner.sim.forward(1, verbose=False); checker.update_status()
            if (i+1)%CHECK_FREQ:
                continue
            distances={p:float(np.linalg.norm(checker.get_part_pos(p)-initial[p])) for p in initial}
            lost=[list(edge) for edge in checker.G.edges()
                  if not planner.sim.body_in_contact('part'+edge[0], 'part'+edge[1], checker.contact_eps)]
            fallen=checker.check_fallen_parts()
            result['records'].append(dict(step=i+1, displacement_m={p:d*certificate['normalization_scale'] for p,d in distances.items()}, lost_initial_contacts=lost, reported_parts=fallen))
            result['completed_steps']=i+1
            if fallen:
                result['rejection_branch']='displacement_and_or_lost_contact'
                result['reported_parts']=fallen
                break
            if time.monotonic()-start>90:
                result['rejection_branch']='diagnostic_timeout'; break
    result['elapsed_seconds']=time.monotonic()-start
    write(ROOT/'outputs/development/physics'/f'{aid}_official.json', result)
    print({k:v for k,v in result.items() if k!='records'}, flush=True)

def local(aid):
    from disassembly_real_v3.simulator import FullDisassemblySim
    certificate, cp, step=setup(aid)
    sim=FullDisassemblySim(cp, max_checks=12)
    records=[]
    for row in certificate['steps'][:step['step']]:
        records.append(sim.remove(row['part_id'], row['direction']))
    nominal={p['id']:dict(position=p['position'],quaternion=p.get('quaternion',[1,0,0,0]),velocity=[0.]*6) for p in sim.case['parts']}
    nominal_result,_=sim.settle(sim.remaining, nominal)
    settled_result,_=sim.settle(sim.remaining, sim.poses)
    result=dict(case_id=f'asap_{aid}',case_sha256=sha(cp),same_fixture_ids=certificate['fixture_ids'],
        operations=records, nominal_remainder=nominal_result,
        from_current_equilibrated_remainder=settled_result,
        comparison='ASAP nominal configuration/contact graph vs bounded MuJoCo displacement/rotation/speed/penetration. No equality assertion.',
        diagnostic_operations=len(records)+2)
    write(ROOT/'outputs/development/physics'/f'{aid}_local.json',result)
    print(dict(case=aid,nominal_stable=nominal_result['stable'],settled_stable=settled_result['stable'],removal_results=[r['reason'] for r in records]),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['official','local']);p.add_argument('aid',choices=['00749','00804']);a=p.parse_args()
    (official if a.mode=='official' else local)(a.aid)

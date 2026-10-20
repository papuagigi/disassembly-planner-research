"""DIAGNOSTIC ONLY: is the six-label straight motion set the binding constraint?

At fixed development states, under the adopted P2 physics, every probed part is
checked (non-committing `check`) along three direction families:
  axes6   the six evaluated labels (source-assembly axes)
  diag20  the 20 edge/corner diagonals of the source frame
  local6  the six source axes rotated by the part's own settling rotation
          (R(q_now) R(q_cad)^T), i.e. the part's CAD axes after it tilted
The extra labels exist only inside this process; planners never see them.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import copy
import itertools
import multiprocessing as mp

import numpy as np
from scipy.spatial.transform import Rotation

from ..common import ROOT, read, utc, write, v6_trial

_SIM = None
AXES = {'+x': (1, 0, 0), '-x': (-1, 0, 0), '+y': (0, 1, 0), '-y': (0, -1, 0), '+z': (0, 0, 1), '-z': (0, 0, -1)}


def _rot(q):
    return Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_matrix()


def labels_for(case, state, parts):
    setup = np.asarray(case['whole_assembly_rigid_transform'])[:3, :3]
    cad = {p['id']: p for p in case['parts']}
    out = {}
    for v in itertools.product((-1, 0, 1), repeat=3):
        if sum(map(abs, v)) >= 2:
            out['diag_%+d%+d%+d' % v] = list(np.asarray(v, float) / np.linalg.norm(v))
    for pid in parts:
        delta = _rot(state['poses'][pid]['quaternion']) @ _rot(cad[pid]['quaternion']).T
        for name, e in AXES.items():
            world = delta @ setup @ np.asarray(e, float)
            out['local_%s_%s' % (pid, name)] = list(setup.T @ world)  # sim re-applies setup rotation
    return out


def _init(case_path, labels):
    global _SIM
    from ..physics_variants import apply
    apply('P2_persist_up_to_stable_penetration')
    from disassembly_real_v3 import simulator as s3
    for k, v in labels.items():
        s3.DIRECTIONS[k] = v
    _SIM = s3.FullDisassemblySim(case_path, max_checks=10**9, capture=False)


def _check(state, pid, label):
    _SIM.restore_state(dict(remaining=state['remaining'], poses=state['poses'], checks=0, trace=[], actions=[]))
    r = _SIM.check(pid, label)
    return dict(part_id=pid, label=label, valid=bool(r['valid']), reason=r['reason'], blockers=r.get('blockers', []),
                collision_distance_m=r.get('collision_distance_m'))


def probe(name, case_path, state, parts, workers):
    case = read(case_path)
    labels = labels_for(case, state, parts)
    jobs = []
    for pid in parts:
        jobs += [(pid, k) for k in AXES]
        jobs += [(pid, k) for k in labels if k.startswith('diag_')]
        jobs += [(pid, k) for k in labels if k.startswith('local_%s_' % pid)]
    with cf.ProcessPoolExecutor(workers, mp_context=mp.get_context('spawn'), initializer=_init, initargs=(case_path, labels)) as pool:
        rows = list(pool.map(_check, [state] * len(jobs), [j[0] for j in jobs], [j[1] for j in jobs]))
    fam = lambda k: 'axes6' if k in AXES else ('diag20' if k.startswith('diag_') else 'local6')
    summary = {}
    for pid in parts:
        mine = [r for r in rows if r['part_id'] == pid]
        summary[pid] = {f: dict(valid=[r['label'] for r in mine if fam(r['label']) == f and r['valid']],
                                max_collision_distance_mm=round(1000 * max([r['collision_distance_m'] or 0 for r in mine if fam(r['label']) == f] + [0]), 2))
                        for f in ('axes6', 'diag20', 'local6')}
    tilt = {pid: float(np.degrees(Rotation.from_matrix(_rot(state['poses'][pid]['quaternion']) @ _rot({p['id']: p for p in case['parts']}[pid]['quaternion']).T).magnitude()))
            for pid in parts}
    return dict(name=name, physics='P2_persist_up_to_stable_penetration', parts=parts, tilt_deg_since_cad=tilt,
                summary=summary, rows=rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--workers', type=int, default=4)
    a = p.parse_args()
    results = []
    for cid in ('asap_05954', 'asap_03114'):
        case_path = read(v6_trial(cid, 'A'))['case_path']
        shared = read(ROOT.parent / 'disassembly_final_v6/outputs/input_audit/evaluation' / cid.split('_')[1] / 'shared.json')
        audit = {c['case_id']: c for c in read(ROOT / 'analysis/physics/initial_lock_audit.json')['cases']}[cid]
        parts = [r['part_id'] for r in audit['evaluated']['rows'] if r['blockers_at_sample0']]
        results.append(probe(cid + '_initial_locked_parts', case_path, shared['state'], parts, a.workers))
        print(results[-1]['name'], {k: {f: len(v['valid']) for f, v in s.items()} for k, s in results[-1]['summary'].items()}, flush=True)
    last = ROOT / 'analysis/physics/06444_last_part_probe.json'
    if last.exists():
        from disassembly_real_v3.simulator import FullDisassemblySim
        cid = 'asap_06444'
        case_path = read(v6_trial(cid, 'A'))['case_path']
        shared = read(ROOT.parent / 'disassembly_final_v6/outputs/input_audit/evaluation/06444/shared.json')
        sim = FullDisassemblySim(case_path, max_checks=10**6, state=shared['state'])
        for pid, d in read(last)['path']:
            assert sim.remove(pid, d)['valid']
        state = dict(remaining=list(sim.remaining), poses=copy.deepcopy(sim.poses))
        results.append(probe(cid + '_end_state_part18', case_path, state, ['18'], a.workers))
        print(results[-1]['name'], results[-1]['summary'], flush=True)
    write(ROOT / 'analysis/physics/motion_probe.json', dict(utc=utc(), method=__doc__.strip(), results=results))


if __name__ == '__main__':
    main()

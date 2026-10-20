"""Initial-interference lock audit with the unchanged evaluation collision checker.

Question: which parts are rejected at path sample 0 (before any motion)?
At sample 0 the moving part is at its current pose, so that test is the same
for all six labels: a part locked there cannot leave in ANY allowed direction
while the reported blocker remains. The audit compares two poses with the
identical checker and tolerances:
  * evaluated: case['initial_poses'] (MuJoCo convex-hull settling, as evaluated)
  * cad_posed: parts[].position/quaternion before that settling
No planner, model call, reference order or tolerance change is involved.
"""
from __future__ import annotations
import argparse
import copy
import time
from pathlib import Path

from .common import ROOT, utc, write, read


def _sim(case_path):
    from disassembly_real_v3.simulator import FullDisassemblySim
    return FullDisassemblySim(case_path, max_checks=10**6, capture=False)


def lock_report(sim, poses, label):
    from disassembly_real_v3.source_collision import SourceMeshCollisionChecker
    checker = SourceMeshCollisionChecker(sim)
    remaining = list(sim.remaining)
    rows = []
    started = time.monotonic()
    for pid in remaining:
        if sim.parts[pid].get('fixed', False):
            continue
        checker.begin_path(pid, remaining, poses)
        result = checker.check_pose({**poses[pid], 'position': list(poses[pid]['position'])})
        material = [d for d in result['details'] if d.get('kind') == 'source_material_sample']
        rows.append(dict(part_id=pid, blockers_at_sample0=result['blockers'],
                         worst_signed_depth_m=max([d['signed_depth_m'] for d in material] + [0.]),
                         detail_kinds=sorted({d['kind'] for d in result['details']})))
    fixed = [p for p in remaining if sim.parts[p].get('fixed', False)]
    locked = {r['part_id']: r['blockers_at_sample0'] for r in rows if r['blockers_at_sample0']}
    # A lock with the permanent fixture, or a mutual lock, cannot be removed by any
    # removal order while poses are unchanged. Residual settling after another
    # removal can move poses, so this is a certificate only for unchanged poses.
    fixture_locked = sorted(p for p, b in locked.items() if set(b) & set(fixed))
    mutual = sorted({tuple(sorted((p, q))) for p, b in locked.items() for q in b
                     if q in locked and p in locked.get(q, [])})
    floor_locked = sorted(p for p, b in locked.items() if '__floor__' in b)
    return dict(label=label, fixed=fixed, movable=len(rows), locked_parts=len(locked),
                fixture_locked_parts=fixture_locked, mutual_locked_pairs=[list(m) for m in mutual],
                floor_locked_parts=floor_locked, rows=rows,
                unchanged_pose_full_disassembly_blocked=bool(fixture_locked or mutual),
                seconds=time.monotonic() - started)


def audit_case(case_path):
    sim = _sim(case_path)
    evaluated = copy.deepcopy(sim.poses)
    cad = {p['id']: {'position': p['position'], 'quaternion': p.get('quaternion', [1, 0, 0, 0]),
                     'velocity': [0.] * 6} for p in sim.case['parts']}
    out = dict(case_id=sim.case['id'], case_path=str(case_path), utc=utc(),
               physics={k: sim.physics.get(k) for k in ('penetration_tolerance_m', 'resting_contact_slack_m',
                                                       'stable_penetration_m', 'path_step_m', 'path_mode',
                                                       'extraction_collision')},
               evaluated=lock_report(sim, evaluated, 'evaluated_initial_poses_after_mujoco_settling'),
               cad_posed=lock_report(sim, cad, 'cad_pose_before_settling'))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('cases', nargs='+')
    p.add_argument('--out', default=str(ROOT / 'analysis/physics/initial_lock_audit.json'))
    a = p.parse_args()
    rows = []
    for c in a.cases:
        r = audit_case(Path(c).resolve())
        rows.append(r)
        e, d = r['evaluated'], r['cad_posed']
        print(r['case_id'], 'evaluated locked', e['locked_parts'], 'fixture', e['fixture_locked_parts'],
              'mutual', len(e['mutual_locked_pairs']), '| cad locked', d['locked_parts'], 'fixture',
              d['fixture_locked_parts'], 'mutual', len(d['mutual_locked_pairs']), flush=True)
    previous = read(a.out)['cases'] if Path(a.out).exists() else []
    keep = [r for r in previous if r['case_id'] not in {x['case_id'] for x in rows}]
    write(a.out, dict(utc=utc(), method=__doc__.strip(), cases=keep + rows))


if __name__ == '__main__':
    main()

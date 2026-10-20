"""Pre-specified P2 adoption checks (analysis/PHYSICS_DECISION.md). Development CADs only.

1. Monotonicity: recorded P0-accepted removal sequences replay under P2 with
   identical validity and child state keys.
2. Plausibility of P2-only acceptances: at the 03114 / 05954 initial states,
   every part that P0 locks at sample 0 is checked in all six labels under P2
   with instrumentation; for every sample whose initial depth exceeds the 0.2 mm
   tolerance we record max initial depth and max growth over the path.
"""
from __future__ import annotations
import copy

import numpy as np

from ..common import ROOT, read, utc, write, v6_trial

LOG = []


def instrument():
    from .. import physics_variants
    physics_variants.apply('P2_persist_up_to_stable_penetration')
    from disassembly_real_v3 import source_collision as sc
    original = sc.SourceMeshCollisionChecker._material_check

    def logged(self, owner, outside, triangle_ids):
        result = original(self, owner, outside, triangle_ids)
        ids, blocks = self._triangle_samples(owner, triangle_ids)
        if sum(len(b) for b in blocks):
            points = np.concatenate(blocks)
            values = sc.signed_material_distance(self.meshes[outside], self._other_local(points, owner, outside, self.poses))
            initial = np.concatenate([self.initial_depth_samples[(owner, outside, t)] for t in ids])
            deep = initial > self.physics['penetration_tolerance_m'] + sc.SURFACE_EPSILON_M
            if deep.any():
                LOG.append(dict(moving=self.moving, owner=owner, outside=outside,
                                max_initial_m=float(initial[deep].max()),
                                max_growth_m=float((values[deep] - initial[deep]).max()),
                                rejected=bool(result[0])))
        return result
    sc.SourceMeshCollisionChecker._material_check = logged


def monotonicity():
    from disassembly_real_v3.simulator import FullDisassemblySim
    from disassembly_recovery.shared_api import physical_state_key
    rows = []
    for case, arm in [('asap_06444', 'A'), ('asap_05954', 'B'), ('asap_05954', 'A')]:
        r = read(v6_trial(case, arm))
        shared = read(ROOT.parent / 'disassembly_final_v6/outputs/input_audit/evaluation' / case.split('_')[1] / 'shared.json')
        sim = FullDisassemblySim(r['case_path'], max_checks=10**6, state=shared['state'])
        accepted = [t for t in r['trace'] if t.get('committed')]
        ok = True
        for t in accepted:
            if physical_state_key(sim.export_state()) != t['physical_state_key_before']:
                break  # later commits follow restores; check the forward prefix only
            res = sim.remove(t['part_id'], t['direction'])
            same = res['valid'] and physical_state_key(sim.export_state()) == t['physical_state_key_after']
            ok &= same
            rows.append(dict(case=case, arm=arm, action=[t['part_id'], t['direction']], p2_valid=res['valid'], same_child_key=same))
        rows.append(dict(case=case, arm=arm, prefix_ok=ok))
    return rows


def locked_parts_under_p2(case_id):
    from disassembly_real_v3.simulator import FullDisassemblySim
    audit = {c['case_id']: c for c in read(ROOT / 'analysis/physics/initial_lock_audit.json')['cases']}[case_id]
    locked = [r['part_id'] for r in audit['evaluated']['rows'] if r['blockers_at_sample0']]
    case_path = read(v6_trial(case_id, 'A'))['case_path']
    sim = FullDisassemblySim(case_path, max_checks=10**6)
    start = sim.export_state()
    out = []
    for pid in locked:
        for d in ('+x', '-x', '+y', '-y', '+z', '-z'):
            sim.restore_state(copy.deepcopy(start))
            n = len(LOG)
            r = sim.check(pid, d)
            seen = LOG[n:]
            out.append(dict(part_id=pid, direction=d, p2_valid=r['valid'], reason=r['reason'], blockers=r['blockers'],
                            collision_distance_m=r.get('collision_distance_m'),
                            max_initial_deep_m=max([x['max_initial_m'] for x in seen] + [0.]),
                            max_growth_deep_m=max([x['max_growth_m'] for x in seen] + [-1.])))
    return out


def main():
    instrument()
    mono = monotonicity()
    probes = {c: locked_parts_under_p2(c) for c in ('asap_05954', 'asap_03114')}
    accepted = [p for rows in probes.values() for p in rows if p['p2_valid']]
    summary = dict(utc=utc(), monotonicity_prefixes_ok=all(r.get('prefix_ok', True) for r in mono),
                   p2_only_accepted_checks=len(accepted),
                   max_initial_deep_depth_m_among_accepted=max([p['max_initial_deep_m'] for p in accepted] + [0.]),
                   max_growth_m_among_accepted=max([p['max_growth_deep_m'] for p in accepted] + [-1.]),
                   slack_m=2e-05, stable_penetration_m=1e-3)
    write(ROOT / 'analysis/physics/p2_adoption_checks.json', dict(summary=summary, monotonicity=mono, locked_part_probes=probes))
    print(summary)


if __name__ == '__main__':
    main()

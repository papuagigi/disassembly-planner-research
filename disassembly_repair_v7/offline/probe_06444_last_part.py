"""06444: rebuild the P0 path to the 19-removal state {1, 18} and test part 18 under P0 and P2."""
import copy, json
from disassembly_repair_v7.common import ROOT, read, write, utc, v6_trial
from disassembly_real_v3.simulator import FullDisassemblySim

ref = read(ROOT / 'analysis/physics/reference_search/dev_asap_06444_from_v6A_prefix.json')
states = ref['expanded_states']
path = [list(a) for a in ref['seeded_prefix']]
chain = []
for a, b in zip(states, states[1:]):
    if b['removed'] != a['removed'] + 1:
        break
    gone = sorted(set(a['remaining']) - set(b['remaining']))
    assert len(gone) == 1
    d = [x[1] for x in a['accepted'] if x[0] == gone[0]][0]
    chain.append([gone[0], d])
case = read(v6_trial('asap_06444', 'A'))['case_path']
shared = read(ROOT.parent / 'disassembly_final_v6/outputs/input_audit/evaluation/06444/shared.json')
out = {}
for variant in (None, 'P2_persist_up_to_stable_penetration'):
    if variant:
        from disassembly_repair_v7.physics_variants import apply
        apply(variant)
    sim = FullDisassemblySim(case, max_checks=10**6, state=shared['state'])
    for pid, d in path + chain:
        assert sim.remove(pid, d)['valid'], (variant, pid, d)
    end = sim.export_state()
    rows = []
    for d in ('+x', '-x', '+y', '-y', '+z', '-z'):
        sim.restore_state(copy.deepcopy(end))
        r = sim.check('18', d)
        det = (r.get('collision_details') or [{}])[0]
        rows.append(dict(direction=d, valid=r['valid'], reason=r['reason'], blockers=r['blockers'],
                         collision_distance_m=r.get('collision_distance_m'), detail=det))
    out[variant or 'P0'] = dict(remaining=sorted(end['remaining']), part18=rows)
    print(variant or 'P0', sorted(end['remaining']), [(x['direction'], x['valid'], x['reason'], x['collision_distance_m']) for x in rows])
write(ROOT / 'analysis/physics/06444_last_part_probe.json', dict(utc=utc(), path=path + chain, results=out))

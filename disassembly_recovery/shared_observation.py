"""One public geometric observation for all arms; no future-state physics oracle."""
import copy
from .shared_api import physical_state_key


def enrich_snapshot(sim):
    obs = sim.snapshot()
    state = sim.export_state()
    key = physical_state_key(state)
    cached = getattr(sim, '_recovery_contact_cache', None)
    if cached is None or cached[0] != key:
        model, data, body_ids, geom_ids = sim._build()
        pairs = {}
        for contact in data.contact:
            a, b = geom_ids.get(int(contact.geom1)), geom_ids.get(int(contact.geom2))
            if a is None or b is None or a == b or float(contact.dist) > .0005:
                continue
            normal_z = float(contact.frame[2])
            if abs(normal_z) < .7:
                continue
            supporter, supported = (a, b) if normal_z > 0 else (b, a)
            pair = (supporter, supported)
            entry = pairs.setdefault(pair, {'supporter':supporter,'supported':supported,
                                            'contact_count':0,'normal_z_abs':abs(normal_z)})
            entry['contact_count'] += 1
            entry['normal_z_abs'] = max(entry['normal_z_abs'], abs(normal_z))
        edges = [pairs[pair] for pair in sorted(pairs)]
        sim._recovery_contact_cache = (key, edges)
    else:
        edges = cached[1]
    obs['state_key'] = key
    obs['support_edges'] = copy.deepcopy(edges)
    obs['support_semantics'] = ('Current vertical contact normal relations from MuJoCo mj_forward, '
        'not force/load measurements or proof of future stability. No hypothetical action was tested. '
        'A supporter may be required to keep a different part stable after target removal.')
    current = [copy.deepcopy(t) for t in sim.trace if t.get('physical_state_key_before') == key]
    graph_edges, rejects = [], []
    for t in current:
        t.pop('elapsed_seconds', None)
        if not t.get('valid'):
            rejects.append({k:t.get(k) for k in ('part_id','direction','reason')})
            if t.get('reason') == 'path_collision':
                for blocker in t.get('blockers', []):
                    graph_edges.append({'from':blocker,'to':t['part_id'],'direction':t['direction']})
    obs['directed_blocking_graph'] = {'state_key':key,'edges':graph_edges,'rejected_actions':rejects,
        'semantics':'Hard exclusion applies only to tested action at this exact physical state. Unknowns stay eligible.'}
    obs['current_state_feedback'] = current
    # Prior feedback is available as experience but is never a hard current-state exclusion.
    obs['history_feedback'] = [{k:t.get(k) for k in ('operation','part_id','direction','valid','reason',
        'blockers','committed','physical_state_key_before','physical_state_key_after','remaining_before','remaining_after')}
        for t in sim.trace]
    return obs

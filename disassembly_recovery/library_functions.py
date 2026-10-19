"""Executable recovery skills, developed on the previous three failed cases only.
No case ID, part role, reference order, or test certificate is used.
"""

def support_profile(observation):
    target = observation['target_id']
    edges = observation.get('support_edges', [])
    loads = [e['supported'] for e in edges if e['supporter'] == target]
    alternatives = []
    sole_loads = []
    for load in loads:
        others = [e['supporter'] for e in edges if e['supported'] == load and e['supporter'] != target]
        alternatives.extend(others)
        if not others:
            sole_loads.append(load)
    return {'loads':loads,'alternatives':alternatives,'sole_loads':sole_loads}


def recovery_hint(observation, checkpoints):
    profile = support_profile(observation)
    if not profile['sole_loads']:
        return ''
    current = set(p['id'] for p in observation['remaining_parts'])
    # Soft early branch abandonment, not a proof that every continuation fails.
    for checkpoint in checkpoints:
        previous = set(checkpoint['remaining_parts'])
        if current < previous:
            return checkpoint['handle']
    return ''


def rank_candidates(observation, candidates, history, model_order):
    target = observation['target_id']
    parts = {p['id']:p for p in observation['remaining_parts']}
    profile = support_profile(observation)
    protected = set(profile['alternatives'])
    loads = set(profile['loads'])
    records = history + observation.get('history_feedback', [])
    goal_directions = []
    roots = []
    # Past collision evidence supplies a soft relevance hint only. All exact
    # state exclusions remain the controller's responsibility.
    for direction in ['+x','-x','+y','-y','+z','-z']:
        relevant = [r for r in records if r.get('part_id') == target and r.get('direction') == direction
                    and r.get('reason') == 'path_collision']
        if relevant:
            blockers = relevant[0].get('blockers', [])
            live = [p for p in blockers if p in parts]
            forbidden = any(parts[p].get('fixed') or p in protected or p in loads for p in live)
            if not forbidden:
                goal_directions.append(direction)
                roots.extend(live)
    needed = set(roots)
    # Follow upward support contacts: upper blockers often have to be removed
    # before the lower obstacle can move. This is ordering, never hard pruning.
    for iteration in range(len(parts)):
        for edge in observation.get('support_edges', []):
            if edge['supporter'] in needed and edge['supported'] in parts:
                needed.add(edge['supported'])
        for record in records:
            if record.get('part_id') in needed and record.get('reason') == 'path_collision':
                for blocker in record.get('blockers', []):
                    if blocker in parts and not parts[blocker].get('fixed') and blocker not in protected and blocker not in loads:
                        needed.add(blocker)
    selected = []
    for action in model_order:
        key = (action['part_id'],action['direction'])
        if key not in selected:
            selected.append(key)
    ranked = []
    for action in candidates:
        pid, direction = action['part_id'],action['direction']
        part = parts[pid]
        category = 0 if pid == target else 1 if pid in needed else 4 if pid in loads else 5 if pid in protected else 3
        # Prefer vertically exposed dependency obstacles; model resolves ties.
        height = -part['bounds'][1][2] if pid in needed else 0
        preferred = goal_directions if pid == target else ['+z','+x','-x','+y','-y','-z']
        direction_rank = preferred.index(direction) if direction in preferred else 6
        key = (pid,direction)
        model_rank = selected.index(key) if key in selected else len(selected)
        ranked.append((category,height,direction_rank,model_rank,pid,direction,action))
    ranked.sort(key=lambda item:item[:6])
    return [item[6] for item in ranked]


def recover_target(api):
    """Shared-budget DFS with goal-support preservation and exact-state memory."""
    observation = api.snapshot()
    hint = recovery_hint(observation, api.checkpoints())
    if hint:
        observation = api.restore(hint)
    history = list(observation.get('history_feedback', []))
    visited = set()
    exhausted = set()
    stack = []
    node = {'handle':api.checkpoint(),'key':observation['state_key'],'tried':set()}
    stack.append(node)
    visited.add(node['key'])
    while stack and observation['remaining_checks'] > 0:
        observation = api.snapshot()
        ids = [p['id'] for p in observation['remaining_parts']]
        if observation['target_id'] not in ids:
            return True
        node = stack[-1]
        blocked = set((r['part_id'],r['direction']) for r in observation.get('current_state_feedback', []) if not r.get('valid'))
        candidates = []
        for part in observation['remaining_parts']:
            if not part.get('fixed'):
                for direction in part['allowed_directions']:
                    pair = (part['id'],direction)
                    if pair not in blocked and pair not in node['tried']:
                        candidates.append({'part_id':part['id'],'direction':direction})
        candidates = rank_candidates(observation,candidates,history,[])
        if not candidates:
            exhausted.add(node['key'])
            stack.pop()
            if not stack:
                return False
            observation = api.restore(stack[-1]['handle'])
            continue
        action = candidates[0]
        node['tried'].add((action['part_id'],action['direction']))
        result = api.remove(action['part_id'],action['direction'])
        history.append(result)
        if result.get('committed'):
            observation = api.snapshot()
            hint = recovery_hint(observation,[c for c in api.checkpoints() if c['handle'] == node['handle']])
            if hint or observation['state_key'] in visited:
                observation = api.restore(node['handle'])
            else:
                visited.add(observation['state_key'])
                stack.append({'handle':api.checkpoint(),'key':observation['state_key'],'tried':set()})
    return False

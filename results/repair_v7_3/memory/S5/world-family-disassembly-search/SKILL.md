---
name: "world-family-disassembly-search"
description: "A state-aware search procedure that discovers useful world-direction families, avoids repeated failures, and backtracks from known dead ends."
---
## Triggers

Use for full disassembly of an unfamiliar assembly. At the start of each episode, inspect `direction_vectors_world` and classify the six labels by their world vectors: up has positive world z, down has negative world z, and lateral has near-zero world z. Never infer geometry from a label name.

If a loaded exact-assembly document has an ID starting with `assembly-note-`, use its Recorded sequence first, checking each listed step in order. Switch to this general procedure only when a listed step is rejected or the sequence ends. For other same-assembly notes, use only cross-assembly patterns; do not reuse their part IDs or sequences.

## Procedure

1. Read available physical procedure documents before the first action. Inspect the snapshot, available nonfixed parts, each part's `allowed_directions`, the exact `state_key`, `search_ledger`, and saved checkpoints.
2. If an exact-assembly Recorded sequence is loaded, check its next action at each matching state first. A rejected step ends sequence replay; continue with the general search.
3. Discover the working world family through a small, diverse probe of available actions. Do not begin with down-family actions: across 3,611 recorded queries, down had zero acceptances in 546 tries. Compare up and lateral using current available actions and state feedback; the aggregate acceptance rates do not establish which family will work on this assembly.
4. After the first accepted stable removal, make its world family the leading family for other parts. In the development records, 73.3% of later acceptances were in the first accepted family, and after a committed removal the same direction label on a different part had a 41.2% acceptance rate versus 9.1% for other labels. Recompute labels' world families from the current observation; labels themselves are names.
5. Prefer `remove` for a candidate when ready to commit: it validates the swept path and remainder stability and commits only a valid stable action in one charged check. Do not `check` and then `remove` for the same candidate, because that costs two checks. If a candidate fails, use its feedback; a path collision may have no stability result, so read nested stability only through `feedback.get('stability') or {}`.
6. Track attempts per exact `state_key`, part, and direction. Never issue a direction already rejected at that state; the rejection cache makes it free but cannot change the deterministic result. After three or more rejections for a part at the same state, defer that part while other candidates remain. Retry it after a state change, since a rejection applies only to its exact state. Do not immediately query a named blocker as the next move; such queries accepted in 7.2% of 1,311 tries.
7. When no preferred-family candidate succeeds, try untested up or lateral actions, prioritizing parts with fewer rejections at this exact state. Do not sweep every direction of one part while other candidates remain. Every accepted move creates a new state: refresh the snapshot and ledger, then rank again using the latest accepted family.
8. Use the search ledger to select among states. Do not re-enter a state marked `known_dead_end`; deterministic physics means its explored actions cannot lead to completion. Restore a resumable checkpoint with untested actions when the current state is exhausted. Restoration does not refund checks, time, or model calls.
9. Continue until `remaining_part_count <= 1`, not until the compatibility `target_id` is removed. Respect cumulative ceilings of 240 charged checks, 900 seconds, and 8 model calls. Account for runtime: unstable-remainder checks had a 19.61 s median, versus 2.12 s for path collisions, so avoid broad low-yield probing that could reach stability simulation.

## CODE application

Keep the exact-assembly Recorded sequence first in the program when available. Then use an iterative search over snapshot candidates. Derive family from world z components; maintain the latest successful world family and action label. Use `search_ledger` and `state_key` to avoid repeated rejections, defer parts with at least three current-state rejections, and skip known-dead-end states. After committing a move, refresh all state-dependent data. Save checkpoints when useful and restore only resumable checkpoints. Avoid loops that keep issuing cached rejections; the runtime may stop a turn after excessive repeated cached answers. The Reference implementation below is a compact template for general search; add an exact-assembly sequence before its generic loop when one is supplied.

## Reference implementation

```python
def run(api):
    latest_label = ''
    latest_family = ''
    initial = api.snapshot()
    vectors = initial.get('direction_vectors_world', {})
    labels = list(vectors.keys())
    family = {}
    for label in labels:
        vec = vectors[label]
        z = vec[2]
        if z > 0.5:
            family[label] = 'up'
        elif z < -0.5:
            family[label] = 'down'
        else:
            family[label] = 'lateral'
    seen_states = set()
    while True:
        snap = api.snapshot()
        if snap.get('remaining_part_count', len(snap.get('remaining_parts', []))) <= 1:
            return
        state = snap.get('state_key', '')
        if state in seen_states:
            return
        seen_states.add(state)
        ledger = snap.get('search_ledger') or {}
        current = ledger.get('current') or {}
        if current.get('known_dead_end'):
            choices = api.checkpoints()
            restored = False
            for cp in reversed(choices):
                key = cp.get('state_key', '')
                row = None
                for state_row in ledger.get('states', []):
                    if state_row.get('state_key') == key:
                        row = state_row
                if row and not row.get('known_dead_end') and row.get('untested_action_count', 0) > 0:
                    api.restore(cp.get('handle'))
                    restored = True
                    break
            if not restored:
                return
            continue
        rows = ledger.get('states', [])
        rejected = set()
        accepted_dead = set()
        for row in rows:
            if row.get('state_key') == state:
                for edge in row.get('accepted_edges', []):
                    if edge.get('child_known_dead_end'):
                        accepted_dead.add((edge.get('part_id'), edge.get('direction')))
        parts = snap.get('remaining_parts', [])
        actions = []
        for part in parts:
            pid = part.get('id', '')
            if part.get('fixed'):
                continue
            for direction in part.get('allowed_directions', []):
                if (pid, direction) in accepted_dead:
                    continue
                actions.append((pid, direction, family.get(direction, 'lateral')))
        feedback = snap.get('current_state_feedback', [])
        rejects_by_part = {}
        for item in feedback:
            if not item.get('valid'):
                pid = item.get('part_id', '')
                direction = item.get('direction', '')
                rejects_by_part[pid] = rejects_by_part.get(pid, 0) + 1
                rejected.add((pid, direction))
        candidates = []
        for action in actions:
            pid = action[0]
            if action[:2] in rejected:
                continue
            candidates.append(action)
        if not candidates:
            choices = api.checkpoints()
            restored = False
            for cp in reversed(choices):
                key = cp.get('state_key', '')
                row = None
                for state_row in rows:
                    if state_row.get('state_key') == key:
                        row = state_row
                if row and key != state and not row.get('known_dead_end') and row.get('untested_action_count', 0) > 0:
                    api.restore(cp.get('handle'))
                    restored = True
                    break
            if not restored:
                return
            continue
        def rank(action):
            pid, direction, fam = action
            if latest_label and direction == latest_label:
                recent = 0
            else:
                recent = 1
            if latest_family and fam == latest_family:
                family_rank = 0
            elif fam == 'up':
                family_rank = 1
            elif fam == 'lateral':
                family_rank = 2
            else:
                family_rank = 3
            count = rejects_by_part.get(pid, 0)
            deferred = 1 if count >= 3 else 0
            return (deferred, recent, family_rank, count, pid, direction)
        candidates = sorted(candidates, key=rank)
        result = None
        for pid, direction, fam in candidates:
            result = api.remove(pid, direction)
            if result.get('valid'):
                latest_label = direction
                latest_family = fam
                break
        if result and result.get('valid'):
            continue
        choices = api.checkpoints()
        restored = False
        fresh = api.snapshot()
        fresh_ledger = fresh.get('search_ledger') or {}
        fresh_rows = fresh_ledger.get('states', [])
        for cp in reversed(choices):
            key = cp.get('state_key', '')
            row = None
            for state_row in fresh_rows:
                if state_row.get('state_key') == key:
                    row = state_row
            if row and key != fresh.get('state_key', '') and not row.get('known_dead_end') and row.get('untested_action_count', 0) > 0:
                api.restore(cp.get('handle'))
                restored = True
                break
        if not restored:
            return

run(api)
```

## GRAPH_DFS application

At each state, rank available actions using world families and the recorded state ledger. Probe up and lateral actions to discover the working family; omit down from early candidates. After an accepted removal, prioritize the latest accepted family and then the same label on other parts. Suppress actions already rejected at that exact state, and push parts with three or more rejections behind less-tried parts. Use ledger dead-end flags and resumable checkpoint handles to guide DFS/backtracking; do not revisit a known dead end. If an exact-assembly Recorded sequence is loaded, rank its next action first until a step is rejected or the sequence ends.

## Evidence

- The development set recorded **3,611 checks across 55 inputs**. World-family acceptance was **0.0% for down (546 tries)**, **14.7% for lateral (2,177 tries)**, and **29.5% for up (888 tries)**.
- The world-family data show assembly variation: one assembly accepted only lateral actions (**36 accepted**), another only up (**3 accepted**), and others accepted both. Across assemblies, **73.3% of later acceptances were in the first accepted family (n=531)**. Therefore, discover the family rather than assume up will work.
- After a committed removal, the same direction label on a different part was accepted **41.2% (828 tries)**, compared with **9.1% (2,088 tries)** for other directions.
- Acceptance after **0, 1, 2, 3, 4, and 5** prior rejections of the same part at the same state was **28.2% (1,189), 10.6% (640), 13.6% (530), 2.8% (427), 7.6% (397), and 15.2% (428)**. Checks spent on parts with at least three such rejections totaled **1,145**. The rates are non-monotonic, so the three-rejection rule is deferral, not permanent exclusion.
- Queries naming the immediately preceding blocker as the next action were accepted **7.2% (1,311 tries)**.
- Median check time was **2.12 s for path collisions (n=2,887)**, **3.76 s for accepted checks (n=582)**, and **19.61 s for unstable remainders (n=142)**.
- The ledger records known dead ends and accepted edges into them; **420 checks** were spent at known dead-end states in the development data. The exact-state rejection cache returns repeated rejections without a charged physics check. Restore does not refund costs.
- Exact-assembly notes reduced the second attempt to minimum checks in **9 of 10 successes** in the supplied summary. This supports replaying a matching note's Recorded sequence first; it does not support copying sequences across assemblies.

## Limits

These are aggregate development observations, not controlled causal estimates or guarantees for an unseen assembly. Family rates combine different assemblies and states; a family with a lower aggregate rate may be the only working family for a particular assembly. Rejections, accepted edges, and dead ends are exact-state facts. Restoring can expose untested branches but consumes wall time and does not refund any budget. The reference program has no loaded-document handling because no assembly-specific IDs or sequences are supplied in its generic form; prepend the exact Recorded sequence when such a note is loaded. Its greedy search/backtracking policy is a template and cannot guarantee completion within the episode budgets.

---
name: "state-first-removal-prioritization"
description: "Orders removal attempts using measured direction and exact-state rejection rates to reduce repeated low-yield checks across both planners."
---
## Triggers

Use when choosing among currently available part-direction actions, especially after a rejected path check or when the search is spending many checks without a committed removal.

## Procedure

1. **Prefer a direction with direct measured support.** If an action repeats the last successful direction for its part, rank it ahead of that part’s other directions. Treat this as a measured prior, not a guarantee.
2. **Prefer upward directions among otherwise comparable untried actions.** Upward actions had higher acceptance than lateral actions; put lateral actions next. Do not spend checks on downward actions while upward or lateral candidates remain untried, unless the planner has stronger current-state evidence for the downward action.
3. **After a rejection, mark only that exact part-direction-state pair as rejected.** Do not immediately try another direction for the same part merely because it is available. First consider other currently available parts, especially those identified as blockers, while recognizing that blocker identity alone is a weak acceptance signal.
4. **Use exact-state history to bound retries.** Once a part has three rejected directions at the same exact state, stop spending checks on further directions for that part at that state. Continue with other parts; reconsider it after a successful state change.
5. **After every committed removal, reassess from the new state.** Recompute available actions and use the new state identity for all history. Prior rejections do not prohibit a fresh check in a changed state.

## CODE application

Order the search frontier by the procedure above. Keep rejection records keyed by exact state, part, and direction; skip a repeated rejected triple, including when the cache is unavailable. At three distinct rejected directions for a part in one state, defer its remaining directions until the state changes. Checkpoint after committed removals and resume from that checkpoint after recovery; use the exact-state ledger and free rejection cache to avoid duplicate work.

```text
while budget remains and goal not reached:
    state = current_exact_state()
    candidates = available_actions(state)
    candidates = remove_exact_rejected_pairs(candidates, state)
    candidates = defer_parts_with_3plus_rejections(candidates, state)
    action = highest_priority(candidates)  # successful-direction reuse, then up, lateral, down
    if no action: restore_or_backtrack_using_ledger(); continue
    result = trusted_check(action)
    record(state, action, result)
    if result accepted and committed: checkpoint_new_state()
```

Keep the loop within the episode’s time and call budgets. Avoid unsupported code constructs: the observed generated-code errors included five whole-episode deadline errors and three other execution errors.

## GRAPH_DFS application

Rank currently available actions in this order: (1) a part’s last successful direction, when available; (2) untried upward actions; (3) untried lateral actions; (4) downward actions. After a rejection, lower that exact part-direction-state pair. If the same part has three rejected directions in the current state, rank its remaining directions below actions on other parts. A blocker named in a collision can receive consideration among other parts, but do not give it an automatic high rank. After a committed removal, rank from the new state and ask for a new ranking when the host DFS is stuck.

## Evidence

The aggregate covers all 1,649 recorded development checks across 21 inputs. Reusing the last successful direction had a 48.9% acceptance rate (274 tries), compared with 7.4% for other directions after a success (797 tries). Acceptance was 32.4% for upward actions (315 tries), 10.3% for lateral actions (1,055 tries), and 0% for downward actions (279 tries). A blocker named in the prior query was followed by acceptance only 4.2% of the time (431 tries).

For a part with prior rejections in the same exact state, acceptance rates by rejection count were 15.4% at zero, 10.4% at one, 13.2% at two, 5.8% at three, and 1.1% at four; the five-rejection estimate was 26.8% from 228 tries and is not a monotonic trend. Checks on parts already at three or more rejections in a state consumed 540 checks. These figures support a practical cutoff after three rejections as a check-saving heuristic, not as a measured optimum.

The supplied episode outcomes show both completed and incomplete episodes under all three conditions; they do not isolate the effect of these ranking rules. Generated programs also recorded five whole-episode deadline errors, plus one augmented-assignment error, one `next` name error, and one missing `accepted_edges` key error.

## Limits

These are development-query associations, not causal estimates or guarantees. The per-rejection-count rates are non-monotonic, and the five-rejection rate is based on a smaller subset. A rejected path can reflect a state-specific obstruction; a successful removal changes the state and requires fresh ranking. The data do not establish that the three-rejection cutoff is optimal, nor do they show that these rules alone guarantee full disassembly.

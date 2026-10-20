---
name: "state-aware-action-budgeting"
description: "Prioritizes measured high-yield removal actions and limits repeated checks that development traces show are unlikely to help."
---
## Triggers

Use at each state when choosing a removal query, especially after a rejection or after a successful removal changes the assembly. Apply only to currently available actions and the exact current state.

## Procedure

1. **Prefer the latest successful direction label.** After a committed removal along label `L`, rank available actions with label `L` first. Treat labels only as labels; use the planner’s action set and trusted checker to establish whether a move works.
2. **Prefer upward actions over lateral actions, and lateral over downward actions.** These are empirical ordering hints, not guarantees. Continue to require trusted path and stability validation.
3. **Do not spend a long sequence of checks on one target in one unchanged state.** After three rejected directions for that target at that exact state, defer it and try a different available target. Resume it only after a committed state change, and reassess using the new state.
4. **On a collision, record the exact state, target, direction, and named blocker if provided.** Lower priority for that target at that state. Do not automatically spend the next check on another direction of the same target: the next query naming a blocker succeeded only 4.2% of the time.
5. **Use exact-state memory for skips.** Skip an exact repeated rejected query if the cache can answer it for free. Do not generalize the rejection to a different state; after a committed removal or restore, reassess actions against that state.
6. **After a rejection, move to another current candidate rather than cycling through directions on a seemingly difficult part.** The data include enclosed examples rejected in several or all directions, while other parts later were accepted. This is a prioritization rule, not proof that a deferred part is impossible.
7. **Keep the query loop simple and within budget.** Reserve checks and model calls for a complete disassembly search; avoid spending the episode on repeated low-yield attempts. Each proposed removal still goes through the trusted path and stability checks.

## CODE application

Generate a candidate order that prioritizes the latest successful direction label, then the measured direction-family order. Maintain rejection counts by `(exact_state, target)` and rejected query results by `(exact_state, target, direction)`. After three rejections for a target in one state, defer it while other candidates remain. A committed removal creates a new state and fresh eligibility; use the exact-repeat cache where available.

```text
while checks remain and parts remain:
    candidates = current_actions()
    order by (latest_success_label, up, lateral, down)
    skip exact rejected repeats if cached
    choose a candidate whose target has fewer than 3 rejects in this state
    if none: defer the most-rejected targets and try another candidate
    validate(candidate)
    record result under exact state
    if committed: update state and latest_success_label
```

Keep the implementation compatible with the supplied API: the development traces recorded three generated-code execution errors (`ValueError` for augmented assignment, `NameError` for `next`, and `KeyError` for `accepted_edges`). Treat these as reasons to keep control flow and API field access minimal and explicit, not as evidence about physical feasibility.

## GRAPH_DFS application

Rank only currently available actions. Give first priority to actions with the label of the most recent committed removal, followed by upward, lateral, then downward actions. Penalize targets with three or more rejections at the exact state and rank other candidates first. A collision naming a blocker is not a reason to rank another direction of that same target immediately above alternatives. Recompute ranks after a committed removal; the host DFS remains responsible for checks, state transitions, and recovery.

## Evidence

- Across **1,649 checks from 21 inputs**, acceptance by direction family was **32.4% for up (315 tried)**, **10.3% for lateral (1,055 tried)**, and **0% for down (279 tried)**.
- After a committed removal, another query using the **same successful direction label on a different part** was accepted **48.9% of the time (274 tried)**; a query using a different label was accepted **7.4% (797 tried)**.
- For a part at one exact state, acceptance conditional on prior rejections was **15.4% at zero prior rejections (435 tries)**, **10.4% after one (357)**, **13.2% after two (242)**, and **5.8% after three (207)**. Checks spent on parts with at least three rejections at a state totaled **540**.
- A query on a blocker named by the immediately preceding query was accepted **4.2% of the time (431 tried)**. The previous advice to try another direction of the same blocked part is therefore not a high-priority default.
- The measured per-condition episodes include successful completions as well as failures under wall-time or call budgets; the statistics do not isolate this procedure’s causal effect. Exact-repeat cache answers are free by the stated planner setup; measured episodes recorded **31 cached rejections in one episode** and zero in the others.
- The supplied code-execution error counts were **one each** for augmented assignment, undefined `next`, and missing `accepted_edges`.

## Limits

These are ordering and stopping heuristics from development query frequencies, not guarantees or causal estimates. The direction-family rates aggregate different assemblies and states; the same-label result applies to other parts after a committed removal, not to retrying the removed part. A rejection count is scoped to an exact state. Reassess after every committed removal or restore, and let the trusted checker decide path collision and remainder stability. Do not infer a fixed removal sequence or permanent impossibility.

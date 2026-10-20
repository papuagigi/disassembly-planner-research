---
name: "defer-persistently-blocked-targets"
description: "Uses exact-state rejection history to shift checks toward other parts when repeated directional attempts on one target have low measured yield."
---
## Triggers

Use after a target has received repeated rejected removal checks in the same exact state, or when choosing among several currently available targets. The procedure applies to either planner and preserves trusted validation as the authority for every removal.

## Procedure

1. **Track failures by exact state and target.** Record the attempted direction and checker result. A committed removal or explicit restore changes the state context; do not count old failures as current-state rejections.
2. **After three rejected directions for one target in one state, defer that target.** Try another currently available target before spending further checks on it. This threshold is a budget heuristic: observed acceptance after three prior rejections was lower than at earlier counts.
3. **Do not make same-target alternative directions the default next query after collision.** Keep untried directions eligible, but first consider other targets. In particular, a query on the named blocker immediately after a collision had very low observed acceptance.
4. **Among candidates, favor actions with the latest successful direction label.** Then use the empirical family order: up, lateral, down. This is a query ordering heuristic; it cannot determine a part’s valid path.
5. **After a successful committed removal, reset the decision using the new exact state.** Recompute candidate availability and blocker information. Previously rejected actions can be reconsidered because the geometry and stability context changed.
6. **Avoid duplicate paid checks.** If the exact `(state, target, direction)` rejection is in the exact-state cache, use the free cached answer rather than issuing another checker call. Preserve the distinction between a cached rejection and a new physical check.
7. **Keep progressing across parts until the goal or episode budget is reached.** Do not terminate merely because one target has no accepted direction among its tested options; other parts may be removable first.

## CODE application

Use an exact-state ledger for rejections and an exact-repeat cache for free answers. Maintain a rejection count per target in the current state. Candidate ordering should favor the latest successful direction label, then up, lateral, down; filter targets with at least three rejections while alternatives exist. On a committed action, load or create the new state’s ledger and recalculate.

```text
for each current state until goal or budget:
    build available actions
    rank by latest_success_label, then up > lateral > down
    omit targets with >= 3 state-local rejections if another target is available
    use cached result for exact repeats; otherwise query trusted checker
    on rejection: record and continue to another target
    on committed acceptance: advance state and recompute
```

Use explicit API fields and simple Python control flow. The measured development records include three code execution errors: one augmented-assignment `ValueError`, one `NameError` for `next`, and one `KeyError` for `accepted_edges`; they support keeping generated control flow and field access straightforward, but do not identify any physical-search improvement.

## GRAPH_DFS application

For every stuck state, rank currently available actions with the latest committed direction label first, then by the observed up/lateral/down ordering. Reduce the rank of a target after its third rejection in that exact state, so DFS can explore other parts. Keep its untested actions in the candidate set at lower rank. When the host returns to a state after progress or restore, rank from that state’s own history and current candidates.

## Evidence

- The full development query set contained **1,649 checks over 21 inputs**.
- Acceptance by number of prior same-target, same-state rejections was **15.4% at 0 (435 tries)**, **10.4% at 1 (357)**, **13.2% at 2 (242)**, **5.8% at 3 (207)**, **1.1% at 4 (180)**, and **26.8% at 5 (228)**. The five-rejection rate is non-monotonic, so the three-rejection threshold is a practical deferral heuristic, not a claim that acceptance always decreases with each retry.
- Checks spent on targets with **3 or more rejections at a state totaled 540**. The anonymized examples include multiple targets rejected in **3 to 6 directions**, with later accepted removals belonging to other parts.
- The named-blocker next-query acceptance rate was **4.2% (431 tries)**.
- After a committed removal, the same successful direction label on a different part had **48.9% acceptance (274 tries)**, compared with **7.4% for other labels (797 tries)**. Direction-family acceptance was **32.4% up (315)**, **10.3% lateral (1,055)**, and **0% down (279)**.
- Episode outcomes were mixed: several episodes reached full disassembly, while others ended with wall-time, call-budget, or no-progress termination. The supplied measurements do not compare these rules in a controlled before-and-after experiment.

## Limits

The statistics describe all supplied development queries, but not an independent evaluation of these procedures. They do not prove that delaying a target causes success, and the non-monotonic five-rejection rate cautions against treating the threshold as a physical law. The same-label statistic is conditional on a prior committed removal and a different target. Direction labels are only planner action labels. Every selected action still requires the trusted swept-path and stability checks.

---
name: "assembly-note-eight-part-z-removal"
description: "First-attempt evidence for this assembly favors replaying the complete +z removal path and provides fallback directions and search cautions."
---
## Triggers

Use this note only when the geometry fingerprint matches this same eight-part assembly (parts `1`–`8`).

## Procedure

1. Start by replaying the host-appended **Recorded sequence** exactly: remove parts `1` through `8`, each along `+z` (world `[0, 0, 1]`). Condition B committed this full path with 8 checks and no recorded rejections.
2. If a step is rejected, keep the already accepted removals and re-check the remaining parts in the resulting state. Condition A shows that after parts `1`, `2`, and `3` were removed along `+z`, part `4` was removable along `+x`; parts `5`, `6`, `7`, and `8` then followed in order using `+z`, `+x`, `+y`, and `+x`.
3. If the replay stops partway, continue from the last accepted state. Try `+z` on the next recorded part first; if rejected, use only evidence-supported alternatives for that part: part `4` has a successful `+x` alternative; part `6` has a successful `+x` alternative after part `5`; part `7` has a successful `+y` alternative after parts `5` and `6`; part `8` has a successful `+x` alternative after part `7`. For parts `1`, `2`, `3`, and `5`, condition A and/or C provide successful `+z` removals, though C's late acceptance shows those checks may be costly.
4. Treat direction labels as fixed world directions. The observed label failures in condition A were `+x` and `+y` for parts `1`, `2`, `3`, and `5`; and `+x` for part `7`. Those failures do not establish that the directions remain invalid after other removals.

## CODE application

Replay the complete recorded sequence in order. If CODE must recover from a rejected action, preserve the committed prefix and try the condition-A alternatives at the corresponding later states: part `4` `+x`, part `6` `+x`, part `7` `+y`, and part `8` `+x`. Avoid sweeping all six directions for a part when the known `+z` path is available.

## GRAPH_DFS application

Seed the search with the recorded ordered path. If a transition fails, backtrack from the current state and retain the committed prefix; prioritize the condition-A alternatives above instead of repeatedly testing directions already rejected in the same state. A six-direction sweep is especially unproductive for parts `5`–`8` at condition C's initial state: all six directions were rejected there, but those parts were later removed after parts `1`–`4` had been cleared.

## Evidence

- Condition B succeeded in 8 checks and 27 seconds: all eight parts were removed in order `1`–`8`, each along `+z`; no rejections were recorded.
- Condition A succeeded in 17 checks and 22 seconds. It recorded initial-state rejections for parts `1`, `2`, `3`, and `5` along `+x` and `+y`, and for part `7` along `+x`. Its successful path used `+z` for parts `1`, `2`, `3`, and `5`; after parts `1`–`3`, part `4` used `+x`; part `6` used `+x`, part `7` used `+y`, and part `8` used `+x`.
- Condition C succeeded, but used 56 checks and 79 seconds. Parts `5`–`8` each rejected all six labels before later being removed along `+z`; part `2` also rejected all six before a later `+z` removal. Part `3` rejected `+x`, `+z`, `-x`, and `-z` before removal along `-x`; part `4` rejected those same four labels before removal along `+x`. Part `1` rejected `+x`, `+y`, `-x`, `-y`, and `-z` before removal along `+z`.
- Labels that failed in condition C, with their world vectors: `+x` `[1,0,0]`, `-x` `[-1,0,0]`, `+y` `[0,1,0]`, `-y` `[0,-1,0]`, `+z` `[0,0,1]`, and `-z` `[0,0,-1]`. Every label failed for at least one part in that condition, so none is globally unusable. In condition A, `+x` and `+y` failed for multiple parts, but both succeeded for other parts. No label is evidenced as universally invalid.
- The broad six-direction checks and repeated rejections in condition C consumed most of the recorded checks and the longest wall time. Condition A and B reached the goal much faster, with B providing the simplest known complete route.

## Limits

These are first-attempt records, not reference solutions. Rejection evidence applies to the recorded part and state only; later removals can change access. The records do not identify why condition C was slower or establish general behavior for unrecorded states. There is no need to infer an untested route because complete successful paths are recorded.

## Recorded sequence

Source: first-attempt condition B, complete success, 8 of 8 required removals, copied verbatim from that episode's final committed path (planner's own record, not a reference solution).

1. part `1` direction `+z` (world [0.0, 0.0, 1.0])
2. part `2` direction `+z` (world [0.0, 0.0, 1.0])
3. part `3` direction `+z` (world [0.0, 0.0, 1.0])
4. part `4` direction `+z` (world [0.0, 0.0, 1.0])
5. part `5` direction `+z` (world [0.0, 0.0, 1.0])
6. part `6` direction `+z` (world [0.0, 0.0, 1.0])
7. part `7` direction `+z` (world [0.0, 0.0, 1.0])
8. part `8` direction `+z` (world [0.0, 0.0, 1.0])

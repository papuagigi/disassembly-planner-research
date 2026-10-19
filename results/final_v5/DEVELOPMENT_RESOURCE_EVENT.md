# Early planned training episode: resource-limited outcome

This is the first of the three user-authorized additional long discovery CADs,not an evaluation episode. Source asap_05459 has17parts and requires16removals. No prior planner result existed when assigned. It passed the initial zero-query capacity screen at884064256bytes and was used once.

Observed result:1/16completed removals,1physical query,2logical model turns,30.2645seconds. The actor peak reached1274150912bytes against the unchanged1073741824byte cap. Recorded LimitError: same1GiBresident-memory ceiling exceeded. This is an operational memory-limit outcome,not evidence that the chosen physical action was infeasible or that the model could not find a path. The recorded removal replay passed;no native solver warnings were recorded. Native warning-free does not imply the episode stayed below its resource cap.

Keep the raw outcome and token cost. Do not silently replace this planned training CAD or rerun it with a larger cap. The main collector reuses the same saved result. There is no collision rejection,instability rejection,or restore in this episode,so it adds no observed repair/backtracking procedure. Proposal and final summaries must distinguish selected/attempted CADs from usable failure-repair evidence. Remaining two new training CADs and all three new validation CADs are selected in the fixed source order by initial input checks,not planner success. Final first-test geometry is still unopened at this checkpoint.

The new learning bank is not yet generated/validated/frozen. No new final A/B/C score is available. Retain old studies separately. No PPT.

# Agent interpretation and observed failure mechanisms

The question is first-episode performance on new products after prior physical experience.No preferred winner is declared.Model weights never update.

|Arm|Unsuccessful episodes|Rejected checks|No-removal episodes|Code errors|Provider errors|
|---|---:|---:|---:|---:|---:|
|A|8|1024|3|6|0|
|B|9|999|3|11|0|
|C|9|592|3|0|0|

## What the logs can establish

- Inspect per-product rows in failure_diagnosis.json and raw call folders before attributing a loss. Provider failure/no completed physical query,generated-code exception,physical rejection,search exhaustion and a cumulative resource cap are distinct mechanisms.
- A library read and declared document_plan establish supplied bytes and model declarations. The trace and observable behavioral proxies are additional evidence. B-A is document availability plus guided-review cost;it cannot isolate one individual document if S2 contains multiple skills. C-B is an architecture bundle. No C-without-memory held-out arm is present.
- A full-disassembly task requires all n-1movable parts. Therefore accepted removals later undone measure wasted branch work;they are not proof that an otherwise nonrequired component was removed. Virtual restoration is not physical reassembly.
- Initial physics validity does not establish a full path under six fixed-orientation straight source-axis actions. A fixed original fixture does not fall under gravity. Every other remaining body is simulated;there is no dynamic gripper/holding/unscrewing/rotation planner. If many directions are physically rejected,the current action/fixture/material model is a candidate limitation,not automatically a weak LLM or a bad skill.
- Case selection is a deterministic source-complexity/input-feasibility sample.No full-path or actor-success selection was used. Wilson intervals in aggregate.csv describe finite binomial uncertainty and do not turn this convenience sample into a representative estimate for all ASAP/factory products.
- The operational test target was amended from15maximum to12fixed CADs for input-preparation cost,before any scored job or test model call. The user required at least10. The source order and first-qualified prefix,model,bank,actor bytes,physics,API and episode caps were unchanged. Read outputs/protocol/evaluation_cohort_amendment.json;do not confuse this source-count amendment with stopping after observing a winner.
- Each CAD/arm has one model episode;the provider exposes no fixed sampling seed here. Resource ceilings match;actual input/output tokens,calls and time can differ. The comparison is ceiling-matched,not equal realized token spending. See cohort_scope.json for development/test size distributions and the possible complexity shift.
- Report development preparation yield,failure-source CAD count,independent admission outcomes and held-out comparison separately. A rejected new document stays rejected even if another condition happens to score better. Token totals include unsuccessful provider calls when usage exists;unknown is not zero.
- This is an ASPIRE-inspired batch update:physical failure traces -> model-written document -> independent repair verification -> append/freeze -> unseen-product evaluation.It does not reproduce ASPIRE evolutionary program search,robot hardware or multimodal execution engine.One batch update is not evidence of indefinite autonomous improvement.Preserving old document bytes does not establish that combined-library behavior has no regressions.

## Evidence files

`input_physics_diagnosis.json` separates setup/engine errors,including observed very-small-mesh MuJoCo compiler failures,from planning outcomes. `development_evidence.json` separates actually observed discovery/validation queries,rejection types,measured repair opportunities and document admission. `matched_conditions_audit.json` verifies matched contracts;`failure_diagnosis.json` retains all observed mechanisms;`trials.csv`/`paired_deltas.csv` locate product-level differences;`memory_context_audit.json` and `behavior_audit.json` separate document presence from behavior. `replay/audit.json` verifies actual MuJoCo events after scoring. No performance result is proof of industrial deployment or reproduction of ASAP numerical results.

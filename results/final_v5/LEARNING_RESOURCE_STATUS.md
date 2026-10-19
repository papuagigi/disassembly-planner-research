# Interim memory-limit impact and continued study

UTC: 2026-10-19T14:02:07.831373+00:00. Not a final comparison.

Existing v4results/source hashes were verified unchanged. Existing S2documents are retained. A/B/C actor,physics,restoration API,model and final caps are unchanged. No final test CAD geometry has opened.

|CAD|Accepted/required|Checks|Native health|Physical replay|Physical rejections|Memory limit|New failure-procedure evidence|
|---|---:|---:|---|---|---:|---|---|
|asap_01613|3/10|30|NOT_YET_AUDITED|PENDING|27|True|False|
|asap_02402|12/12|13|NO_NATIVE_WARNINGS_RECORDED|PASS|1|False|True|
|asap_02406|12/12|27|NO_NATIVE_WARNINGS_RECORDED|PASS|15|False|True|
|asap_02429|12/17|240|NO_NATIVE_WARNINGS_RECORDED|PASS|188|False|True|
|asap_03674|11/11|35|NO_NATIVE_WARNINGS_RECORDED|PASS|24|False|True|
|asap_05459|1/16|1|NO_NATIVE_WARNINGS_RECORDED|PASS|0|True|False|
|asap_07722|4/14|240|NATIVE_ENGINE_WARNINGS_RECORDED|PASS|232|False|False|

05459had one accepted query and no collision/instability rejection or restore. It adds no new failure-repair evidence. It reached1274150912bytes of actor peak RSS after initial884064256byte capacity screening,against1073741824bytes allowed. The actor guard raised LimitError;the OS did not report an OOM kill.

01613has3/10accepted removals and27collision rejections before its memory-limit stop at1119977472bytes. Its feedback can support a procedure only after independent event replay and native health pass. Neither case demonstrates successful backtracking. A later operational stop does not invalidate an independently verified earlier physical-failure prefix.

Case geometry counts:05459has12891convex collision meshes;01613has13032;07385has1793. Code constructs source-mesh BVHs and native MuJoCo models during checks. These are plausible memory contributors;no allocation profile was run,so the exact allocation source or a memory leak is not established. Counts and part count do not alone predict peak RSS.

learning_evidence.eligibility now explicitly separates operational stops,completed physical rejection and replay/native validity before the single future proposal. Accepted-only prefixes are retained in raw accounting but excluded from new failure-procedure evidence. No actor behavior,physics,model,cap or final selection rule was changed. Forty regression tests passed,including five resource-evidence boundary checks. The main supervisor had not imported final_learning/proposed a document when the evidence guard was updated. Already-running helpers only use the unchanged discovery_job/audit_result paths.

Main pipeline PID37806/session80110continues source preparation. Planned remaining-learning helper PID39283/session80815runs01613then07385under the shared discovery_collection.lock. Main collection reuses saved results without rerun. Final stages remain:collect8attempted full-search records→one new proposal→3fresh validation CADs→freeze/admit-or-retain-prior→4new test CADs×ABC→native replays/aggregate/tokens/publication. Validation/final latency episodes run serial after prep drains. Stop after this pass regardless of winner. No PPT.

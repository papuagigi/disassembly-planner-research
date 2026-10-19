"""Agent-readable live counts; plans, inspected sources and admitted memory differ."""
from collections import Counter
from .common import ROOT,read,write,sha,utc

def optional(path,default=None):
    p=ROOT/path
    return read(p) if p.exists() else default

def main():
    pool=read(ROOT/'outputs/input_audit/pools.json')
    selected=optional('outputs/input_audit/selected_development.json',optional('outputs/input_audit/progress_development.json',{}))
    final=optional('outputs/input_audit/selected_evaluation.json',optional('outputs/input_audit/progress_evaluation.json',{}))
    index=optional('outputs/development/collection_index.json',{'cases':[]})['cases']
    discovery=[r for r in index if r['role']=='discovery'];validation=[r for r in index if r['role']=='validation']
    complete=optional('outputs/development/complete.json',{})
    trials=list((ROOT/'outputs/evaluation/trials').glob('*/*/result.json'))
    bound=optional('outputs/evaluation/manifest.json')
    counts=dict(created_utc=utc(),official_archives=dict(training_CADs=1906,test_CADs=240,training_OBJ=14966,test_OBJ=4466),
        prior_document_source_CADs=2,prior_document_source_ids=['00749','01275'],prior_additional_controller_CADs=['00804'],
        prior_geometry_IDs_across_all_roles=len(read(ROOT/'outputs/input_audit/previous_geometry_use.json')),
        prior_scored_IDs_across_all_roles=len(read(ROOT/'outputs/input_audit/previous_scored_use.json')),
        fresh_training_candidate_CADs=len(pool['development_candidates']),fresh_test_11plus_candidate_CADs=len(pool['evaluation_candidates']),
        targets=dict(discovery=pool['discovery_target'],independent_validation=pool['validation_target'],test_maximum=final.get('effective_test_target',pool['evaluation_target'])),
        original_frozen_test_maximum=pool['evaluation_target'],
        test_cohort_amendment=optional('outputs/protocol/evaluation_cohort_amendment.json'),
        minimum_requirements=dict(discovery=pool['minimum_discovery_CADs'],independent_validation=pool['minimum_validation_CADs'],test=pool['minimum_evaluation_CADs']),
        newly_initially_qualified_development_CADs=len(selected.get('cases',[])),
        newly_collected_discovery_CADs=len(discovery),newly_collected_validation_CADs=len(validation),
        discovery_CADs_with_completed_physical_queries=sum(r.get('observed_query_count',0)>0 for r in discovery),
        validation_CADs_with_completed_physical_queries=sum(r.get('observed_query_count',0)>0 for r in validation),
        discovery_CADs_with_actual_rejections=sum(r['failure_count']>0 for r in discovery),
        discovery_CADs_with_measured_repair_pairs=sum(r['repair_pairs']>0 for r in discovery),
        new_document_admitted=complete.get('new_document_admitted'),bank_skills=complete.get('skills'),
        initially_qualified_test_CADs=len(final.get('cases',[])),completed_test_episodes=len(trials),
        bound_test_CADs=len(bound['cases']) if bound else None,
        pre_score_prior_shape_duplicate_exclusions=len(bound['excluded_prior_exact_geometry_duplicates']) if bound else None,
        completed_test_CADs=len({p.parent.parent.name for p in trials if len(list(p.parent.parent.glob('*/result.json')))==3}),
        download_is_not_learning=True,model_weights_updated=False)
    write(ROOT/'outputs/dataset_counts.json',counts)
    lines=['# v3 agent handoff and counts','',f'Observed {counts["created_utc"]}. Use these counts,not source archive totals,for study claims.','',
        '## Goal and intervention','',
        'Learn portable physical disassembly repair procedures from development failures as SKILL.md,validate on independent development CADs,freeze the bank,and test first episodes on new products. No model weights update. No winner is required. A=generated code/no bank;B=same generated code/S2;C=exact-state Graph+LLM ordering+fixed DFS/same S2. B-A changes document availability plus charged guided review;C-B changes an architecture bundle.',
        '', '## Required minimums and finite targets','',
        '|Role|Required minimum CADs|Operational target CADs|', '|---|---:|---:|',
        f'|Discovery / external-memory learning|{pool["minimum_discovery_CADs"]}|{pool["discovery_target"]}|',
        f'|Independent development validation|{pool["minimum_validation_CADs"]}|{pool["validation_target"]}|',
        f'|Unseen first-episode test|{pool["minimum_evaluation_CADs"]}|{counts["targets"]["test_maximum"]}|',
        '',f'Pre-score test-count amendment={counts["test_cohort_amendment"]}. The original frozen operational maximum remains recorded;model,actors,bank,physics and per-episode caps are unchanged.',
        '', 'These are lower bounds,not exact totals. Completion checks actual physical observations,not downloaded or prepared files. During collection,the finalized index may lag individual result.json files;read outputs/progress.json and raw results for live work.',
        '', '|Quantity|Observed count|','|---|---:|']
    for k in ['prior_document_source_CADs','prior_geometry_IDs_across_all_roles','prior_scored_IDs_across_all_roles',
            'fresh_training_candidate_CADs','fresh_test_11plus_candidate_CADs','newly_initially_qualified_development_CADs',
            'newly_collected_discovery_CADs','newly_collected_validation_CADs',
            'discovery_CADs_with_completed_physical_queries','validation_CADs_with_completed_physical_queries',
            'discovery_CADs_with_actual_rejections',
            'discovery_CADs_with_measured_repair_pairs','initially_qualified_test_CADs','completed_test_episodes','completed_test_CADs']:
        lines.append(f'|{k}|{counts[k]}|')
    lines += ['',f'New document admission={counts["new_document_admitted"]};bank skills={counts["bank_skills"]}. A rejected/provisional candidate is not deployed. A CAD in the discovery input list is not necessarily evidence of a successful repair or admitted skill. Source geometry use includes failed preparation and previous test work;do not count all prior geometry as training.',
        '', '## Evidence map','',
        'Start with outputs/dataset_counts.json,analysis/aggregate.csv and analysis/cohort_scope.json when available. Raw selection receipts contain detailed per-hull geometry QA and may be large;inspect focused fields instead of loading them in full. analysis/results.json links the preserved qualification source by SHA rather than duplicating its full QA payload.',
        '- `PLAN.md`: prospective split,admission,budget and stopping rules;`outputs/protocol/*amendment.json`: user-authorized changes before new model calls.',
        '- `outputs/input_audit/archive_inventory.json`: full CRC/SHA verified source archives;`pools.json`: metadata-only candidate order;`selected_development.json` and `selected_evaluation.json`: actual cohorts and all exclusions.',
        '- `outputs/development/collection_index.json` and `collection/*/result.json`: actual physical failure queries and separately assigned discovery/validation sources.',
        '- `outputs/development/new_document/{proposal,admission}.json`: model-generated portable procedure and independent accept/reject gate. `memory/S2.json`: identical frozen B/C bank.',
        '- `outputs/protocol/freeze.json`: actor,physical-engine,source-order and bank hashes before opening new test geometry. `outputs/evaluation/manifest.json`: bound identical per-product inputs. `outputs/evaluation/trials/*/{A,B,C}`: raw first episodes,prompts,code/ranks,token metadata,queries and restores.',
        '- `analysis/RESULTS.md`, `analysis/{trials,aggregate,paired_deltas,token_calls}.csv`, `analysis/token_usage.json`: all outcomes and costs,including unknown token usage and provider failures.',
        '- `replay/index.json`, `replay/audit.json`: independent MuJoCo event replays. PASS_VERIFIED_PREFIX preserves one charged unfinished query without inventing an outcome. Any successful reference sequence is extracted/revalidated after scoring,never supplied to the actor.',
        '- `outputs/preservation/audit.json`: old results/source/PPT integrity. `outputs/regressions_final.log`: executed recovery,document and API regressions.',
        '', '## Execution and recovery','',
        'Read `outputs/pipeline_state.json` and actual processes. A stale PID/heartbeat is not proof of live work. The finite supervisor is `python -B -m disassembly_docskills_v3.pipeline`;input preparation is reusable and locked;an already-started scored episode is finalized from its evidence and never rerun. Use the existing disassembly_learning_v1/.venv with PYTHONDONTWRITEBYTECODE=1. Read CLAUDE.md for continuity only;Claude is not assigned. No recurring automation or PPT edits.',
        '', '## Interpretation limits','',
        'ASAP official training/test source split is retained;previous project geometry IDs are excluded and shape fingerprints screen duplicates. This does not prove foundation-model pretraining novelty or manufacturer/factory provenance. All test cases require at least10removals and initial stability,but a complete path is not guaranteed in our restricted setup. One permanent original fixture,assumed material properties,source-axis fixed-orientation straight extraction and virtual restore differ from ASAP grasp/regrasp/motion planning. Input exclusions,unresolved budgeted planning,document reading,behavioral compliance and held-out efficacy are distinct. Use actual counts and denominators.']
    (ROOT/'AGENT_HANDOFF.md').write_text('\n'.join(lines)+'\n')
    status_path=ROOT/'STATUS.md'
    history=ROOT/'outputs/protocol/STATUS_before_counted_refresh.md'
    if status_path.exists() and not history.exists():history.write_bytes(status_path.read_bytes())
    state=optional('outputs/pipeline_state.json',{})
    status_lines=['# v3 counted status','',f'Observed {counts["created_utc"]}. Codex owns this study;Claude is not assigned.',
        '',f'Pipeline receipt: {state.get("status")} / {state.get("phase")}. Verify the actual process and OS lock before any recovery;this snapshot alone does not prove liveness.',
        '',f'Minimums={counts["minimum_requirements"]};finite operational targets={counts["targets"]}. Training includes3+component CADs;test requires11+components/10+removals.',
        '',f'Physically observed discovery={counts["discovery_CADs_with_completed_physical_queries"]};validation={counts["validation_CADs_with_completed_physical_queries"]}. Newly admitted document={counts["new_document_admitted"]};fixed bank documents={counts["bank_skills"]}. No model weights update.',
        '',f'Initially qualified test CADs={counts["initially_qualified_test_CADs"]};completed test episodes={counts["completed_test_episodes"]};fully scored test CADs={counts["completed_test_CADs"]}. Preparation is not scored evaluation.',
        '', 'Read AGENT_HANDOFF.md,outputs/dataset_counts.json,outputs/progress.json and raw evidence for detail. Preserve all prior studies/PPT. Never rerun a started final episode. No PPT work. Post-score verifier corrections are recorded under outputs/post_verification and do not alter actor,physics,bank,admission or scores.']
    status_path.write_text('\n'.join(status_lines)+'\n')
    print({k:counts[k] for k in ['newly_initially_qualified_development_CADs','newly_collected_discovery_CADs','newly_collected_validation_CADs','completed_test_episodes']})
    return counts

if __name__=='__main__':main()

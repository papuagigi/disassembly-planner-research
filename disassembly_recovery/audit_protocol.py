"""Independent file-only protocol audit. Never imports or runs an actor/simulator.

Default: immutable-source/input audit only. --final requires all 54 scheduled
results and the harness completion marker. Its output distinguishes equal
initial information from different system prompts and internal policies.
"""
from __future__ import annotations

import argparse
import collections
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
OUTPUT = ROOT / 'outputs/independent_protocol_audit.json'
LIMITS = {'max_calls': 8, 'max_checks': 120, 'max_steps': 10000000,
          'timeout_seconds': 480.0, 'max_checkpoints': 128, 'max_restores': 256}
METHODS = ['code_no_library', 'code_with_library', 'graph_llm_dfs_library']
EXPECTED_FREEZE = '2b3c11346b3d91709119d908a736eb8cf70ce4a84e6a4e78b54de8f7d788dc39'
EXPECTED_MANIFEST = '2f90aa3b2c0e154ee660d7738c9ddd95b98775bcde9b45df029b4334098afb22'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value, ensure_ascii=False):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=ensure_ascii,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def scrub_time(value):
    if isinstance(value, dict):
        return {k: scrub_time(v) for k, v in value.items() if k != 'elapsed_seconds'}
    if isinstance(value, list):
        return [scrub_time(v) for v in value]
    return value


def physical_key(state):
    remaining = sorted(state['remaining'])
    return digest({'remaining': remaining, 'poses': {p: state['poses'][p] for p in remaining}}, True)


def task_payload(path, method):
    marker = 'TASK AND FEEDBACK:\n' if method == METHODS[2] else 'TASK:\n'
    return json.loads(Path(path).read_text().split(marker, 1)[1])


class Audit:
    def __init__(self):
        self.checks = []
        self.trials = []

    def check(self, name, condition, detail=None):
        self.checks.append({'check': name, 'pass': bool(condition), 'detail': detail})
        return bool(condition)

    def source_input_audit(self):
        freeze_path = ROOT / 'outputs/protocol/actor_freeze.json'
        freeze = read(freeze_path)
        manifest = read(ROOT / 'outputs/evaluation/manifest.json')
        self.freeze, self.manifest = freeze, manifest
        for label, obj, expected in [('actor', freeze, EXPECTED_FREEZE), ('evaluation', manifest, EXPECTED_MANIFEST)]:
            unhashed = {k: v for k, v in obj.items() if k != 'manifest_sha256'}
            self.check(label + '_manifest_digest', digest(unhashed) == obj['manifest_sha256'] == expected)
            self.check(label + '_model_and_limits', obj['model'] == 'gpt-6-luna' and
                       obj['reasoning_effort'] == 'low' and obj['limits'] == LIMITS)
        self.check('actor_manifest_file_binding', sha(freeze_path) == manifest['actor_freeze_file_sha256'])
        self.check('same_frozen_sources_in_both_manifests', freeze['source_sha256'] == manifest['source_sha256'])
        for source, expected in freeze['source_sha256'].items():
            path = Path(source)
            frozen = ROOT / 'outputs/protocol/source_snapshot' / path.relative_to(WORKSPACE)
            self.check('source_unchanged:' + str(path.relative_to(WORKSPACE)), sha(path) == expected)
            self.check('snapshot_matches:' + str(path.relative_to(WORKSPACE)), frozen.exists() and sha(frozen) == expected)
        for asset, expected in manifest['asset_sha256'].items():
            self.check('asset_unchanged:' + str(Path(asset).relative_to(ROOT)), sha(asset) == expected)
        library = read(ROOT / 'outputs/protocol/library.json')
        self.check('library_frozen', digest(library) == freeze['library_sha256'] and
                   library['library_source'] == (ROOT / 'library_functions.py').read_text())
        self.library = library
        self.check('generator_frozen', sha(ROOT / 'data_tools/build_recovery_family.py') == freeze['generator_sha256'])
        authorization = read(ROOT / 'outputs/input_audit/generation_authorization.json')
        selection = read(ROOT / 'outputs/input_audit/selected_cases.json')
        protocol = read(ROOT / 'outputs/input_audit/selection_protocol.json')
        independently_verified = read(ROOT / 'outputs/input_audit/independent_verification.json')
        self.check('generation_authorized_after_actor_freeze',
                   datetime.fromisoformat(authorization['timestamp_utc']) > datetime.fromisoformat(freeze['timestamp_utc']) and
                   authorization['freeze_sha256'] == sha(freeze_path) and
                   authorization['generator_sha256'] == freeze['generator_sha256'])
        self.check('case_selection_geometry_only', selection['all_three_variants_certified'] and
                   authorization['no_actor_or_llm_calls'] and len(selection['cases']) == 3 and
                   all(c['accepted'] and c['attempt'] == 1 for c in selection['considered']))
        self.check('separate_full_graph_certification_present', independently_verified['pass_'] and
                   independently_verified['selected_index_sha256'] == sha(ROOT / 'outputs/input_audit/selected_cases.json') and
                   [x['full_graph']['minimum_removals'] for x in independently_verified['cases']] == [5, 6, 7] and
                   all(x['seeded_graph']['goal_states'] == 0 and x['restore_then_reference_success'] and
                       x['restore_did_not_refund_checks'] for x in independently_verified['cases']))
        development_hashes = {sha(WORKSPACE / p) for p in protocol['development_cases']}
        self.check('heldout_case_files_differ_from_development',
                   not development_hashes.intersection(sha(c['case_path']) for c in manifest['cases']))
        self.input_map = {}
        for case in manifest['cases']:
            for track, entry in case['tracks'].items():
                shared = read(entry['path'])
                self.input_map[(case['case_id'], track)] = shared
                prefix = case['case_id'] + ':' + track
                self.check('shared_input_hash:' + prefix, sha(entry['path']) == entry['sha256'])
                self.check('shared_observation_hash:' + prefix,
                           digest(scrub_time(shared['observation'])) == entry['observation_sha256'])
                self.check('preparation_charged:' + prefix, shared['state']['checks'] == entry['preparation_checks'] ==
                           (7 if track == 'seeded' else 6))
                self.check('duplicate_probe_alias:' + prefix, shared['observation']['common_probe_feedback'] ==
                           shared['observation']['current_state_feedback'])
                self.check('initial_key_exact:' + prefix, physical_key(shared['state']) == shared['observation']['state_key'])
        self.schedule = read(ROOT / 'outputs/evaluation/schedule.json')
        expected = {(i, r, m, t) for i in range(3) for r in range(1, 4) for m in METHODS for t in ('normal', 'seeded')}
        actual = {(s['case_index'], s['repeat'], s['method'], s['track']) for s in self.schedule}
        self.check('complete_unique_prespecified_schedule', len(self.schedule) == 54 and actual == expected and
                   [s['ordinal'] for s in self.schedule] == list(range(1, 55)))
        self.check('rotated_method_order', all(
            self.schedule[start + j]['method'] == METHODS[(self.schedule[start]['case_index'] +
                self.schedule[start]['repeat'] + (self.schedule[start]['track'] == 'seeded') - 1 + j) % 3]
            for start in range(0, 54, 3) for j in range(3)))
        self.provenance = {
            'freeze_timestamp_utc': freeze['timestamp_utc'],
            'generation_timestamp_utc': authorization['timestamp_utc'],
            'first_trial_timestamp_utc': min(read(p)['timestamp_utc'] for p in
                                            (ROOT / 'outputs/evaluation/trials').rglob('started.json')),
            'actor_manifest_sha256': freeze['manifest_sha256'],
            'evaluation_manifest_sha256': manifest['manifest_sha256'],
            'independent_case_audit_sha256': sha(ROOT / 'outputs/input_audit/independent_verification.json'),
            'note': 'File hashes and recorded chronology support the local freeze. They are not an external signed preregistration.'}
        self.check('case_generation_precedes_first_trial',
                   self.provenance['generation_timestamp_utc'] < self.provenance['first_trial_timestamp_utc'])

    def audit_prompt(self, path, method, initial=None, registry=None):
        relative = str(path.relative_to(ROOT))
        text = path.read_text()
        payload = task_payload(path, method)
        forbidden = ('/Users/', 'selection_report', 'part_roles', 'strict_minimum_removals',
                     'full_reachable_graph', 'wrong_branch_all_reachable_states',
                     'seeded_checkpoint', 'good_reference', 'gate_1', 'candidate01_certificate',
                     'initial_checkpoint', 'restoration_replay')
        found = [token for token in forbidden if token in text]
        self.check('prompt_has_no_privileged_material:' + relative, not found, found)
        self.check('prompt_limits:' + relative, payload['limits'] == LIMITS)
        if method == METHODS[2]:
            observation = payload['observation']
            key = observation['state_key']
            legal = {(p['id'], d) for p in observation['remaining_parts'] if not p.get('fixed', False)
                     for d in p.get('allowed_directions', ['+x', '-x', '+y', '-y', '+z', '-z'])}
            candidates = {(a['part_id'], a['direction']) for a in payload['candidate_actions']}
            rejected = {(t['part_id'], t['direction']) for t in observation['current_state_feedback'] if not t['valid']}
            self.check('C_candidates_legal_and_not_same_state_rejections:' + relative,
                       candidates <= legal and not candidates.intersection(rejected) and
                       len(candidates) == len(payload['candidate_actions']))
            graph = payload['directed_graph']
            self.check('C_graph_filtered_using_exact_current_state:' + relative, graph['state_key'] == key and
                       all(e['state_key'] == key for e in graph['edges']) and
                       {(a['part_id'], a['direction']) for a in graph['rejected_actions']} == rejected)
            self.check('C_graph_edges_have_current_physical_evidence:' + relative, all(
                any(t['part_id'] == e['to'] and t['direction'] == e['direction'] and
                    t['reason'] == 'path_collision' and e['from'] in t.get('blockers', [])
                    for t in observation['current_state_feedback']) for e in graph['edges']))
        metadata_path = path.parent / 'metadata.json'
        if metadata_path.exists():
            meta = read(metadata_path)
            self.check('provider_model_effort_and_no_tools:' + relative,
                       meta['requested_model'] == 'gpt-6-luna' and meta['requested_reasoning_effort'] == 'low' and
                       meta.get('tool_activity_count') == 0 and meta['prompt_sha256'] == sha(path))
            command = meta.get('command', [])
            self.check('provider_ephemeral_isolation:' + relative, '--ignore-user-config' in command and
                       '--ephemeral' in command and all('--disable' in command and feature in command for feature in
                       ('shell_tool', 'apps', 'plugins', 'memories', 'multi_agent')))
        if initial is None:
            return
        actual = payload['observation']
        if method != METHODS[2]:
            self.check('actual_initial_prompt_exact:' + relative, actual == initial['observation'])
            if method == METHODS[1]:
                self.check('actual_B_library_frozen:' + relative, payload['reusable_library'] == self.library)
            else:
                self.check('actual_A_has_no_library:' + relative, not payload['reusable_library'].get('available', True))
            return
        expected = copy.deepcopy(initial['observation'])
        expected.pop('common_probe_feedback')
        actual_core, expected_core = copy.deepcopy(actual), copy.deepcopy(expected)
        actual_recovery = actual_core.pop('recovery')
        expected_recovery = expected_core.pop('recovery')
        self.check('actual_C_initial_physical_information_equal:' + relative, actual_core == expected_core)
        expected_handles = {c['handle'] for c in expected_recovery['checkpoints']}
        actual_handles = {c['handle'] for c in actual_recovery['checkpoints']}
        extra = actual_handles - expected_handles
        self.check('actual_C_only_adds_current_checkpoint:' + relative,
                   expected_handles <= actual_handles and len(extra) <= 1 and all(
                       c['state_key'] == expected['state_key'] for c in actual_recovery['checkpoints'] if c['handle'] in extra))
        if registry:
            self.check('actual_C_checkpoint_metadata_host_logged:' + relative, all(
                c == registry['checkpoints'][c['handle']]['metadata'] for c in actual_recovery['checkpoints']))
        for k, v in expected_recovery.items():
            if k not in ('checkpoints', 'checkpoint_count'):
                self.check('actual_C_recovery_field:' + k + ':' + relative, actual_recovery[k] == v)

    def dynamic_audit(self):
        marker = ROOT / 'outputs/evaluation/complete.json'
        if not marker.exists():
            raise RuntimeError('Final audit requires the evaluation completion marker; do not audit partial results as final.')
        completed = read(marker)
        self.check('harness_completed_and_verified', completed['trials'] == 54 and completed['source_verification'] == 'PASS')
        actual_paths = set((ROOT / 'outputs/evaluation/trials').rglob('result.json'))
        expected_paths = set()
        for scheduled in self.schedule:
            case = self.manifest['cases'][scheduled['case_index']]
            method, track, repeat = scheduled['method'], scheduled['track'], scheduled['repeat']
            folder = ROOT / 'outputs/evaluation/trials' / case['case_id'] / track / f'repeat_{repeat:02d}' / method
            path = folder / 'result.json'
            expected_paths.add(path)
            self.check('scheduled_result_retained:' + str(path.relative_to(ROOT)), path.exists())
            if not path.exists():
                continue
            result = read(path)
            label = case['case_id'] + ':' + track + ':' + str(repeat) + ':' + method
            before_checks = len(self.checks)
            shared = self.input_map[(case['case_id'], track)]
            self.check('result_identity:' + label, all(result[k] == v for k, v in
                       [('case_id', case['case_id']), ('track', track), ('repeat', repeat), ('method', method)]))
            prompts = sorted((folder / 'llm_calls').glob('call_*/prompt.txt'))
            self.check('recorded_model_call_count:' + label, len(prompts) == result['llm_calls'] <= 8)
            self.check('all_model_metadata_retained:' + label,
                       all((p.parent / 'metadata.json').exists() for p in prompts))
            registry = result.get('recovery_state')
            for i, prompt in enumerate(prompts):
                self.audit_prompt(prompt, method, shared if i == 0 else None, registry)
            if registry is None:
                self.check('incomplete_worker_is_failed_and_unknown:' + label, result['success'] is False and
                           result['termination'] in ('wall_budget_exhausted', 'worker_error') and result['checker_calls'] is None)
                self.trials.append({'trial': label, 'success': False, 'termination': result['termination'],
                                    'resource_verifiability': 'incomplete_worker_state', 'pass': all(c['pass'] for c in self.checks[before_checks:])})
                continue
            self.check('same_declared_limits_model_protocol:' + label, result['limits'] == LIMITS and
                       result['model'] == 'gpt-6-luna' and result['reasoning_effort'] == 'low' and
                       result['protocol_sha256'] == self.manifest['manifest_sha256'])
            self.check('initial_actor_input_exact:' + label, result['initial_observation'] == shared['observation'] and
                       result['initial_observation_sha256'] == digest(scrub_time(shared['observation'])))
            self.check('initial_registry_prefix_retained:' + label,
                       registry['episode_id'] == shared['recovery_state']['episode_id'] and
                       registry['events'][:len(shared['recovery_state']['events'])] == shared['recovery_state']['events'] and
                       all(registry['checkpoints'][h] == cp for h, cp in shared['recovery_state']['checkpoints'].items()))
            events = registry['events']
            self.check('event_sequence:' + label, [e['event_index'] for e in events] == list(range(1, len(events) + 1)) and
                       registry['next_event_index'] == len(events) + 1)
            successful_restores = [e for e in events if e['operation'] == 'restore' and e.get('restored')]
            self.check('restore_counts_actual:' + label, len(successful_restores) == registry['restore_count'] == result['successful_restores'])
            self.check('resource_caps:' + label, 0 <= result['checker_calls'] <= 120 and
                       0 <= result['execution_steps'] <= 10000000 and len(registry['checkpoints']) <= 128 and
                       0 <= registry['restore_attempts'] <= 256)
            self.check('checkpoint_contains_no_refundable_budgets:' + label, all(
                set(cp['state']) == {'remaining', 'poses', 'actions'} and cp['metadata']['state_key'] == physical_key(cp['state'])
                for cp in registry['checkpoints'].values()))
            last_checks, last_key = None, None
            for event in events:
                suffix = label + ':' + str(event['event_index'])
                if last_checks is not None:
                    self.check('cumulative_check_chain:' + suffix, event['checks_before'] == last_checks)
                if last_key is not None:
                    self.check('physical_state_chain:' + suffix, event['state_key_before'] == last_key)
                if event.get('checks_after') is None:
                    self.check('unfinished_operation_only_at_end:' + suffix, event is events[-1] and not result['success'])
                    last_checks = None
                    last_key = None
                    continue
                after, before = event['checks_after'], event['checks_before']
                self.check('checks_never_refunded:' + suffix, after >= before)
                if event['operation'] in ('restore', 'checkpoint'):
                    self.check('restore_or_checkpoint_preserves_checks:' + suffix, after == before)
                elif event['status'] == 'completed':
                    self.check('physics_call_charged_once:' + suffix, after == before + 1)
                if event.get('restored'):
                    cp = registry['checkpoints'].get(event['handle'])
                    self.check('restore_returns_exact_saved_physics:' + suffix, bool(cp) and
                               event['state_key_after'] == cp['metadata']['state_key'])
                self.check('event_has_ordered_time:' + suffix, event['started_at_utc'] <= event['finished_at_utc'])
                last_checks, last_key = after, event['state_key_after']
            state = result['state']
            self.check('final_cumulative_check_consistency:' + label, state['checks'] == result['checker_calls'] and
                       (last_checks is None or last_checks == state['checks']))
            self.check('final_physical_key_consistency:' + label, last_key is None or physical_key(state) == last_key)
            self.check('trace_is_cumulative:' + label, result['trace'] == state['trace'] and
                       result['trace'][:len(shared['state']['trace'])] == shared['state']['trace'])
            for trace in result['trace']:
                event = events[trace['api_event_index'] - 1]
                self.check('trace_matches_operation:' + label + ':' + str(trace['checker_call']),
                           trace['checker_call'] == event['checker_call'] and
                           trace['physical_state_key_before'] == event['state_key_before'] and
                           trace['physical_state_key_after'] == event['state_key_after'] and
                           trace['operation'] == event['operation'] and trace['valid'] == event['valid'] and
                           bool(trace.get('committed')) == bool(event.get('committed')))
            self.check('success_is_verified_goal_within_actor_deadline:' + label, not result['success'] or (
                case['target_id'] not in state['remaining'] and result['termination'] == 'goal_reached' and
                result['elapsed_seconds'] <= 480.0 and len(state['actions']) >= case['reference']['minimum_removals']))
            if result['termination'] == 'check_budget_exhausted':
                self.check('physics_budget_failure_classified_from_counter:' + label,
                           not result['success'] and result['checker_calls'] == 120)
            if result['termination'] == 'call_budget_exhausted':
                self.check('model_budget_failure_classified_from_counter:' + label,
                           not result['success'] and result['llm_calls'] == 8)
            self.check('successful_backtracks_not_inferred:' + label,
                       (len(result['backtracks']) if isinstance(result['backtracks'], list) else result['backtracks']) == len(successful_restores))
            self.trials.append({'trial': label, 'case_id': case['case_id'], 'track': track, 'method': method,
                                'repeat': repeat, 'success': result['success'], 'termination': result['termination'],
                                'checker_calls': result['checker_calls'], 'llm_calls': result['llm_calls'],
                                'successful_restores': len(successful_restores),
                                'restore_reasons': dict(collections.Counter(
                                    b['reason'] for b in result['backtracks'])) if isinstance(result['backtracks'], list) else None,
                                'pass': all(c['pass'] for c in self.checks[before_checks:])})
        self.check('no_missing_or_extra_scheduled_results', actual_paths == expected_paths)

    def report(self, final):
        failed = [c for c in self.checks if not c['pass']]
        timing_note = ROOT / 'outputs/protocol/timing_overlap_note.json'
        if timing_note.exists():
            self.provenance['timing_overlap_record'] = {
                'path': str(timing_note), 'sha256': sha(timing_note), 'record': read(timing_note),
                'evidence_limit': 'Recorded filesystem mtime bounds, not a measurement of CPU contention or causal latency.'}
        out = {
            'audit_timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'mode': 'final' if final else 'static_only_dynamic_pending',
            'status': ('PASS_WITH_DISCLOSED_DESIGN_LIMITATIONS' if final else 'STATIC_PASS_DYNAMIC_PENDING') if not failed else 'FAIL',
            'audit_script_sha256': sha(__file__), 'provenance': self.provenance,
            'read_only_method': 'Independent stdlib-only file/hash/log inspection; no model calls, physics calls, actor imports or source edits.',
            'check_count': len(self.checks), 'failed_checks': failed,
            'manual_source_findings': {
                'common_api': 'A/B restricted PublicAPI subclasses SharedAPI; C uses the same SharedAPI directly. All can check/remove/checkpoint/restore/checkpoints/snapshot.',
                'exact_state_filter': 'C graph indexes rejected actions by exact remaining-part positions/quaternions/velocities. It filters only recorded same-state action failures; unknown candidates remain. Library ranks are soft ordering, not hard deletion.',
                'restoration_scope': 'Only remaining/poses/actions are saved and restored. Checks, trace, registry and events remain cumulative; LLM/opcode/time accounting lives outside saved state.',
                'provider_isolation': 'Frozen provider launches ephemeral inference in a new temporary directory, disables tools/apps/plugins/memories and uses an explicit model slug and reasoning effort.',
                'initial_observation_vs_prompt': 'All arms receive the same saved initial input. A/B first prompt observation is exact. C omits duplicate common_probe_feedback, keeps identical current_state_feedback, and in seeded trials creates one current-state checkpoint through the same public API before its first prompt. Prompt strings and role instructions intentionally differ.',
                'executable_library': 'B receives frozen library code plus a prebound skills object; C calls the same source functions after model skill-name selection. The source is an agent/human-authored development adaptation, not autonomous ASPIRE discovery.',
                'scope_of_holdout': 'Geometry generated and physically screened after actor freeze; same designed mechanism family as development, not an unseen family or a random sample of commercial CAD.'},
            'limitations': [
                'B-C is a complete-system comparison, not a one-factor causal estimate for LLM versus DFS.',
                'C library rank categories and direction preferences precede the model tie-break. Success cannot be attributed solely to LLM ranking.',
                'A has no cross-case reusable library, but retains within-episode observations, feedback, history and checkpoints. No arm changes model weights.',
                'Seeded recovery starts from an experimenter-imposed accepted wrong removal. Its recovery rate is not the frequency of spontaneous model errors.',
                'Three geometric variants of one designed 3D OBJ family, each repeated three times per track/condition; repeats are not independent products.',
                'The 10M opcode bound is an execution safety cap. Restricted generated-code counting and native fixed-controller counting are not equal FLOPs.',
                'The 480s actor limit and 120s model/code-turn limits bound execution; worker startup, teardown and serialization can make outer elapsed time slightly larger.',
                'Independent offline physical certification overlapped the first trial. Wall-clock timing is secondary and subject to machine-load/backend confounding.',
                'Explicit model slug and low reasoning are fixed; backend snapshot, stochastic seed and temperature are not controlled by this interface.',
                'The six-axis sampled extraction and MuJoCo residual stability model is not a force-driven robot, grasping, or complete continuous-motion planner.',
                'Budget or runtime failure is UNKNOWN within budget, not proof that physical disassembly is impossible.',
                'Development B v0 failure and v1 interface wording repair are preserved separately; only the post-repair frozen actors enter this evaluation.'
                ,'The result.accepted_removals field has different definitions in code and host actors and must not be pooled. Comparative materials instead recompute cumulative committed trace actions and final actions separately.'
                ,'An observed restore is not automatically exhaustive DFS backtracking. C restore reasons are reported from actual logs; skill_soft_support_risk is an early heuristic recovery.'
            ],
            'trials': self.trials,
            'termination_counts': dict(collections.Counter(t['termination'] for t in self.trials)) if final else None,
            'checks': self.checks}
        OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'status': out['status'], 'checks': len(self.checks), 'failures': failed,
                          'trials': len(self.trials), 'output': str(OUTPUT)}, ensure_ascii=False))
        return not failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    audit = Audit()
    audit.source_input_audit()
    if args.final:
        audit.dynamic_audit()
    raise SystemExit(0 if audit.report(args.final) else 1)


if __name__ == '__main__':
    main()

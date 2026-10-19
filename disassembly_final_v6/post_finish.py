"""Finalize interpretation and an optional local replay server after scoring."""
import socket
import subprocess
import sys
from .common import ROOT,WORKSPACE,read,write,sha,utc

def main():
    from .post_root_coverage import main as root_coverage
    root_coverage()
    from .post_pack import main as pack
    pack()
    result=read(ROOT/'analysis/results.json');development=read(ROOT/'outputs/development/complete.json')
    from .post_cohort_scope import summary as cohort_amendment
    amendment=cohort_amendment()
    confirmation=ROOT/'outputs/protocol/cohort_amendment_confirmation.json'
    if amendment and confirmation.exists():
        recorded=read(confirmation)
        assert recorded['original_amendment_sha256']==sha(ROOT/'outputs/protocol/cohort_amendment.json')
        amendment={**amendment,'subsequent_explicit_user_confirmation':recorded}
    lines=['# Final bounded comparison','',f'Created UTC: {utc()}. One final pass;no test-log retuning.','',
        'Discovery/validation have11–20parts;test uses the predeclared11–20first/21+backup reserve. Report actual sizes. Full success=n−1stable committed removals. Model=gpt-6-luna/low;8logical CLI calls,240physical queries,900seconds per episode. B/C use identical frozen S3;A has no document memory. All share the physical/restoration API and initial input.',
        '',f'Development: {development}. Prior90discovery CADs contributed local probes,not90complete disassemblies. Eight byte-identical earlier1GiBfull-search outcomes were retained;two additional4GiBdevelopment episodes used the existing memory-limited CADs05459/01613. Ten episodes are eight unique long CADs,not ten independent products. Four inherited full-search CADs overlap the90local-probe inputs;the target unique current-line discovery count is94. Actual attempted versus usable failure-repair CADs are distinct. The user-approved three-CAD extension and16-hour target are recorded in protocol/memory_budget_amendment.json. Three fresh validation CADs replace the earlier partial validation group. A candidate can be rejected;prior documents remain. These are external-memory updates,not model-weight training. This is a small pilot comparison,not broad industrial-performance estimation.',
        '',('Pre-outcome cohort amendment: '+str(amendment)+'. The original four-CAD minimum was not met;all75input candidates were processed and only three passed unchanged input criteria. The sample-count amendment was recorded before any A/B/C policy episode;no policy outcome selected or removed a CAD. Models,budgets,documents,physics and API remain frozen.' if amendment else 'Original registered CAD target retained.'),
        '', '|Arm|Raw goal reached|Goal reached without native warning|Mean final progress|Mean best progress|Mean checks|Mean calls|Known mean tokens|Mean seconds|', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in result['aggregate']:
        lines.append(f"|{r['arm']}|{r['successes']}/{r['n']}|{r['warning_free_goal_reached']}/{r['n']}|{r['final_progress_mean']:.3f}|{r['best_progress_mean']:.3f}|{r['checks_mean']:.1f}|{r['llm_calls_mean']:.2f}|{r['total_tokens_mean']:.0f}|{r['elapsed_seconds_mean']:.1f}|")
    lines+=['','Unknown token usage is not zero;inspect token_usage.json. Provider totals include CLI context;cache/reasoning are subsets. Model calls are logical CLI turns,not observed HTTP requests.',
        '', '## Interpretation', '',
        'B−A changes document availability plus charged review. C−B changes graph/DFS/code generation/scheduling together. No pure C-memory ablation was run. v3→v6 changes learning experience,input cohort and wall budget;do not attribute differences to one cause. Two4GiBadditional TRAINING episodes retain600queries/900s/8calls;the preserved eight1GiBepisodes retain their original five240-query and three600-query budgets. Final A/B/C all use4GiBRSS. Final A/B/C all retain the same240query cap. Mixed training budgets are not a controlled policy-improvement comparison.',
        'Full success,final progress,best progress,and branch restoration are distinct. Undone accepted removals measure search work. A failed uncommitted extraction alone is not backtracking. Reading or declaring a document does not prove compliance or benefit.',
        'Recognized wall-deadline/budget exceptions are reported separately from nonbudget execution errors. See reporting_classification_audit.json and caught_budget_stop_count in trials.csv. Do not call an intentional900-second stop a generated-code defect. Raw scores and result hashes remain unchanged.',
        'Read ROOT_ACTION_COVERAGE.md and root_action_coverage.json for post-score evidence at the exact initial state. Full warning-free/replay-verified coverage with every declared action rejected can establish a blocked first step under this finite local API only. Incomplete coverage leaves feasibility unresolved;it does not establish real-world or original ASAP impossibility. No extra model or physics call is used by this diagnostic.',
        'Source/initial-physics exclusions are separate from planner failures. An unresolved budgeted episode is not proof of physical impossibility. One permanent fixture,six straight source-axis directions,assumed mass/friction and local finite collision checks differ from original ASAP. Virtual restores are not real reassembly.',
        'Actor resident-memory exhaustion,native MuJoCo errors/warnings,and collision/stability rejection are different observed mechanisms. Initial capacity screening cannot guarantee runtime memory stays within the cap. Keep every started episode and cost;do not silently replace a resource-limited input or count its operational error as a learned physical failure.',
        'Deterministic replay can reproduce native solver overflow. Raw outcomes are preserved;the additional warning-free goal column excludes any episode with a native worker warning or missing worker log without dropping its CAD from the denominator. See native_engine_health/native_warning_count in trials.csv. No-warning observation is not proof of complete physical fidelity. Such development episodes cannot supply new skill-procedure evidence;validation warnings veto admission.',
        'All actual first episodes and negative outcomes are retained. A verified prefix marks one unfinished charged check as unknown. Reference paths are derived and physically revalidated after scoring,not unique/optimal answers or original ASAP certificates.',
        'This single final cycle stops here regardless of winner. PPT waits for user review.']
    (ROOT/'analysis/RESULTS.md').write_text('\n'.join(lines)+'\n')
    from .protocol import verify
    verify()
    from disassembly_docskills_v3.protocol import verify as verify_previous
    if (WORKSPACE/'disassembly_docskills_v3/outputs/protocol/freeze.json').exists():verify_previous()
    prior_complete=WORKSPACE/'disassembly_docskills_v3/outputs/evaluation/complete.json'
    prior_count=0
    if prior_complete.exists():
        for row in read(prior_complete)['episodes']:
            assert sha(row['result_path'])==row['sha256']
            prior_count+=1
    preserved=read(ROOT/'protocol/prior_v4_preservation.json')
    for group in ['results_sha256','sources_sha256']:
        for relative,expected in preserved[group].items():assert sha(WORKSPACE/relative)==expected,('Preserved v4artifact changed',relative)
    preserved_v5=read(ROOT/'protocol/prior_v5_preservation.json')
    for relative,expected in preserved_v5['sha256'].items():assert sha(WORKSPACE/relative)==expected,('Preserved v5artifact changed',relative)
    current=read(ROOT/'outputs/evaluation/complete.json')
    for row in current['episodes']:assert sha(row['result_path'])==row['sha256'],('Current raw result changed',row['result_path'])
    manifest=read(ROOT/'outputs/evaluation/manifest.json')
    for path,expected in manifest['asset_sha256'].items():assert sha(path)==expected,('Bound input asset changed',path)
    write(ROOT/'analysis/source_hash_audit.json',dict(status='PASS',utc=utc(),verified_frozen_sources=True,previous_final_results_preserved=prior_count,
        prior_v4_results_preserved=len(preserved['results_sha256']),prior_v4_sources_preserved=len(preserved['sources_sha256']),
        prior_v5_artifacts_preserved=len(preserved_v5['sha256']),current_final_raw_results_preserved=len(current['episodes']),
        bound_input_assets_preserved=len(manifest['asset_sha256'])))
    port=8785
    with socket.socket() as s:available=s.connect_ex(('127.0.0.1',port))!=0
    if available:
        log=(ROOT/'outputs/replay_server.log').open('ab')
        p=subprocess.Popen([sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1','--directory',str(ROOT)],stdout=log,stderr=log,start_new_session=True)
        write(ROOT/'outputs/replay_server.json',dict(pid=p.pid,url=f'http://127.0.0.1:{port}/viewer/index.html',utc=utc()))

if __name__=='__main__':main()

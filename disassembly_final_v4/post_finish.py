"""Finalize interpretation and an optional local replay server after scoring."""
import socket
import subprocess
import sys
from .common import ROOT,WORKSPACE,read,write,sha,utc

def main():
    result=read(ROOT/'analysis/results.json');development=read(ROOT/'outputs/development/complete.json')
    lines=['# Final bounded comparison','',f'Created UTC: {utc()}. One final pass;no test-log retuning.','',
        'Discovery/validation have11–20parts;test uses the predeclared11–20first/21+backup reserve. Report actual sizes. Full success=n−1stable committed removals. Model=gpt-6-luna/low;8logical CLI calls,240physical queries,900seconds per episode. B/C use identical frozen S3;A has no document memory. All share the physical/restoration API and initial input.',
        '',f'Development: {development}. Prior90discovery CADs contributed local probes. Four of those CADs received further full-search experience plus six new CADs:96unique discovery CADs. Ten separate new validation CADs were evaluated once. A candidate can be rejected;prior documents remain. These are external-memory updates,not model-weight training.',
        '', '|Arm|Raw goal reached|Goal reached without native warning|Mean final progress|Mean best progress|Mean checks|Mean calls|Known mean tokens|Mean seconds|', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in result['aggregate']:
        lines.append(f"|{r['arm']}|{r['successes']}/{r['n']}|{r['warning_free_goal_reached']}/{r['n']}|{r['final_progress_mean']:.3f}|{r['best_progress_mean']:.3f}|{r['checks_mean']:.1f}|{r['llm_calls_mean']:.2f}|{r['total_tokens_mean']:.0f}|{r['elapsed_seconds_mean']:.1f}|")
    lines+=['','Unknown token usage is not zero;inspect token_usage.json. Provider totals include CLI context;cache/reasoning are subsets. Model calls are logical CLI turns,not observed HTTP requests.',
        '', '## Interpretation', '',
        'B−A changes document availability plus charged review. C−B changes graph/DFS/code generation/scheduling together. No pure C-memory ablation was run. v3→v4 changes both learning experience and wall budget;do not attribute differences to one cause.',
        'Full success,final progress,best progress,and branch restoration are distinct. Undone accepted removals measure search work. A failed uncommitted extraction alone is not backtracking. Reading or declaring a document does not prove compliance or benefit.',
        'Source/initial-physics exclusions are separate from planner failures. An unresolved budgeted episode is not proof of physical impossibility. One permanent fixture,six straight source-axis directions,assumed mass/friction and local finite collision checks differ from original ASAP. Virtual restores are not real reassembly.',
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
    write(ROOT/'analysis/source_hash_audit.json',dict(status='PASS',utc=utc(),verified_frozen_sources=True,previous_final_results_preserved=prior_count))
    port=8783
    with socket.socket() as s:available=s.connect_ex(('127.0.0.1',port))!=0
    if available:
        log=(ROOT/'outputs/replay_server.log').open('ab')
        p=subprocess.Popen([sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1','--directory',str(ROOT)],stdout=log,stderr=log,start_new_session=True)
        write(ROOT/'outputs/replay_server.json',dict(pid=p.pid,url=f'http://127.0.0.1:{port}/viewer/index.html',utc=utc()))

if __name__=='__main__':main()

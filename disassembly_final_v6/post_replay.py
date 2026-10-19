"""Independent replay of all retained first episodes,including failed ones."""
from pathlib import Path
import os
import shutil
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress
from .post_evidence import replay_result
from .metrics import summarize
from disassembly_docskills_v1.post_replay import annotate
from disassembly_real_v3.simulator import FullDisassemblySim
from .native_health import audit as audit_native_health

LABELS={'A':'A · LLM 코드 / 문서 없음','B':'B · LLM 코드 / 분해 절차 문서',
        'C':'C · Graph·LLM 순위·DFS / 같은 분해 절차 문서'}
def relative(path,base):return os.path.relpath(Path(path).resolve(),Path(base).resolve())

def viewer():
    folder=ROOT/'viewer';old=WORKSPACE/'disassembly_docskills_v1/viewer'
    if not old.exists():old=WORKSPACE/'viewer' # portable GitHub snapshot
    if not (folder/'vendor').exists():shutil.copytree(old/'vendor',folder/'vendor')
    text=(old/'index.html').read_text().replace('문서형 skill · 3D 분해 실험','실제 분해 실패 절차 · 대형 CAD 비교')
    text=text.replace('별도로 검증한 가능한 순서','실행 후 재검증한 가능한 순서').replace('평가 LLM에 제공하지 않은 참고 경로입니다.','검증된 성공 경로가 있는 경우에만 평가 후 재검증한 참고 순서를 표시합니다. 평가 LLM에는 미리 제공하지 않습니다.')
    text=text.replace('viewer.js?rev=document-final-2','viewer.js?rev=final-document-v4')
    text=text.replace('재생 시간은 시각화용이며 실제 분해 작업 시간과 다릅니다.',
        '재생 시간은 시각화용이며 실제 분해 작업 시간과 다릅니다. 거절된 검사는 현재 조립체 상태에 적용되지 않습니다.')
    (folder/'index.html').write_text(text)
    js=(old/'viewer.js').read_text().replace(
        "C:'C · Graph·LLM 순위·DFS / 문서 있음',C_S0:'C(S0) · Graph·LLM 순위·DFS / 문서 없음'",
        "C:'C · Graph·LLM 순위·DFS / 같은 분해 절차 문서'")
    js=js.replace("txt('sequence',steps.map((a,i)=>(i+1)+'. '+a.part_id+' ('+a.direction+')').join(' → '));",
        "txt('sequence',steps.length?steps.map((a,i)=>(i+1)+'. '+a.part_id+' ('+a.direction+')').join(' → '):'이 예산에서 검증된 성공 경로가 없습니다. 분해 불가능을 뜻하지 않습니다.');")
    js=js.replace("const data=await response.json();", "const data=resolved.pathname.endsWith('.gz')?JSON.parse(await new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).text()):await response.json();")
    warning="if(s.native_engine_health&&s.native_engine_health!=='NO_NATIVE_WARNINGS_RECORDED'){txt('scope','MuJoCo 경고 또는 로그 누락 · planner 실패와 구분');txt('result','물리 계산 확인 필요');$('result').className='tag failure';stat('MuJoCo 경고',s.native_warning_count??'알 수 없음');txt('physics','접촉·제약 계산의 자원 부족 등 native 경고가 있습니다. 같은 오류를 다시 재생해도 물리 검증 성공을 뜻하지 않습니다. '+(episode.physics_scope??''));}\n  "
    js=js.replace('if(s.diagnostic){',warning+'if(s.diagnostic){')
    (folder/'viewer.js').write_text(js)

def main():
    manifest=read(ROOT/'outputs/evaluation/manifest.json');viewer();out=ROOT/'replay';items=[];audits=[];refs=[];errors=[]
    for case in manifest['cases']:
        results={a:read(ROOT/'outputs/evaluation/trials'/case['case_id']/a/'result.json') for a in ['A','B','C']}
        health={a:audit_native_health(ROOT/'outputs/evaluation/trials'/case['case_id']/a) for a in ['A','B','C']}
        successful=next((a for a in ['A','B','C'] if results[a].get('success') and health[a]['warning_free_observed']),None)
        ref=None
        if successful:
            refpath=out/'reference'/case['case_id']/'episode.json'
            if not refpath.exists():
                shared=read(case['shared_path']);actions=results[successful]['actions']
                sim=FullDisassemblySim(case['case_path'],max_checks=len(actions),state=shared['state'],capture=True)
                for a in actions:assert sim.remove(a['part_id'],a['direction'])['valid']
                assert sim.success
                sim.dump_demo(refpath,title=case['case_id']+' · 평가 후 재검증 경로',summary=dict(reference=True,condition='reference',
                    success=True,required_removals=case['required_removals'],final_removed=len(actions),llm_calls=0,checks=sim.checks,
                    source_scope='성공한 실제 실행의 경로를 평가 후 독립 검증 · 유일한 정답/최적 경로 아님'))
                ep=read(refpath);ep.update(case_id=case['case_id'],condition='reference',assembly_display_name=case['case_id'],
                    reference_sequence=dict(steps=[{k:a[k] for k in ['part_id','direction']} for a in actions]),
                    document_reads=[],document_application_claims=[],physics_scope='현재 로컬 물리 모델 조건부 검증; 원본 ASAP 동역학과 같지 않습니다.')
                for f in ep['frames']:f['completed_removals']=len(f['removed'])
                write(refpath,ep)
            ref=dict(path=refpath,actions=results[successful]['actions']);refs.append(dict(case_id=case['case_id'],url=relative(refpath,ROOT/'viewer'),source_arm=successful,after_evaluation=True))
        for arm,result in results.items():
            rp=ROOT/'outputs/evaluation/trials'/case['case_id']/arm/'result.json';dest=out/'data'/case['case_id']/arm
            dest.mkdir(parents=True,exist_ok=True);epath=dest/'episode.json';apath=dest/'audit.json'
            if not epath.exists():
                try:audit,sim,extra=replay_result(rp,shared_path=case['shared_path'],capture=True,allow_incomplete=True)
                except Exception as exc:
                    errors.append(dict(case_id=case['case_id'],arm=arm,error=repr(exc)));continue
                metrics=summarize(result);summary=dict(**metrics,condition=arm,method_label=LABELS[arm],reference=False,
                    model=manifest['model'],reasoning_effort=manifest['reasoning_effort'],limits=manifest['limits'],
                    bank_version=result.get('bank_version'),library_enabled=arm!='A',required_removals=case['required_removals'],
                    actions=result.get('actions',[]),replay_audit=audit['status'],learning_updates=0,
                    unfinished_reserved_checks=audit['charged_unfinished_checks'],
                    native_engine_health=health[arm]['status'],native_warning_count=health[arm]['warning_count'],
                    warning_free_goal_reached=bool(result['success'] and health[arm]['warning_free_observed']),
                    source_scope='미사용 원본 CAD의 첫 실행 · 초기 물리만으로 선정 · 로컬 물리 모델 조건부 결과')
                sim.events=extra['events'];sim.dump_demo(epath,title=case['case_id']+' · '+LABELS[arm],summary=summary)
                episode=read(epath);tagged={**result,'_path':rp,'_episode_parent':dest}
                annotate(episode,tagged,result['recovery_state']['events'],extra)
                if audit['status']=='PASS_VERIFIED_PREFIX':
                    episode['replay_scope']='완료된 사건만 독립 재검증했습니다. 마지막 검사는 실행 중 종료되어 결과가 없으며 비용은 원래 점수에 유지됩니다.'
                    for frame in episode['frames']:
                        if frame.get('phase')=='unfinished_reserved_check':frame['checks_spent']=result['checker_calls']
                episode.update(schema='physical_document_final_CAD_replay_v4',assembly_display_name=case['case_id'].replace('asap_','ASAP '),
                    document_application_plans=[dict(call=d['call'],plan=d.get('document_plan',[])) for d in result.get('decisions',[]) if d.get('document_plan')])
                if ref:episode['reference_sequence']=dict(steps=[{k:a[k] for k in ['part_id','direction']} for a in ref['actions']],
                    episode_url=relative(ref['path'],dest),local_verified=True,after_evaluation=True,unique=False,optimality_proven=False)
                write(epath,episode);write(apath,audit,exclusive=True)
            audit=read(apath);assert audit['status'] in ('PASS','PASS_VERIFIED_PREFIX');audits.append(dict(case_id=case['case_id'],arm=arm,**audit))
            items.append(dict(case_id=case['case_id'],arm=arm,label=LABELS[arm],url=relative(epath,ROOT/'viewer'),
                result_url=relative(rp,ROOT/'viewer'),episode_sha256=sha(epath),summary=read(epath)['summary']))
            progress('actual_replay_verified',case=case['case_id'],arm=arm,queries=audit['physical_queries_replayed'],completed=len(items))
            write(out/'index.json',dict(status='PARTIAL',episodes=items,references=refs,default_url=items[0]['url']))
    write(out/'index.json',dict(status='PASS' if not errors else 'INCOMPLETE',created_utc=utc(),episodes=items,references=refs,default_url=items[0]['url'] if items else None))
    write(out/'audit.json',dict(status='PASS' if not errors else 'FAIL',episodes=audits,errors=errors,no_model_calls=True,
        physical_queries=sum(r['physical_queries_replayed'] for r in audits),restores=sum(r['restores_verified'] for r in audits),
        post_score_verifier_sha256=sha(ROOT/'post_evidence.py'),original_scores_and_admission_unchanged=True))
    progress('all_actual_replays_ready',episodes=len(items),errors=len(errors))

if __name__=='__main__':main()

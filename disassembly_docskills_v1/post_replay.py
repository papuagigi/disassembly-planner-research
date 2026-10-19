"""Post-score actual API replay and a separate withheld feasible reference view."""
from pathlib import Path
import copy
import json
import os
import shutil
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress
from .protocol import verify
from .evidence_replay import replay_result
from .metrics import summarize
from disassembly_real_v3.simulator import FullDisassemblySim

LABELS={'A':'A · LLM 코드 / 문서 없음','B':'B · LLM 코드 / 문서 있음',
        'C':'C · Graph·LLM 순위·DFS / 문서 있음','C_S0':'C(S0) · Graph·LLM 순위·DFS / 문서 없음'}

def relative(path,base):return os.path.relpath(Path(path).resolve(),Path(base).resolve())

def annotate(episode,result,api_events,extra):
    parts={p['id']:p for p in episode['parts']};byevent={e['event_index']:e for e in api_events}
    first_id=episode['target_id']
    for i,frame in enumerate(episode['frames']):
        event=byevent.get(frame.get('api_event_index'),{})
        remaining=set(parts)-set(frame['removed'])
        frame.update(run_stage='planner',checks_spent=event.get('checks_after',0),
            completed_removals=len(parts)-len(remaining),
            focus_target_id=first_id if first_id in remaining else next((p for p in sorted(remaining) if not parts[p]['fixed']),None))
        if event.get('part_id'):
            frame['current_action']={k:event.get(k) for k in ['part_id','direction','valid','reason','operation']}
    episode.update(schema='document_skills_actual_replay_v1',case_id=result['case_id'],condition=result['condition'],
        actual_source=dict(result_url=relative(result['_path'],result['_episode_parent']),result_sha256=sha(result['_path'])),
        planner_start_frame=0,failure_frames=extra['failure_frames'],restore_frames=extra['restore_frames'],
        api_timeline=api_events,document_reads=result.get('document_reads',[]),
        document_application_claims=[dict(call=d['call'],skill_ids=d.get('claimed_application_ids',[]),summary=d.get('response',{}).get('summary')) for d in result['decisions'] if d.get('claimed_application_ids')],
        physics_scope='OBJ 원형의 표본화된 직선 경로 검사 + MuJoCo 잔류 중력·마찰. 추출은 힘 기반 로봇 동작이 아닙니다.',
        memory_scope='문서 선택·문맥 제공·사용 선언을 기록합니다. 사용 선언은 개선 효과의 증명이 아닙니다.',
        timeline_scope='재생 시각은 시각화용입니다. 실제 벽시계 실행 시간과 분해 작업 시간이 아닙니다.')
    episode['changed_restore_frames']=[i for i,f in enumerate(episode['frames'])
        if (byevent.get(f.get('api_event_index'),{}).get('operation')=='restore'
            and byevent[f['api_event_index']].get('state_key_before')!=byevent[f['api_event_index']].get('state_key_after'))]
    episode['summary']['changed_state_restores']=sum(e['operation']=='restore' and e.get('status')=='completed'
        and e.get('state_key_before')!=e.get('state_key_after') for e in api_events)

def main():
    verify();manifest=read(ROOT/'outputs/evaluation/manifest.json');completion=read(ROOT/'outputs/evaluation/complete.json')
    assert len(completion['episodes'])==manifest['planned_episodes']
    out=ROOT/'replay';viewer=ROOT/'viewer';viewer.mkdir(exist_ok=True)
    old_vendor=WORKSPACE/'disassembly_real_v3/viewer/vendor'
    if not (viewer/'vendor').exists():shutil.copytree(old_vendor,viewer/'vendor')
    items=[];audits=[];references=[]
    for case in manifest['cases']:
        ref_folder=out/'reference'/case['case_id'];ref_folder.mkdir(parents=True,exist_ok=True)
        refpath=ref_folder/'episode.json'
        if not refpath.exists():
            witness=read(case['reference_path']);shared=read(case['shared_path'])
            sim=FullDisassemblySim(case['case_path'],max_checks=len(witness['actions']),state=shared['state'],capture=True)
            for action in witness['actions']:
                r=sim.remove(action['part_id'],action['direction']);assert r['valid']
            assert sim.success
            summary=dict(reference=True,condition='reference',success=True,required_removals=len(sim.parts)-1,
                final_removed=len(sim.actions),llm_calls=0,checks=sim.checks,source_scope='현재 로컬 모델에서 검증한 가능한 순서 · 유일한 정답/최적 순서 아님')
            sim.dump_demo(refpath,title=case['case_id']+' · 검증된 참고 순서',summary=summary)
            ep=read(refpath);ep.update(case_id=case['case_id'],condition='reference',
                reference_sequence={'steps':[{k:a[k] for k in ['part_id','direction']} for a in witness['actions']]},
                official_ASAP_certificate=case['official'],reference_path_sha256=case['reference_sha256'],
                physics_scope='평가 LLM에 제공하지 않은 별도 로컬 경로 재실행',document_reads=[],document_application_claims=[])
            for f in ep['frames']:f['completed_removals']=len(f['removed'])
            write(refpath,ep)
        references.append(dict(case_id=case['case_id'],url=relative(refpath,viewer),episode_sha256=sha(refpath),official=case['official']))
        for arm in manifest['arms']:
            folder=ROOT/'outputs/evaluation/trials'/case['case_id']/arm;rp=folder/'result.json';result=read(rp)
            dest=out/'data'/case['case_id']/arm;dest.mkdir(parents=True,exist_ok=True);episode_path=dest/'episode.json';audit_path=dest/'audit.json'
            if not episode_path.exists():
                audit,sim,extra=replay_result(rp,shared_path=case['shared_path'],capture=True)
                metrics=summarize(result)
                summary=dict(**metrics,condition=arm,method_label=LABELS[arm],reference=False,model=manifest['model'],
                    reasoning_effort=manifest['reasoning_effort'],limits=manifest['limits'],bank_version=result['bank_version'],
                    library_enabled=arm in ('B','C'),required_removals=result['required_removals'],actions=result['actions'],
                    replay_audit='PASS',learning_updates=0,source_scope='연구에서 처음 평가하는 공개 CAD · 고정된 로컬 물리 모델 조건부 결과')
                sim.events=extra['events'];sim.dump_demo(episode_path,title=case['case_id']+' · '+LABELS[arm],summary=summary)
                episode=read(episode_path);result['_path']=rp;result['_episode_parent']=dest
                annotate(episode,result,result['recovery_state']['events'],extra)
                episode.update(assembly_display_name=case['case_id'].replace('asap_','ASAP '),
                    reference_sequence={'steps':[{k:a[k] for k in ['part_id','direction']} for a in read(case['reference_path'])['actions']],
                        'episode_url':relative(refpath,dest),'local_verified':True,'unique':False,'optimality_proven':False},
                    official_ASAP_certificate=case['official'])
                write(episode_path,episode);write(audit_path,audit,exclusive=True)
            audit=read(audit_path);assert audit['status']=='PASS'
            items.append(dict(case_id=case['case_id'],arm=arm,label=LABELS[arm],url=relative(episode_path,viewer),
                result_url=relative(rp,viewer),episode_sha256=sha(episode_path),summary=read(episode_path)['summary']))
            audits.append(dict(case_id=case['case_id'],arm=arm,**audit))
            progress('actual_replay_verified',case=case['case_id'],arm=arm,queries=audit['physical_queries_replayed'])
    write(out/'index.json',dict(status='PASS',created_utc=utc(),episodes=items,references=references,
        default_url=items[0]['url'] if items else None,protocol_sha256=manifest['protocol_sha256']))
    write(out/'audit.json',dict(status='PASS',episodes=audits,references=references,
        no_model_calls=True,physical_queries=sum(a['physical_queries_replayed'] for a in audits),restores=sum(a['restores_verified'] for a in audits)))
    progress('all_actual_replays_ready',episodes=len(items),references=len(references))

if __name__=='__main__':main()

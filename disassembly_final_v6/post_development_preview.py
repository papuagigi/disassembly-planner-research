"""Reconstruct05459's actual26queries for viewing;never run a planner."""
import fcntl
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from .common import ROOT,WORKSPACE,read,write,sha,utc
from .dataset import pools
from .cohort import resolved_case
from .metrics import summarize
from .post_evidence import replay_result
from .native_health import inspect_log
from .post_pack import SAFE_KEYS,clean

DEST=ROOT/'replay/development/asap_05459/C'


def capture():
    folder=ROOT/'outputs/development/memory_extension/asap_05459'
    result_path=folder/'result.json';result=read(result_path)
    assert result['success'] and result['completed_removals']==16
    assert read(folder/'physical_audit.json')['status']=='PASS'
    assert read(folder/'engine_health.json')['warning_free_observed']
    if (DEST/'episode.json').exists():return
    case=next(resolved_case(c) for c in pools()['reused_discovery_cases'] if c['case_id']=='asap_05459')
    lock=ROOT/'outputs/development/discovery_collection.lock'
    with lock.open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        phase=read(ROOT/'outputs/pipeline_state.json')['phase']
        allowed={'prepare_development_inputs','drain_preserved_input_workers_after_scope_reduction',
                 'waiting_for_prior_replays_and_integrity','verify_regressions_before_new_learning','full_search_learning'}
        assert phase in allowed,('Do not overlap native preview with scored validation/test',phase)
        before=sha(result_path)
        audit,sim,extra=replay_result(result_path,shared_path=case['shared_path'],capture=True,allow_incomplete=False)
        assert audit['status']=='PASS' and sim.success
        DEST.mkdir(parents=True,exist_ok=True)
        sim.events=extra['events']
        summary=dict(**summarize(result),condition='C',method_label='C · 4GiB 추가학습',reference=False,
            library_enabled=True,model=result['model'],reasoning_effort=result['reasoning_effort'],
            limits=result['limits'],bank_version=result['bank_version'],required_removals=16,
            actions=result['actions'],replay_audit='PASS',learning_updates=0,
            native_engine_health='NO_NATIVE_WARNINGS_RECORDED',native_warning_count=0,
            warning_free_goal_reached=True,source_scope='추가학습 CAD 실제 실행 · 최종 A/B/C 테스트 제외')
        path=DEST/'episode.json';sim.dump_demo(path,title='ASAP 05459 · 17부품 중 16개 제거 · 4GiB 추가학습',summary=summary)
        episode=read(path)
        from disassembly_docskills_v1.post_replay import annotate
        tagged={**result,'_path':result_path,'_episode_parent':DEST}
        annotate(episode,tagged,result['recovery_state']['events'],extra)
        episode.update(assembly_display_name='ASAP 05459 · 추가학습',
            reference_sequence=dict(steps=[{k:a[k] for k in ['part_id','direction']} for a in result['actions']],
                local_verified=True,unique=False,optimality_proven=False,after_development_run=True),
            document_application_plans=[dict(call=d['call'],plan=d.get('document_plan',[])) for d in result['decisions'] if d.get('document_plan')])
        for part in episode['parts']:
            source=(path.parent/part['mesh_url']).resolve();digest=sha(source)
            target=ROOT/'replay/development/meshes'/(digest+'.obj');target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copy2(source,target)
            assert sha(target)==digest
            part['mesh_url']=os.path.relpath(target,DEST)
        write(path,episode);write(DEST/'audit.json',audit,exclusive=True)
        assert sha(result_path)==before,'Original scored/training result changed'
        write(ROOT/'analysis/development_preview_capture.json',dict(status='CAPTURED_PENDING_NATIVE_LOG_CHECK',utc=utc(),
            original_result_sha256=before,episode_sha256=sha(path),frames=len(episode['frames']),
            physical_queries_replayed=audit['physical_queries_replayed'],restores_verified=audit['restores_verified'],
            no_model_calls=True,no_actor_or_budget_change=True,native_capture_locked_before_scored_episodes=True))


def package():
    log=ROOT/'outputs/development_preview.log';health=inspect_log(log)
    assert health['warning_free_observed'],health
    episode=read(DEST/'episode.json');audit=read(DEST/'audit.json');assert audit['status']=='PASS'
    from .post_replay import viewer
    viewer()
    html=(ROOT/'viewer/index.html').read_text().replace('새 제품의 첫 budgeted episode · 평가 중 학습 없음','추가학습 실행 · 최종 A/B/C 테스트 제외')
    html=html.replace('평가 후 다시 검증했습니다. 평가 LLM에 미리 제공하지 않았습니다.','개발 실행 후 다시 검증했습니다. 이 순서를 정답으로 미리 제공하지 않았습니다.')
    html=html.replace('./viewer.js?rev=final-document-v4','./development.js?rev=4gib-preview-1')
    (ROOT/'viewer/development.html').write_text(html)
    js=(ROOT/'viewer/viewer.js').read_text().replace("fetch('../replay/index.json'","fetch('../replay/development/index.json'")
    js=re.sub(r"names=\{[^;\n]+\};","names={C:'C · Graph·LLM 순위·DFS / 4GiB 추가학습'};",js,count=1)
    js=js.replace("+' · 실제 첫 실행'","+' · 추가학습 실행'")
    js=js.replace('평가 중 갱신 0회','실행 중 문서 갱신 0회')
    (ROOT/'viewer/development.js').write_text(js)
    url='../replay/development/asap_05459/C/episode.json'
    row=dict(case_id='asap_05459',arm='C',label='C · 4GiB 추가학습',url=url,summary=episode['summary'])
    catalog=dict(status='PASS',episodes=[row],references=[],default_url=url,scope='Development only;not a held-out final score')
    write(ROOT/'replay/development/index.json',catalog)
    target=ROOT/'development_demo';target.mkdir(exist_ok=True)
    shutil.copytree(ROOT/'viewer',target/'viewer',dirs_exist_ok=True)
    ep=clean({k:v for k,v in episode.items() if k in SAFE_KEYS})
    destination=target/'replay/development/asap_05459/C/episode.json.gz'
    for part,original in zip(ep['parts'],episode['parts']):
        source=(DEST/original['mesh_url']).resolve();digest=sha(source)
        mesh=target/'replay/meshes'/(digest+'.obj');mesh.parent.mkdir(parents=True,exist_ok=True)
        if not mesh.exists():shutil.copy2(source,mesh)
        assert sha(mesh)==digest and mesh.stat().st_size<4_000_000
        part['mesh_url']=os.path.relpath(mesh,destination.parent)
    payload=json.dumps(ep,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    assert '/Users/' not in payload.decode()
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(gzip.compress(payload,mtime=0))
    assert len(destination.read_bytes())<4_000_000 and gzip.decompress(destination.read_bytes())==payload
    publicrow={**row,'url':'../replay/development/asap_05459/C/episode.json.gz','summary':clean(row['summary'])}
    write(target/'replay/development/index.json',{**catalog,'episodes':[publicrow],'default_url':publicrow['url']})
    license_path=WORKSPACE/'disassembly_real_v3/vendor/ASAP/LICENSE'
    if license_path.exists():shutil.copy2(license_path,target/'ASAP_LICENSE.txt')
    (target/'README.md').write_text('''# 05459 development replay

This is the actual4GiBadditional TRAINING episode,not a held-out A/B/C result or proof of library benefit.17original parts,one permanent fixture,16stable removals.26physical queries and every failed query are included. No planner or model was rerun for this viewer. All finished API events were independently revalidated with nativeMuJoCo;rendering usesThree.js.

Run `python3 -m http.server 8786 --bind 127.0.0.1` from this directory,then open http://127.0.0.1:8786/viewer/development.html . Use play,first failure,end,and the timeline. Colors identify parts;gray is the external-fixture assumption. The shown sequence is observed and revalidated,not unique or optimal. Kinematic straight extraction and residual gravity/contact/friction are distinct;no robot/screw/real reassembly is simulated.

Includes only normalized visual meshes and compressed saved frames/events. No source archives,auth,model prompts/CLIlogs or native environment. Original CAD rights remain with their sources. ASAP:https://github.com/yunshengtian/ASAP . Original dataset:https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/training_assembly.zip . Preserve upstream/vendor notices;the software license does not grant new rights over third-partyCAD.
''')
    files=[p for p in target.rglob('*') if p.is_file()];total=sum(p.stat().st_size for p in files)
    assert total<=50*1024**2
    receipt=dict(status='READY',utc=utc(),case_id='asap_05459',development_only=True,
        final_test_results_not_included=True,frames=len(episode['frames']),physical_queries=26,removals=16,
        native_capture_health=health,total_bytes=total,assets={str(p.relative_to(target)):sha(p) for p in files})
    write(ROOT/'analysis/development_preview_bundle.json',receipt)
    port=8785
    with socket.socket() as s:available=s.connect_ex(('127.0.0.1',port))!=0
    if available:
        with (ROOT/'outputs/replay_server.log').open('ab') as f:
            p=subprocess.Popen([sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1','--directory',str(ROOT)],stdout=f,stderr=f,start_new_session=True)
        write(ROOT/'outputs/replay_server.json',dict(pid=p.pid,url=f'http://127.0.0.1:{port}/viewer/development.html',utc=utc()))
    print(json.dumps(dict(status='READY',url=f'http://127.0.0.1:{port}/viewer/development.html?episode={url}',frames=len(episode['frames']),bytes=total)))


if __name__=='__main__':
    capture() if sys.argv[-1]=='capture' else package()

"""A clearly separate development gravity-failure diagnostic, after scoring.

The real rejected query is re-executed. Its hypothetical remainder is displayed
separately from the accepted planner state. No new model call or scored outcome.
"""
import copy
import os
from pathlib import Path
import shutil
from .common import ROOT,WORKSPACE,read,write,sha,utc,progress
from .evidence_replay import equal
from disassembly_real_v3.simulator import FullDisassemblySim

def main():
    assert (ROOT/'outputs/evaluation/complete.json').exists(),'No offline native diagnostic may overlap timed episodes'
    folder=ROOT/'replay/diagnostic/development_support_failure';folder.mkdir(parents=True,exist_ok=True)
    if (folder/'audit.json').exists():
        assert read(folder/'audit.json')['status']=='PASS';return
    original_case=WORKSPACE/'disassembly_real_v3/cases/fresh_01/asap_00749.json'
    origin=WORKSPACE/'disassembly_real_v3/outputs/supplementary/trials/asap_00749/normal/repeat_01/B_code_with_library/result.json'
    original=read(origin);witness=next(t for t in original['trace'] if t['reason']=='unstable_remainder' and t['remaining_before']==original['initial_observation']['remaining_part_ids']) if 'remaining_part_ids' in original['initial_observation'] else next(t for t in original['trace'] if t['reason']=='unstable_remainder')
    assert witness['remaining_before']==[p['id'] for p in read(original_case)['parts']],'Use the actual unmodified root-state failure'
    data=copy.deepcopy(read(original_case));assets=ROOT/'data/development_diagnostic/asap_00749';assets.mkdir(parents=True,exist_ok=True)
    copied={}
    for part in data['parts']:
        for field in ['visual_mesh','collision_meshes']:
            names=part[field] if isinstance(part[field],list) else [part[field]]
            replacements=[]
            for name in names:
                source=(original_case.parent/name).resolve();target=assets/'assets'/part['id']/source.name;target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():shutil.copy2(source,target)
                assert sha(source)==sha(target);copied[str(target.relative_to(ROOT))]=sha(target)
                replacements.append(os.path.relpath(target,assets))
            part[field]=replacements if isinstance(part[field],list) else replacements[0]
    cp=assets/'case.json';write(cp,data)
    sim=FullDisassemblySim(cp,max_checks=1,capture=True)
    result=sim.check(witness['part_id'],witness['direction']);assert result['reason']=='unstable_remainder'
    for field in ['valid','reason','blockers','stability']:equal(witness[field],result[field],field)
    sim.frames=[];sim.clock=0.;sim._record_frame('개발 진단 · 가상 제거 전 원래 상태')
    remainder=[p for p in sim.remaining if p!=witness['part_id']]
    stability,_=sim.settle(remainder,sim.poses,capture=True);equal(result['stability'],stability,'rejected native stability')
    summary=dict(diagnostic=True,development_only=True,reference=False,condition='diagnostic',success=False,
        title='개발 사례의 거절된 내부 검사',required_removals=len(sim.parts)-1,final_removed=0,
        checks=1,failed_checks=1,restores=0,llm_calls=0,termination='unstable_remainder',library_enabled=False,
        stability=stability,source_query=witness['checker_call'],candidate=dict(part_id=witness['part_id'],direction=witness['direction']),
        explanation='후보를 임시로 제외한 잔류 중력 검사입니다. 불안정하여 실제 planner 상태에는 제거가 반영되지 않았습니다. 새 CAD 평가나 성공률에 포함하지 않습니다.')
    source_query=folder/'source_query.json';write(source_query,dict(source_result_sha256=sha(origin),query=witness))
    ep=folder/'episode.json';sim.dump_demo(ep,title='개발 사례 · 거절된 지지 부품 제거의 중력 진단',summary=summary)
    episode=read(ep);episode.update(case_id='development_asap_00749',condition='diagnostic',events=[],
        physics_scope='평가 외 개발 진단 · 실제 거절된 MuJoCo 잔류 검사 재실행 · 승인 상태/성공률 변경 없음',
        document_reads=[],document_application_claims=[],reference_sequence={},
        actual_source=dict(result_url='source_query.json',result_sha256=sha(source_query)),
        diagnostic_source=dict(origin=str(origin),origin_sha256=sha(origin),original_case_sha256=sha(original_case),copied_case_sha256=sha(cp)))
    write(ep,episode)
    audit=dict(status='PASS',created_utc=utc(),development_only=True,not_primary_evaluation=True,
        no_model_calls=True,source_original_query=witness['checker_call'],source_result_sha256=sha(origin),
        identical_rejected_stability_feedback=True,diagnostic_case=str(cp),diagnostic_case_sha256=sha(cp),copied_assets=copied,
        frozen_fixture_note='Gray original part is permanently world-fixed; dynamic parts integrate gravity.')
    write(folder/'audit.json',audit,exclusive=True)
    index_path=ROOT/'replay/index.json';index=read(index_path);index['diagnostics']=[dict(label='개발 사례 · 거절된 중력 검사',url=os.path.relpath(ep,ROOT/'viewer'))];write(index_path,index)
    progress('development_gravity_diagnostic_ready',not_primary_result=True)

if __name__=='__main__':main()

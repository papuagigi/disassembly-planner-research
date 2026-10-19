"""Operator-only pre-score source-count amendment;frozen actors stay unchanged."""
import argparse
import os
import signal
import subprocess
import time
from .common import ROOT,read,write,sha,utc,progress
from .protocol import verify

def processes():
    rows={}
    raw=subprocess.check_output(['ps','-axo','pid=,ppid=,pgid=,state=,command='],text=True)
    for line in raw.splitlines():
        p=line.strip().split(None,4)
        if len(p)==5:rows[int(p[0])]=dict(pid=int(p[0]),ppid=int(p[1]),pgid=int(p[2]),state=p[3],command=p[4])
    return rows

def main(pid,target):
    frozen=verify();pool=read(ROOT/'outputs/input_audit/pools.json')
    assert pool['minimum_evaluation_CADs']<=target<=frozen['evaluation_target']
    assert '-m disassembly_docskills_v3.pipeline' in processes()[pid]['command']
    assert read(ROOT/'outputs/pipeline_state.json')['phase']=='heldout_input_preparation'
    assert not list((ROOT/'outputs/evaluation/trials').glob('*/*/job.json'))
    final=ROOT/'outputs/input_audit/selected_evaluation.json'
    assert not final.exists()
    os.kill(pid,signal.SIGSTOP)
    try:
        assert read(ROOT/'outputs/pipeline_state.json')['phase']=='heldout_input_preparation'
        assert not list((ROOT/'outputs/evaluation/trials').glob('*/*/job.json'))
        original=ROOT/'outputs/input_audit/progress_evaluation.json';snapshot=read(original)
        assert len(snapshot['cases'])>=target
        cases=snapshot['cases'][:target]
        assert all(c['required_removals']>=10 and c['source_split']=='test_assembly' for c in cases)
        assert len({c['geometry_fingerprint'] for c in cases})==target
        cut=next(i+1 for i,r in enumerate(snapshot['statuses']) if r['id']==cases[-1]['source_assembly_id'])
        amendment=dict(status='PROSPECTIVE_BEFORE_ANY_SCORED_EPISODE',utc=utc(),
            user_minimum=pool['minimum_evaluation_CADs'],original_operational_maximum=frozen['evaluation_target'],effective_test_target=target,
            reason='Input conversion cost exceeded the operational estimate;use the completed fixed-order prefix above the user minimum,without examining any actor outcomes.',
            source_order_unchanged=True,model_bank_actors_physics_API_and_episode_caps_unchanged=True,
            scored_jobs_before_amendment=0,test_model_calls_before_amendment=0,
            original_frozen_protocol_sha256=sha(ROOT/'outputs/protocol/freeze.json'),
            source_progress_sha256=sha(original),selected_case_ids=[c['case_id'] for c in cases])
        write(ROOT/'outputs/protocol/evaluation_cohort_amendment.json',amendment,exclusive=True)
        rows=processes();owned={pid}
        while True:
            expanded=owned|{p for p,r in rows.items() if r['ppid'] in owned}
            if expanded==owned:break
            owned=expanded
        groups={rows[p]['pgid'] for p in owned if p in rows}
        safe_groups={g for g in groups if {p for p,r in rows.items() if r['pgid']==g}<=owned}
        for group in sorted(safe_groups,key=lambda g:g==rows[pid]['pgid']):
            try:os.killpg(group,signal.SIGTERM)
            except ProcessLookupError:pass
        for p in owned:
            if p not in rows or rows[p]['pgid'] in safe_groups:continue
            try:os.kill(p,signal.SIGTERM)
            except ProcessLookupError:pass
        try:os.kill(pid,signal.SIGCONT)
        except ProcessLookupError:pass
        for _ in range(50):
            live=processes()
            remaining=[p for p in owned if p in live and not live[p]['state'].startswith('Z')]
            if not remaining:break
            time.sleep(.1)
        assert not remaining,('Owned preparation processes remain',remaining)
        source_ids={r['id'] for r in snapshot['statuses'][:cut]};unused=[];cancelled=[]
        for folder in sorted((ROOT/'outputs/input_audit/evaluation').iterdir()):
            if not folder.is_dir() or folder.name in source_ids:continue
            qp=folder/'qualification.json'
            if qp.exists():unused.append(dict(id=folder.name,status=read(qp)['status_record']['status'],used_for_selection=False))
            elif (folder/'heartbeat.json').exists():cancelled.append(dict(id=folder.name,reason='operator stopped unused preparation after prospective cohort finalization',partial_files_preserved=True))
        value=dict(status='FINITE_COHORT_COMPLETE',utc=utc(),cases=cases,statuses=snapshot['statuses'][:cut],
            attempted=cut,source_candidates=len(pool['evaluation_candidates']),requested_cases_max=frozen['evaluation_target'],
            effective_test_target=target,source_pool_exhausted=False,selection=pool['selection'],no_actor_or_reference_search=True,
            prospective_amendment='outputs/protocol/evaluation_cohort_amendment.json',
            additional_prepared_receipts_unused_for_selection=unused,cancelled_unused_preparation=cancelled)
        write(final,value,exclusive=True)
        write(ROOT/'outputs/protocol/pre_score_selector_stop.json',dict(utc=utc(),root_pid=pid,
            reason='Operator finalized test cohort before scoring;not an unexplained crash',
            stopped_owned_processes=[rows[p] for p in sorted(owned) if p in rows],
            no_scored_episode_interrupted=True,unused_partial_inputs_preserved=True),exclusive=True)
        verify()
        progress('test_cohort_fixed_before_scoring',qualified=target,minimum=pool['minimum_evaluation_CADs'])
        print(dict(status='TEST_COHORT_FIXED_BEFORE_SCORING',test_CADs=target,planned_episodes=target*3,frozen_hashes_unchanged=True),flush=True)
    except BaseException:
        try:os.kill(pid,signal.SIGCONT)
        except ProcessLookupError:pass
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True);p.add_argument('--target',type=int,required=True)
    a=p.parse_args();main(a.pid,a.target)

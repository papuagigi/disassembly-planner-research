"""Append-only, first-encounter full-disassembly evaluation on source CAD."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from .common import ROOT, WORKSPACE, MODEL, EFFORT, LIMITS, CONDITIONS, read, write, digest, prepare as prepare_input, solve, neutral_observation_hash
from .memory import SkillBank


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def progress(phase, **details):
    entry = dict(phase=phase, owner='Codex', claude_assigned=False,
                 updated_utc=datetime.now(timezone.utc).isoformat(), **details)
    write(ROOT/'outputs/progress.json', entry)
    with (ROOT/'outputs/journal.jsonl').open('a') as stream:
        stream.write(json.dumps(entry, ensure_ascii=False)+'\n')


def sources():
    old = read(WORKSPACE/'disassembly_abc_v4/outputs/protocol/freeze.json')['source_sha256']
    own = list(ROOT.glob('*.py')) + list((ROOT/'data_tools').glob('*.py'))
    return sorted(set([Path(p) for p in old] + own), key=str)


def input_dependencies(selection):
    """Bind geometry and physical certification before actor/source freeze."""
    paths=set()
    for key in ['source_catalog_path','conversion_config_path','case_selection_path']:
        if selection.get(key):paths.add(Path(selection[key]).resolve())
    for row in selection['cases']:
        case_path=Path(row['case_path']).resolve()
        assert sha(case_path)==row['case_sha256'], ('Selected case bytes changed',case_path)
        paths.add(case_path)
        case=read(case_path)
        for part in case['parts']:
            paths.add((case_path.parent/part['visual_mesh']).resolve())
            paths.update((case_path.parent/p).resolve() for p in part['collision_meshes'])
        for key in ['initial_validity_path','conversion_path']:
            paths.add(Path(row[key]).resolve())
    # Original source bytes and their provenance/quality receipts remain auditable.
    for directory in ['data/source','outputs/input_audit']:
        paths.update(p.resolve() for p in (ROOT/directory).rglob('*')
                     if p.is_file() and p.suffix not in ['.partial','.log'])
    return {str(p):sha(p) for p in sorted(paths,key=str)}


def verify_pre_source_freeze():
    path=ROOT/'outputs/protocol/before_fresh_source_freeze.json'
    value=read(path)
    assert value['status']=='FROZEN_BEFORE_SOURCE_FETCH'
    assert set(value['source_sha256'])=={str(p.resolve()) for p in sources()}
    for name,expected in value['source_sha256'].items():
        assert sha(name)==expected, ('Code changed after pre-source freeze',name)
    assert sha(ROOT/'memory/S5.json')==value['bank_file_sha256']
    assert sha(value['physical_protocol_path'])==value['physical_protocol_sha256']
    return value


def freeze():
    out = ROOT/'outputs/protocol/freeze.json'
    if out.exists():
        raise FileExistsError('Do not replace the frozen protocol')
    pre_source=verify_pre_source_freeze()
    gate = read(ROOT/'outputs/task_validation/final.json')
    assert gate['status'] == 'PASS'
    for name, expected in gate['source_sha256'].items():
        assert sha(ROOT/name) == expected, ('Task adapter changed after tests', name)
    selection = read(ROOT/'outputs/input_audit/selected_cases.json')
    assert selection['cases'] and all(c['accepted'] for c in selection['cases'])
    assert selection['all_selected_valid']
    review=read(ROOT/'outputs/protocol/input_review.json')
    assert review['status']=='PASS' and review['selected_cases_sha256']==sha(ROOT/'outputs/input_audit/selected_cases.json')
    assert review['actual_case_count']==len(selection['cases'])
    assert review['planned_case_count']==review['actual_case_count'] or review['input_shortfall_acknowledged']
    assert len({c['source_assembly_id'] for c in selection['cases']}) == len(selection['cases'])
    dependencies=input_dependencies(selection)
    catalog_path=Path(selection['source_catalog_path']).resolve()
    assert sha(catalog_path)==selection['source_catalog_sha256']
    catalog=read(catalog_path)
    declared_ids=catalog['declared_reserve_ids']
    assert catalog['fresh_source_role']=='heldout_after_generic_rule_freeze'
    assert catalog['pre_source_freeze_sha256']==sha(ROOT/'outputs/protocol/before_fresh_source_freeze.json')
    assert not set(declared_ids).intersection(pre_source['forbidden_source_ids'])
    assert all(c['source_assembly_id'] in declared_ids for c in selection['cases'])
    bank = ROOT/'memory/S5.json'
    origin = WORKSPACE/'disassembly_abc_v4/memory/S5.json'
    assert sha(bank) == sha(origin) == sha(ROOT/'outputs/protocol/library.json')
    assert not list((ROOT/'outputs/evaluation').glob('trials/**/started.json'))
    value = dict(
        created_utc=datetime.now(timezone.utc).isoformat(), model=MODEL, reasoning_effort=EFFORT,
        pre_source_freeze_file_sha256=sha(ROOT/'outputs/protocol/before_fresh_source_freeze.json'),
        physical_protocol_path=pre_source['physical_protocol_path'],
        physical_protocol_sha256=pre_source['physical_protocol_sha256'],
        task='full_disassembly', goal='A collision/stability-accepted sequence leaving exactly one original component; n-1 removals on the retained success path.',
        reference_methods=[
            'https://github.com/yunshengtian/ASAP/blob/3727e716b57e0b508c4e9ecd9fefa6953e8f72da/plan_sequence/planner/base.py',
            'https://arxiv.org/html/2309.16909v2', 'https://assembly.csail.mit.edu/'],
        conditions=list(CONDITIONS), limits=LIMITS,
        skill_stage_limits={'opcodes':150000,'wall_seconds':0.3},
        planned_cases=len(selection['cases']), planned_trials=3*len(selection['cases']),
        declared_source_count=len(declared_ids),declared_source_ids=declared_ids,
        input_coverage_policy='Report valid-input coverage and conditional planner success, plus end-to-end successes divided by all declared source products. Preparation exclusions are common pipeline failures, not unobserved planner trials; missing actor costs/progress remain null.',
        tracks=['normal'], track_repetitions={'normal':1},
        source_sha256={str(p.resolve()):sha(p) for p in sources()},
        task_validation_sha256=sha(ROOT/'outputs/task_validation/final.json'),
        selected_cases_sha256=sha(ROOT/'outputs/input_audit/selected_cases.json'),
        source_catalog_path=str(catalog_path),source_catalog_sha256=sha(catalog_path),
        input_review_sha256=sha(ROOT/'outputs/protocol/input_review.json'),
        input_dependency_sha256=dependencies,
        banks={'S5':dict(path=str(bank.resolve()),file_sha256=sha(bank),bank_sha256=SkillBank(bank).sha256)},
        bank_origin=dict(path=str(origin.resolve()),file_sha256=sha(origin),
                         same_exact_source_and_bank_for_B_C=True,
                         learning_origin='Prior failure-driven self-designed development assemblies; not claimed as ASAP training-set learning.'),
        library_snapshot_sha256=sha(ROOT/'outputs/protocol/library.json'),
        condition_contract={
            CONDITIONS[0]:'Generated restricted Python owns search and API dispatch, without a reusable bank.',
            CONDITIONS[1]:'Generated restricted Python may retrieve/call S5 and owns API dispatch.',
            CONDITIONS[2]:'Fixed Graph/DFS invokes the same S5; LLM may resolve genuine uncovered semantic ties after deterministic recovery.'},
        comparison='A-B measures library access as a system change; B-C changes control ownership/filtering/activation/ranking together, not one isolated causal factor.',
        first_encounter='One complete-budget episode per source product and arm. No repeated practice, seeded error or cross-product state/bank transfer during evaluation.',
        within_episode='Feedback, temporary search ledgers, checkpoints, backtracking and code repair within the common caps are allowed.',
        memory_policy='Frozen S5; no model-weight or bank updates. Each arm gets fresh provider context and an empty episode ledger.',
        initial_focus_policy='A deterministic remaining-part focus supports the inherited single-target skill interface. It is the same public observation for all arms and never defines task success or supplies a feasible order.',
        preparation='Root checkpoint only. No target probes, forced mistakes, preparatory removals or seeded condition. Offline CAD preparation/certification costs are reported separately.',
        fairness='Same original CAD, normalized assembled geometry, physical settings, fixture, initial state/observation/checkpoints, API, model/effort and resource upper bounds. Realized costs may differ.',
        accounting='Policy/controller and executable skill opcodes are counted, not equal FLOPs. Physical actions/queries charge each directed attempt. Preparation/asset conversion, validation and replay are offline; episode time begins after shared input preparation.',
        sampling='Documented source-only semantic/geometry cohort and fixed reserve order plus initial-model validity gates; all amendments precede actor outcomes.',
        exclusions='Every conversion/initial-model failure and unattempted reserve is retained. A failed reference or planner search is not an invalid CAD and cannot trigger replacement.',
        failure_policy='Keep every scheduled outcome, including code/provider/budget failures. No score-driven reruns, source edits, bank additions or case replacement.',
        novelty_scope='Project-specific unused original assembly IDs and recorded geometry checks; no claim to know foundation-model pretraining exposure.',
        physical_scope='Original public research CAD meshes; uniform assumed scale/material values; six-axis kinematic extraction and MuJoCo residual gravity/friction stability. No force-driven extraction, fastener torque, dynamic holding, per-step reorientation or robot execution.',
        limitations='Full task endpoint follows prior planners; simulator/action/support assumptions and evaluation cost units differ from ASAP, so scores are not an ASAP reproduction or manufacturer validation.',
        neutral_outcome='No desired winning condition. All-zero success and absent LLM/skill invocation are valid observed results; report partial progress and evidence limits.',
        additional_learning='New source-CAD failure-derived skills require separate development data and a later untouched test set; not silently trained on these test episodes.')
    value['manifest_sha256'] = digest(value)
    write(out, value)
    for path in sources():
        target = ROOT/'outputs/protocol/source_snapshot'/path.relative_to(WORKSPACE)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    progress('frozen_before_evaluation', planned_trials=value['planned_trials'],freeze_file_sha256=sha(out))
    print(json.dumps({'freeze_sha256':sha(out),'source_files':len(sources()),'planned_trials':value['planned_trials']}),flush=True)


def verify_frozen():
    value = read(ROOT/'outputs/protocol/freeze.json')
    assert digest({k:v for k,v in value.items() if k!='manifest_sha256'}) == value['manifest_sha256']
    verify_pre_source_freeze()
    assert sha(ROOT/'outputs/protocol/before_fresh_source_freeze.json')==value['pre_source_freeze_file_sha256']
    for name, expected in value['source_sha256'].items():
        assert sha(name) == expected, ('Frozen source changed',name)
    for name, field in [('outputs/task_validation/final.json','task_validation_sha256'),
                        ('outputs/input_audit/selected_cases.json','selected_cases_sha256'),
                        ('outputs/protocol/input_review.json','input_review_sha256'),
                        ('outputs/protocol/library.json','library_snapshot_sha256')]:
        assert sha(ROOT/name) == value[field], ('Frozen protocol dependency changed',name)
    assert sha(value['source_catalog_path'])==value['source_catalog_sha256']
    for name,expected in value['input_dependency_sha256'].items():
        assert sha(name)==expected, ('Frozen input/certification changed',name)
    assert sha(value['bank_origin']['path']) == value['bank_origin']['file_sha256']
    for bank in value['banks'].values():
        assert sha(bank['path']) == bank['file_sha256']
        assert SkillBank(bank['path']).sha256 == bank['bank_sha256']
    return value


def prepare():
    frozen = verify_frozen(); out = ROOT/'outputs/evaluation/manifest.json'
    if out.exists():
        raise FileExistsError('Shared inputs already prepared')
    cases=[]; assets={}
    for row in read(ROOT/'outputs/input_audit/selected_cases.json')['cases']:
        path=Path(row['case_path']).resolve(); case=read(path); paths={path}
        for part in case['parts']:
            paths.add((path.parent/part['visual_mesh']).resolve())
            paths.update((path.parent/p).resolve() for p in part['collision_meshes'])
        assets.update({str(p):sha(p) for p in paths})
        shared=prepare_input(row)
        dst=ROOT/'outputs/evaluation/shared_inputs'/row['case_id']/'normal.json'
        write(dst,shared)
        tracks={'normal':dict(path=str(dst.resolve()),sha256=sha(dst),
                             observation_sha256=neutral_observation_hash(shared['observation']),
                             preparation_checks=shared['state']['checks'],preparation_seconds=shared['preparation_seconds'])}
        cases.append({**row,'case_path':str(path),'tracks':tracks,
                      'reference':{'minimum_removals':None,'reference_length':None,'scope':'No solved path or optimality oracle used for case selection.'}})
    value={**frozen,'cases':cases,'asset_sha256':assets,'freeze_file_sha256':sha(ROOT/'outputs/protocol/freeze.json'),
           'runtime':{name:importlib.metadata.version(name) for name in ['mujoco','numpy','scipy','trimesh']}}
    value.pop('manifest_sha256');value['manifest_sha256']=digest(value);write(out,value)
    progress('prepared_for_independent_audit',cases=len(cases),planned_trials=3*len(cases))
    print(json.dumps({'cases':len(cases),'trials':3*len(cases),'manifest_sha256':value['manifest_sha256']}),flush=True)


def manifest():
    verify_frozen(); value=read(ROOT/'outputs/evaluation/manifest.json')
    assert digest({k:v for k,v in value.items() if k!='manifest_sha256'})==value['manifest_sha256']
    for name,expected in value['asset_sha256'].items():
        assert sha(name)==expected, ('Frozen asset changed',name)
    for case in value['cases']:
        for track in case['tracks'].values():
            assert sha(track['path'])==track['sha256']
    return value


def worker(case_index, condition):
    from disassembly_mujoco.agent import CodexCLIProvider
    value=manifest(); case=value['cases'][case_index]
    folder=ROOT/'outputs/evaluation/trials'/case['case_id']/'normal/repeat_01'/condition
    if (folder/'started.json').exists():
        raise FileExistsError('This product/condition has already started')
    write(folder/'started.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),condition=condition))
    shared=read(case['tracks']['normal']['path'])
    provider=CodexCLIProvider(folder/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    started=time.monotonic()
    result=solve(case,condition,provider,shared,bank_path=value['banks']['S5']['path'])
    result.update(case_id=case['case_id'],case_path=case['case_path'],condition=condition,method=condition,
        track='normal',repeat=1,source_assembly_id=case['source_assembly_id'],model=MODEL,reasoning_effort=EFFORT,
        limits=LIMITS,protocol_sha256=value['manifest_sha256'],goal_type='full_disassembly',
        first_encounter=True,preparation_checks=shared['state']['checks'],
        preparation_seconds=shared['preparation_seconds'],elapsed_seconds_total=time.monotonic()-started,
        expected_initial_observation_sha256=neutral_observation_hash(shared['observation']),
        library_available=condition!=CONDITIONS[0],bank_version='S5' if condition!=CONDITIONS[0] else None,
        bank_sha256=value['banks']['S5']['bank_sha256'] if condition!=CONDITIONS[0] else None)
    write(folder/'result.json',result)
    print(json.dumps({k:result.get(k) for k in ['case_id','condition','success','termination','completed_removals','required_removals','checker_calls','llm_calls','elapsed_seconds_total']}),flush=True)


def evaluate():
    value=manifest();schedule=[]
    audit=read(ROOT/'outputs/protocol/pre_evaluation_audit.json')
    assert audit['status']=='PASS' and audit['manifest_sha256']==value['manifest_sha256']
    for i,case in enumerate(value['cases']):
        offset=i%len(CONDITIONS)
        for condition in CONDITIONS[offset:]+CONDITIONS[:offset]:
            schedule.append(dict(ordinal=len(schedule)+1,case_index=i,condition=condition,track='normal',repeat=1))
    sp=ROOT/'outputs/evaluation/schedule.json'
    if sp.exists(): assert read(sp)==schedule
    else:write(sp,schedule)
    for job in schedule:
        case=value['cases'][job['case_index']]
        folder=ROOT/'outputs/evaluation/trials'/case['case_id']/'normal/repeat_01'/job['condition']
        if (folder/'result.json').exists():continue
        if (folder/'started.json').exists():raise RuntimeError('Interrupted episode needs an explicit retained-outcome audit: '+str(folder))
        folder.mkdir(parents=True,exist_ok=True)
        command=[sys.executable,'-B','-m','disassembly_real_v1.study','worker','--case-index',str(job['case_index']),'--condition',job['condition']]
        started=time.monotonic();process=subprocess.Popen(command,cwd=WORKSPACE,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        timed_out=False
        try:stdout,stderr=process.communicate(timeout=LIMITS['timeout_seconds']+15)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate()
        (folder/'worker.stdout').write_text(stdout);(folder/'worker.stderr').write_text(stderr)
        if stdout.strip():print(stdout.strip(),flush=True)
        if not (folder/'result.json').exists():
            write(folder/'result.json',dict(case_id=case['case_id'],case_path=case['case_path'],source_assembly_id=case['source_assembly_id'],
                condition=job['condition'],method=job['condition'],track='normal',repeat=1,goal_type='full_disassembly',first_encounter=True,
                model=MODEL,reasoning_effort=EFFORT,limits=LIMITS,protocol_sha256=value['manifest_sha256'],success=False,
                termination='outer_wall_budget_exhausted' if timed_out else 'worker_error',error=stderr[-3000:],trace=[],actions=[],
                checker_calls=None,llm_calls=len(list((folder/'llm_calls').glob('call_*'))),
                preparation_checks=0,elapsed_seconds_total=time.monotonic()-started,
                physical_evidence_available=False,library_available=job['condition']!=CONDITIONS[0],
                bank_version='S5' if job['condition']!=CONDITIONS[0] else None,
                bank_sha256=value['banks']['S5']['bank_sha256'] if job['condition']!=CONDITIONS[0] else None))
        progress('evaluation',completed=job['ordinal'],expected=len(schedule),latest_result=str(folder/'result.json'))
    manifest();write(ROOT/'outputs/evaluation/complete.json',dict(trials=len(schedule),source_verification='PASS'))
    progress('evaluation_complete',completed=len(schedule),expected=len(schedule),next='Exact MuJoCo replay, source/ledger audit and descriptive analysis')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['freeze','prepare','worker','evaluate'])
    parser.add_argument('--case-index',type=int);parser.add_argument('--condition',choices=CONDITIONS)
    args=parser.parse_args()
    if args.command=='freeze':freeze()
    elif args.command=='prepare':prepare()
    elif args.command=='evaluate':evaluate()
    else:worker(args.case_index,args.condition)

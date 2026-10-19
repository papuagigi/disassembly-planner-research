"""Pre-execution input/fairness gate. No model or physical action is called."""
import json
from pathlib import Path

from .common import ROOT,MODEL,EFFORT,LIMITS,CONDITIONS,read,write,neutral_observation_hash
from .study import manifest,sha


def run():
    value=manifest()
    assert value['model']==MODEL and value['reasoning_effort']==EFFORT
    assert value['limits']==LIMITS
    assert value['conditions']==list(CONDITIONS)
    assert value['task']=='full_disassembly'
    assert value['tracks']==['normal'] and value['track_repetitions']=={'normal':1}
    assert value['planned_trials']==3*len(value['cases'])
    assert not list((ROOT/'outputs/evaluation/trials').glob('**/started.json'))
    assert not list((ROOT/'outputs/evaluation/trials').glob('**/result.json'))
    assert sha(ROOT/'memory/S5.json')==sha(ROOT/'outputs/protocol/library.json')
    gate=read(ROOT/'outputs/task_validation/final.json')
    assert gate['status']=='PASS'
    rows=[]
    for case in value['cases']:
        source=read(case['case_path'])
        shared=read(case['tracks']['normal']['path'])
        state=shared['state'];obs=shared['observation'];recovery=shared['recovery_state']
        ids={part['id'] for part in source['parts']}
        fixtures=sorted(part['id'] for part in source['parts'] if part.get('fixed'))
        n=len(ids)
        assert n>1 and len(fixtures)<=1
        assert fixtures==sorted(case['fixture_ids'])
        assert set(state['remaining'])==ids
        assert state['actions']==[] and state['trace']==[] and state['checks']==0
        assert shared['preparation_checks']==0
        assert obs['goal_type']=='full_disassembly' and not obs['goal_reached']
        assert obs['total_part_count']==n and obs['remaining_part_count']==n
        assert obs['required_removals']==n-1 and obs['completed_removals']==0
        assert obs['target_id']==source['target_id'] and not obs['initial_focus_removed']
        assert neutral_observation_hash(obs)==case['tracks']['normal']['observation_sha256']
        assert recovery['restore_count']==0
        events=recovery['events']
        assert len(events)==1 and events[0]['operation']=='checkpoint'
        assert len(recovery['checkpoints'])==1
        certification=read(case['initial_validity_path'])
        assert certification['status']=='physical_valid'
        assert certification['selected']['candidate_protocol_complete'] is True
        assert certification['selected']['case_sha256']==sha(case['case_path'])
        rows.append(dict(case_id=case['case_id'],source_assembly_id=case['source_assembly_id'],
                         n=n,required_removals=n-1,fixtures=fixtures,
                         shared_observation_sha256=neutral_observation_hash(obs),
                         root_checkpoint_only=True,preparation_checks=0))
    report=dict(status='PASS',manifest_sha256=value['manifest_sha256'],
                model=MODEL,reasoning_effort=EFFORT,limits=LIMITS,
                cases=rows,planned_trials=3*len(rows),
                physical_queries=0,model_calls=0,
                full_goal_and_shared_input_verified=True,
                frozen_source_file_count=len(value['source_sha256']),
                frozen_input_dependency_count=len(value['input_dependency_sha256']),
                same_bank_B_C=True,claude_assigned=False)
    write(ROOT/'outputs/protocol/pre_evaluation_audit.json',report)
    print(json.dumps({k:report[k] for k in ['status','planned_trials','physical_queries','model_calls']}))


if __name__=='__main__':run()

"""Fixed-order long-horizon role assignment, without policy-result selection."""
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from pathlib import Path
from .common import ROOT,WORKSPACE,read,write,sha,progress
from .dataset import pools
from .preparation import run_one
from .capacity import probe

def resolved_case(case):
    case=dict(case)
    for key in ['case_path','shared_path','source_inventory_path']:
        p=Path(case[key]);case[key]=str(p if p.is_absolute() else WORKSPACE/p)
    return case

def select(stage):
    target=16 if stage=='development' else 10
    final=ROOT/'outputs/input_audit'/('selected_'+stage+'.json')
    if final.exists():return read(final)
    pool=pools();reused=[];seen=set(pool.get('prior_geometry_fingerprints',[]))
    if stage=='development':
        for raw in pool['reused_discovery_cases']:
            c=resolved_case(raw)
            if not Path(c['case_path']).exists():c=run_one(stage,c['source_assembly_id'])['case']
            assert c and sha(c['case_path'])==c['case_sha256']
            assert probe(c)['eligible'],'Reused development input fails initial actor-capacity check;no new model calls permitted'
            reused.append(c);seen.add(c['geometry_fingerprint'])
    else:
        from .protocol import verify
        verify()
        for c in read(ROOT/'outputs/input_audit/selected_development.json')['cases']:seen.add(c['geometry_fingerprint'])
    prior=read(ROOT/'outputs/input_audit/previous_geometry_fingerprints.json')
    seen.update(r['fingerprint'] for r in prior['records'])
    selected=[];statuses=[]
    rows=pool[stage+'_candidates'];cursor=next_submit=0;ready={};surplus=[]
    def prepare(row):
        result=run_one(stage,row['id'])
        if result.get('case'):result={**result,'capacity':probe(result['case'])}
        return result
    with ThreadPoolExecutor(max_workers=2) as ex:
        active={}
        def submit():
            nonlocal next_submit
            while len(active)<2 and next_submit<len(rows) and next_submit-cursor<8 and len(selected)<target:
                active[ex.submit(prepare,rows[next_submit])]=next_submit;next_submit+=1
        submit()
        while active:
            done,_=wait(active,timeout=30,return_when=FIRST_COMPLETED)
            for f in done:ready[active.pop(f)]=f.result()
            while cursor in ready and len(selected)<target:
                result=ready.pop(cursor);cursor+=1
                c=result.get('case');status=dict(result['status_record']);sig=result.get('geometry_fingerprint')
                if c:
                    capacity=result['capacity'];status['initial_actor_capacity']=capacity
                    if not capacity['eligible']:status['status']='initial_actor_capacity_excluded';c=None
                if sig in seen:status['status']='duplicate_geometry_excluded';c=None
                if sig:seen.add(sig)
                statuses.append(status)
                if c and len(selected)<target:
                    assert (11<=c['part_count']<=20) if stage=='development' else c['part_count']>=11
                    selected.append(c)
                write(ROOT/'outputs/input_audit'/('progress_'+stage+'.json'),dict(cases=selected,statuses=statuses))
            progress('preparing_'+stage,qualified=len(selected),target=target,attempted=len(statuses),
                active_ids=[rows[i]['id'] for i in active.values()],completed_out_of_order=len(ready))
            submit()
        surplus=[dict(id=rows[i]['id'],status=r['status_record']['status'],selected=False) for i,r in sorted(ready.items())]
    if len(selected)<target:raise RuntimeError(f'Finite {stage} reserve exhausted: {len(selected)}/{target};do not relax input criteria')
    value=dict(status='FINITE_COHORT_COMPLETE',cases=reused+selected,statuses=statuses,attempted=len(statuses),
        selection=pool['selection'],source_order_fixed=True,no_policy_result_gate=True,prepared_but_unused=surplus)
    if stage=='development':
        value.update(discovery_cases=reused+selected[:6],validation_cases=selected[6:],reused_discovery_CADs=4,new_discovery_CADs=6)
        assert len(value['discovery_cases'])==10 and len(value['validation_cases'])==10
    write(final,value,exclusive=True);return value

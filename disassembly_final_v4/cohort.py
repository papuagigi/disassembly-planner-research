"""Fixed-order long-horizon role assignment, without policy-result selection."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .common import ROOT,WORKSPACE,read,write,sha,progress
from .dataset import pools
from .preparation import run_one

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
            reused.append(c);seen.add(c['geometry_fingerprint'])
    else:
        from .protocol import verify
        verify()
        for c in read(ROOT/'outputs/input_audit/selected_development.json')['cases']:seen.add(c['geometry_fingerprint'])
    prior=read(ROOT/'outputs/input_audit/previous_geometry_fingerprints.json')
    seen.update(r['fingerprint'] for r in prior['records'])
    selected=[];statuses=[]
    # map yields in source order. Prefetched extra receipts are preserved,never
    # selected by completion speed; no actor is run during this stage.
    rows=pool[stage+'_candidates']
    with ThreadPoolExecutor(max_workers=2) as ex:
        cursor=0
        while len(selected)<target and cursor<len(rows):
            batch=rows[cursor:cursor+2];cursor+=len(batch)
            for result in ex.map(lambda r:run_one(stage,r['id']),batch):
                c=result.get('case');status=dict(result['status_record']);sig=result.get('geometry_fingerprint')
                if sig in seen:status['status']='duplicate_geometry_excluded';c=None
                if sig:seen.add(sig)
                statuses.append(status)
                if c and len(selected)<target:
                    assert (11<=c['part_count']<=20) if stage=='development' else c['part_count']>=11
                    selected.append(c)
                write(ROOT/'outputs/input_audit'/('progress_'+stage+'.json'),dict(cases=selected,statuses=statuses))
                progress('preparing_'+stage,qualified=len(selected),target=target,attempted=len(statuses))
    if len(selected)<target:raise RuntimeError(f'Finite {stage} reserve exhausted: {len(selected)}/{target};do not relax input criteria')
    value=dict(status='FINITE_COHORT_COMPLETE',cases=reused+selected,statuses=statuses,attempted=len(statuses),
        selection=pool['selection'],source_order_fixed=True,no_policy_result_gate=True)
    if stage=='development':
        value.update(discovery_cases=reused+selected[:6],validation_cases=selected[6:],reused_discovery_CADs=4,new_discovery_CADs=6)
        assert len(value['discovery_cases'])==10 and len(value['validation_cases'])==10
    write(final,value,exclusive=True);return value

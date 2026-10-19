"""Keep native setup/qualification failures outside planner-outcome metrics."""
from collections import Counter
from .common import ROOT,read,write,sha,utc

def main():
    stages={}
    for stage in ['development','evaluation']:
        selected_path=ROOT/'outputs/input_audit'/('selected_'+stage+'.json')
        selected=read(selected_path) if selected_path.exists() else {}
        rows=[]
        for path in sorted((ROOT/'outputs/input_audit'/stage).glob('*/qualification.json')):
            value=read(path);status=value['status_record'];details=status.get('details',{})
            rows.append(dict(id=path.parent.name,status=status['status'],elapsed_seconds=status['elapsed_seconds'],
                in_selected_cohort=any(c['source_assembly_id']==path.parent.name for c in selected.get('cases',[])),
                selected_initial_native_health=details.get('selected_initial_native_health'),
                error=details.get('error'),source_path=str(path.relative_to(ROOT)),source_sha256=sha(path)))
        stages[stage]=dict(completed_source_preparations=len(rows),
            ordered_candidates_consumed=selected.get('attempted'),selected_CADs=len(selected.get('cases',[])),
            source_preparation_statuses=dict(Counter(r['status'] for r in rows)),receipts=rows)
    report=dict(utc=utc(),stages=stages,scope='All completed preparation receipts include unused prefetch. Ordered selection and final scored denominators are separate. No setup/native-capacity exclusion proves physical impossibility or planner failure.')
    write(ROOT/'analysis/input_preparation_diagnosis.json',report)
    return report

"""Outcome definitions fixed before any final evaluated geometry is fetched."""
from collections import Counter

def summarize(result):
    trace=result.get('trace',[]);events=result.get('recovery_state',{}).get('events',[])
    failures=[t for t in trace if not t.get('valid')];seen=set();repeated=repeat_rejected=0;bad=set()
    for t in trace:
        key=(t.get('physical_state_key_before'),t.get('part_id'),t.get('direction'))
        repeated+=key in seen;repeat_rejected+=key in bad;seen.add(key)
        if not t.get('valid'):bad.add(key)
    required=result.get('required_removals',1);final=result.get('completed_removals',0)
    accepted=sum(bool(t.get('committed')) for t in trace)
    best=max([final]+[result.get('total_part_count',required+1)-len(t.get('remaining_after',[])) for t in trace])
    claimed=[sid for d in result.get('decisions',[]) for sid in d.get('claimed_application_ids',[])]
    return dict(success=bool(result.get('success')),termination=result.get('termination'),
        final_removed=final,required_removed=required,final_progress=final/max(1,required),best_removed=best,
        checks=result.get('checker_calls',0),failed_checks=len(failures),failure_causes=dict(Counter(t.get('reason') for t in failures)),
        duplicate_queries=repeated,duplicate_rejected_queries=repeat_rejected,
        accepted_removals=accepted,undone_accepted_removals=max(0,accepted-final),
        restores=result.get('recovery_state',{}).get('restore_count',0),
        checkpoint_count=len(result.get('recovery_state',{}).get('checkpoints',{})),
        llm_calls=result.get('llm_calls',0),tokens=result.get('token_usage',{}),elapsed_seconds=result.get('elapsed_seconds',0),
        instructions=result.get('execution_steps',0),path_samples=sum(t.get('path_samples',0) for t in trace),
        dynamic_steps=sum(t.get('physics_steps',0) for t in trace),document_reads=len(result.get('document_reads',[])),
        claimed_skill_ids=sorted(set(claimed)),read_skill_ids=sorted({r['skill_id'] for r in result.get('document_reads',[])}),
        application_evidence_scope='Read bytes and model declarations are recorded separately; trace invariants are tested separately, not inferred from declarations.')

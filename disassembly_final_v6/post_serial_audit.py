"""Verify observed planner process windows and actual4GiBjob contracts."""
from datetime import datetime
from .common import ROOT,read,write,utc
from .contracts import LIMITS,DEV_LIMITS


def main():
    rows=[];missing=[]
    for group in ['development/memory_extension','development/full_validation','evaluation/trials']:
        for p in sorted((ROOT/'outputs'/group).rglob('job.json')):
            folder=p.parent;job=read(p)
            expected=DEV_LIMITS if group.endswith('memory_extension') else LIMITS
            assert job['limits']==expected,(str(p),'Unexpected new job budget')
            start=folder/'lifecycle_started.json';end=folder/'lifecycle_final.json'
            if not start.exists() or not end.exists():
                missing.append(str(folder.relative_to(ROOT)));continue
            a=read(start);b=read(end)
            rows.append(dict(job=str(p.relative_to(ROOT)),phase=job['phase'],arm=job['arm'],
                pid=a['pid'],started_utc=a['utc'],finished_utc=b['utc'],
                rss_cap_bytes=job['limits']['max_rss_bytes']))
    assert not missing,('Missing planner lifecycle evidence',missing)
    rows.sort(key=lambda r:r['started_utc'])
    for left,right in zip(rows,rows[1:]):
        assert datetime.fromisoformat(right['started_utc'])>=datetime.fromisoformat(left['finished_utc']),('Planner overlap',left,right)
    assert len(rows)==17,('Expected2development+3validation+12final jobs',len(rows))
    value=dict(status='PASS',utc=utc(),new_planner_episodes=len(rows),observed_max_concurrent_planners=1,
        all_new_jobs_4GiB=True,episodes=rows,
        scope='Planner worker lifecycle windows only;input preparation and post-score native replay are not planner invocations.')
    write(ROOT/'analysis/serial_execution_audit.json',value)
    return value

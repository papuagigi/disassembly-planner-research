"""Input-only exact-actor initialization check;zero model/physical-query calls."""
from pathlib import Path
import json
import os
import subprocess
import sys
from .common import ROOT,read,write,sha,utc
from .contracts import LIMITS

MARGIN=32*1024*1024

def probe(case):
    folder=ROOT/'outputs/input_audit/capacity';folder.mkdir(parents=True,exist_ok=True)
    p=folder/(case['case_id']+'.json')
    if p.exists():
        value=read(p);assert value['case_sha256']==sha(case['case_path']) and value['shared_sha256']==sha(case['shared_path']);return value
    command=[sys.executable,'-B','-m','disassembly_final_v6.capacity','worker',case['case_path'],case['shared_path']]
    value=dict(utc=utc(),case_id=case['case_id'],case_sha256=sha(case['case_path']),shared_sha256=sha(case['shared_path']),
        eligible=False,model_calls=0,physical_queries=0,episode_cap_bytes=LIMITS['max_rss_bytes'],preflight_margin_bytes=MARGIN)
    try:
        completed=subprocess.run(command,text=True,capture_output=True,timeout=50,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        report=json.loads(completed.stdout.splitlines()[-1]);assert report['model_calls']==0 and report['physical_queries']==0
        value.update(report,worker_returncode=completed.returncode)
    except Exception as e:value['error']=repr(e)
    write(p,value,exclusive=True);return value

def worker(case_path,shared_path):
    from .actors import solve
    limits={**LIMITS,'max_calls':0,'timeout_seconds':30.,'max_rss_bytes':LIMITS['max_rss_bytes']-MARGIN}
    result=solve(case_path,None,ROOT/'memory/S0.json','code',shared=read(shared_path),limits=limits)
    report=dict(eligible=result.get('error') is None and result['max_rss_bytes_observed']<=limits['max_rss_bytes'],
        peak_rss_bytes=result['max_rss_bytes_observed'],error=result.get('error'),model_calls=result['llm_calls'],physical_queries=result['checker_calls'])
    print(json.dumps(report),flush=True)

if __name__=='__main__':worker(sys.argv[2],sys.argv[3])

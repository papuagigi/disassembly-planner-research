"""Small read-only progress snapshot for agents;avoid loading whole raw logs."""
import argparse
import json
from .common import ROOT,read

def main(after=0):
    paths=sorted((ROOT/'outputs/evaluation/trials').glob('*/*/result.json'),key=lambda p:p.stat().st_mtime_ns)
    fresh=[]
    for p in paths[after:]:
        r=read(p)
        fresh.append(dict(case=p.parent.parent.name,arm=p.parent.name,
            **{k:r.get(k) for k in ['success','completed_removals','required_removals','checker_calls','llm_calls','elapsed_seconds','termination']}))
    value=dict(progress=read(ROOT/'outputs/progress.json'),finished=len(paths),fresh=fresh)
    print(json.dumps(value,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--after',type=int,default=0);main(p.parse_args().after)

"""Protect previous research bytes; no writes outside this new study."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
from .common import ROOT, WORKSPACE, sha, utc, write

SKIP = {'.git', '__pycache__', '.venv', 'node_modules', '.upstream_venv',
        '.upstream_build', '.collision_deps', '.conversion_deps', '.deps'}
BASELINE = ROOT/'outputs/preservation/baseline.json.gz'

def files():
    for folder in sorted(WORKSPACE.glob('disassembly*')):
        if not folder.is_dir() or folder == ROOT:
            continue
        for parent, dirs, names in os.walk(folder, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in SKIP and not (Path(parent)/d).is_symlink())
            for name in sorted(names):
                path=Path(parent)/name
                if not path.is_symlink() and path.suffix != '.pyc':
                    yield path

def initial():
    assert not BASELINE.exists(), 'Never replace a prior-research baseline'
    rows={}
    for path in files():
        log=path.suffix=='.log' and any(x in path.name.lower() for x in ('server','http'))
        rows[str(path.resolve())]=dict(sha256=sha(path),bytes=path.stat().st_size,
            mode='preserve_prefix' if log else 'exact')
    value=dict(created_utc=utc(),scope='Previous disassembly study source/data/results/documents; dependency environments, native builds, .git and bytecode excluded',
        excluded_directory_names=sorted(SKIP),files=rows)
    BASELINE.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(BASELINE,'xt') as f:json.dump(value,f,ensure_ascii=False)
    write(BASELINE.with_suffix('.receipt.json'),dict(status='BASELINED',files=len(rows),baseline_sha256=sha(BASELINE),created_utc=utc()))
    print({'status':'BASELINED','files':len(rows)})

def audit():
    with gzip.open(BASELINE,'rt') as f:value=json.load(f)
    changed=[];missing=[];append_only=[]
    for name,row in value['files'].items():
        path=Path(name)
        if not path.exists():missing.append(name);continue
        if row['mode']=='preserve_prefix':
            with path.open('rb') as f:actual=hashlib.sha256(f.read(row['bytes'])).hexdigest()
            if actual!=row['sha256'] or path.stat().st_size<row['bytes']:changed.append(name)
            elif path.stat().st_size!=row['bytes']:append_only.append(name)
        elif sha(path)!=row['sha256']:changed.append(name)
    result=dict(status='PASS' if not changed and not missing else 'FAIL',utc=utc(),
        prior_files=len(value['files']),changed=changed,missing=missing,
        preserved_server_log_prefixes_with_new_requests=append_only,baseline_sha256=sha(BASELINE))
    write(ROOT/'outputs/preservation/audit.json',result)
    print({k:v for k,v in result.items() if k!='preserved_server_log_prefixes_with_new_requests'})
    assert result['status']=='PASS'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['baseline','audit']);a=p.parse_args()
    initial() if a.operation=='baseline' else audit()

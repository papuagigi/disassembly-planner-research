"""Copy audited conversion code and choose a metadata-only finite reserve.

This must precede any final geometry download. Copied code writes only new roots.
"""
import re
import shutil
from collections import defaultdict
from .common import ROOT, WORKSPACE, read, write, sha, utc

def main():
    old=WORKSPACE/'disassembly_real_v3'
    target=ROOT/'data_tools';target.mkdir(exist_ok=True)
    origins=[]
    for name in ['__init__.py','convert_cad.py','inventory_sources.py','range_zip.py']:
        source=old/'data_tools'/name
        if not source.exists() and name=='__init__.py':
            (target/name).touch(); continue
        shutil.copy2(source,target/name)
        origins.append(dict(path=str(source),sha256=sha(source),new_path=str((target/name).relative_to(ROOT))))
    source=ROOT/'data/source';source.mkdir(parents=True,exist_ok=True)
    for name in ['training_zip_central.bin','training_zip_tail.bin']:
        shutil.copy2(old/'data/source'/name,source/name)
    # Dependency directories remain read-only. No pip operation follows these links.
    for name in ['.deps','.collision_deps','.conversion_deps']:
        link=ROOT/name
        if not link.exists(): link.symlink_to((old/name).resolve(),target_is_directory=True)
    write(ROOT/'references/copied_conversion.json',dict(created_utc=utc(),sources=origins,adaptation='namespace only; settings frozen separately before final geometry'))
    excluded=set(read(old/'outputs/protocol/before_fresh_source_freeze.json')['forbidden_source_ids'])
    for project in WORKSPACE.glob('disassembly*'):
        if not project.is_dir() or project==ROOT: continue
        for folder in (project/'data/source').glob('*'):
            if folder.is_dir():
                excluded.update(p.name for p in folder.iterdir() if p.is_dir() and re.fullmatch(r'\d{5}',p.name))
                if re.fullmatch(r'\d{5}',folder.name):excluded.add(folder.name)
        cases=project/'cases'
        if cases.exists():
            for cp in cases.rglob('asap_*.json'):
                excluded.update(re.findall(r'asap_(\d{5})',cp.stem))
    from .data_tools.range_zip import index
    groups=defaultdict(list)
    for info in index().infolist():
        match=re.fullmatch(r'training_assembly/(\d{5})/[^/]+\.obj',info.filename)
        if match:groups[match[1]].append(info)
    rows=[]
    for aid, infos in sorted(groups.items()):
        size=sum(i.file_size for i in infos)
        if aid>'00825' and aid not in excluded and 5<=len(infos)<=10 and 100000<=size<=1000000:
            rows.append(dict(id=aid,part_count=len(infos),obj_bytes=size))
        if len(rows)==20:break
    assert len(rows)==20
    request=dict(created_utc=utc(),stage='METADATA_ONLY_BEFORE_GEOMETRY',ids=[r['id'] for r in rows],rows=rows,
        rule='first20 ascending IDs >00825,5–10 original OBJ components,100k–1M OBJ bytes,all prior exposed CAD excluded',
        excluded_ids=sorted(excluded),geometry_downloaded=False,central_sha256=sha(source/'training_zip_central.bin'))
    write(ROOT/'outputs/input_audit/reserve.json',request,exclusive=True)
    print(request['rows'],flush=True)

if __name__=='__main__':main()

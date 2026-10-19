"""Official archive inventory, explicit product split and checked local extraction."""
from __future__ import annotations
from collections import defaultdict
import json
from pathlib import Path
import shutil
import zipfile
from .common import ROOT,WORKSPACE,read,write,sha,utc

TRAIN_URL='https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/training_assembly.zip'
TEST_URL='https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/test_assembly.zip'

def groups(z):
    result=defaultdict(list)
    for i in z.infolist():
        if i.filename.endswith('.obj'):result[Path(i.filename).parent.name].append(i)
    return result

def pools():
    path=ROOT/'outputs/input_audit/pools.json'
    if path.exists():return read(path)
    prior=read(ROOT/'protocol/prior_sources.json')
    previous=set(prior['prior_geometry_ids'])
    with zipfile.ZipFile(ROOT/'data/source/training_assembly.zip') as z: training=groups(z)
    with zipfile.ZipFile(ROOT/'data/source/test_assembly.zip') as z:test=groups(z)
    def reserve(source,maximum):
        rows=sorted([dict(id=k,part_count=len(v),obj_bytes=sum(x.file_size for x in v)) for k,v in source.items() if k not in previous and 11<=len(v)<=20],key=lambda r:(r['obj_bytes'],r['part_count'],r['id']))
        bins=[[r for r in rows if r['part_count']<=15],[r for r in rows if r['part_count']>=16]];out=[]
        while any(bins):
            for group in bins:
                if group:out.append(group.pop(0))
        return out[:maximum]
    reused=prior['reused_discovery_cases']
    assert len(reused)==4
    result=dict(created_utc=utc(),development_candidates=reserve(training,150),evaluation_candidates=reserve(test,100),
        reused_discovery_cases=reused,development_target=16,discovery_target=6,validation_target=10,evaluation_target=10,
        minimum_discovery_CADs=10,minimum_validation_CADs=10,minimum_evaluation_CADs=10,preparation_concurrency=2,
        prior_opened_ids=sorted(previous),selection='Alternating11-15/16-20 source metadata bins; initial physics only; preserve all failures',
        discovery_assignment='4 previous discovery CADs plus first6new qualified inputs; next10new inputs are independent validation',
        previous_discovery_CADs=90,prior_geometry_fingerprints=prior.get('prior_opened_shape_fingerprints',[]),part_count_range=[11,20],all_earlier_geometry_IDs_excluded_from_new_reserves=True)
    write(path,result,exclusive=True);return result

def finalize_download():
    receipt=ROOT/'outputs/input_audit/archive_inventory.json'
    if receipt.exists():return read(receipt)
    target=ROOT/'data/source/training_assembly.zip';partial=target.with_suffix('.zip.partial')
    if not target.exists():
        assert partial.stat().st_size==618781705,'Official training ZIP download is incomplete'
        with zipfile.ZipFile(partial) as z:assert z.testzip() is None
        partial.rename(target)
    records=[]
    for split,filename,url,expected in [('training','training_assembly.zip',TRAIN_URL,1906),('test','test_assembly.zip',TEST_URL,240)]:
        p=ROOT/'data/source'/filename
        with zipfile.ZipFile(p) as z:
            assert z.testzip() is None
            g=groups(z);assert len(g)==expected
        records.append(dict(split=split,url=url,path=str(p),bytes=p.stat().st_size,sha256=sha(p),
            CADs=len(g),OBJ_components=sum(map(len,g.values())),all_member_CRCs_verified=True))
    assert records[1]['sha256']=='c89ea240b1962e3230b00487bf23f3fcbb8b5cd7b6ce1a6816e043a31cac09c2'
    result=dict(utc=utc(),status='ALL_OFFICIAL_ARCHIVE_BYTES_AVAILABLE_AND_CRC_VERIFIED',archives=records,
        learned_CAD_count_not_equal_to_downloaded_count=True)
    write(receipt,result,exclusive=True);return result

def extract(split,aid):
    assert split in ('training','test') and aid.isdigit() and len(aid)==5
    folder=ROOT/'data/source'/('asap_'+split)/aid
    receipt=folder/'source_receipt.json'
    if receipt.exists():
        old=read(receipt)
        for m in old['members']:assert sha(ROOT/m['path'])==m['sha256']
        return old
    folder.mkdir(parents=True,exist_ok=True)
    archive=ROOT/'data/source'/(split+'_assembly.zip');members=[]
    with zipfile.ZipFile(archive) as z:
        infos=[i for i in z.infolist() if Path(i.filename).parent.name==aid and not i.is_dir()]
        assert infos
        for info in infos:
            assert Path(info.filename).suffix in ('.obj','.json')
            payload=z.read(info);p=folder/Path(info.filename).name
            if p.exists():assert p.read_bytes()==payload
            else:
                tmp=p.with_suffix(p.suffix+'.partial');tmp.write_bytes(payload);tmp.replace(p)
            members.append(dict(member=info.filename,path=str(p.relative_to(ROOT)),sha256=sha(p),
                bytes=len(payload),zip_crc32=info.CRC))
    result=dict(source_assembly_id=aid,split=split,url=TRAIN_URL if split=='training' else TEST_URL,
        archive_path=str(archive),archive_sha256=next(r['sha256'] for r in read(ROOT/'outputs/input_audit/archive_inventory.json')['archives'] if r['split']==split),
        members=members,created_utc=utc())
    write(receipt,result,exclusive=True);return result

if __name__=='__main__':
    import sys
    result=finalize_download() if sys.argv[-1]=='finalize' else pools()
    print(json.dumps({k:v for k,v in result.items() if k not in ('development_candidates','evaluation_candidates','previous_extracted_product_ids')},ensure_ascii=False),flush=True)

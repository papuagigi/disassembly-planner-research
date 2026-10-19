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
    from .data_tools.range_zip import index
    previous=set(read(ROOT/'outputs/input_audit/previous_geometry_use.json'))
    previous.update(['00749','01275','00804'])
    training=groups(index())
    with zipfile.ZipFile(ROOT/'data/source/test_assembly.zip') as z:test=groups(z)
    assert not set(training)&set(test)
    def rows(g,minimum):
        return sorted([dict(id=a,part_count=len(v),obj_bytes=sum(i.file_size for i in v))
            for a,v in g.items() if a not in previous and len(v)>=minimum],
            key=lambda r:(r['obj_bytes'],r['part_count'],r['id']))
    training_rows=rows(training,3);evaluation=rows(test,11)
    # Size diversity is declared before collecting failure labels. Each size bin
    # retains metadata-only source-byte order; no policy outcome chooses inputs.
    bins={
        'small':[r for r in training_rows if r['part_count']<=5],
        'medium':[r for r in training_rows if 6<=r['part_count']<=10],
        'large':[r for r in training_rows if r['part_count']>=11]}
    schedule=('small','small','small','medium','medium','large');dev=[]
    while any(bins.values()):
        for size in schedule:
            if bins[size]:dev.append(bins[size].pop(0))
    result=dict(created_utc=utc(),training_archive_CADs=len(training),test_archive_CADs=len(test),
        previous_extracted_product_ids=sorted(previous),development_candidates=dev,
        evaluation_candidates=evaluation,development_target=102,discovery_target=90,validation_target=12,
        evaluation_target=15,minimum_discovery_CADs=80,minimum_validation_CADs=10,minimum_evaluation_CADs=10,preparation_concurrency=4,
        selection='Development: 3/2/1 round-robin of 3-5/6-10/11+ part bins; each bin ascending source OBJ bytes,part count,ID. Evaluation: 11+ parts ascending source OBJ bytes,part count,ID. Initial physics only;no full-path or policy-result gate.',
        no_training_test_product_overlap=True,no_evaluation_OBJ_opened_for_pool_selection=True,
        archived_source_training_OBJ_count=sum(map(len,training.values())),
        archived_source_test_OBJ_count=sum(map(len,test.values())),
        sufficient_for_full_benchmark_claim=False,
        evaluation_scope='New-to-project subset of official ASAP test archive under a different local physics/motion setup;not ASAP numerical reproduction.')
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

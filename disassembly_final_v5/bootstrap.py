"""Portable setup: public source archives, checksums and checked configuration."""
import argparse
import shutil
import urllib.request
from .common import ROOT,read,write,sha,utc

ARCHIVES=[('training_assembly.zip','https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/training_assembly.zip','0f21fa9642877c69078b5489bb6a86db3a5e786024cc2fdd19dfb25384a64968',1906),
          ('test_assembly.zip','https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/test_assembly.zip','c89ea240b1962e3230b00487bf23f3fcbb8b5cd7b6ce1a6816e043a31cac09c2',240)]

def configure():
    for filename in ['conversion_development.json','conversion_evaluation.json']:
        p=ROOT/'outputs/protocol'/filename;source=ROOT/'config'/filename
        if not p.exists() and source.exists():p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,p)
    p=ROOT/'outputs/input_audit/previous_geometry_fingerprints.json'
    if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'config/previous_geometry_fingerprints.json',p)

def download():
    configure();rows=[]
    for filename,url,expected,count in ARCHIVES:
        p=ROOT/'data/source'/filename;p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():
            tmp=p.with_suffix('.zip.partial')
            with urllib.request.urlopen(url,timeout=60) as src,tmp.open('wb') as dst:shutil.copyfileobj(src,dst)
            assert sha(tmp)==expected,'Archive checksum mismatch';tmp.rename(p)
        assert sha(p)==expected
        rows.append(dict(path=str(p),url=url,sha256=expected,CADs=count,bytes=p.stat().st_size))
    receipt=ROOT/'outputs/input_audit/archive_inventory.json'
    if not receipt.exists():write(receipt,dict(utc=utc(),archives=[{**r,'split':'training' if i==0 else 'test'} for i,r in enumerate(rows)]),exclusive=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--download',action='store_true');a=p.parse_args()
    download() if a.download else configure()

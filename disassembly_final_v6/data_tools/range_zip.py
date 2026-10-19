"""Read original ASAP ZIP members by HTTP range; verify local header and CRC.

Avoids downloading an entire 590 MiB archive to inspect a few new source CADs.
This does not claim a SHA256 for the complete archive. Each original member has
its own SHA256 and ZIP CRC; the ETag, size, central directory and range receipts
bind the remote snapshot that supplied those bytes.
"""
import io
import json
import struct
import hashlib
import zipfile
import zlib
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/source'
URL='https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/training_assembly.zip'
ETAG='"24e1dc09-6171d20708780"'
SIZE=618781705

def sha(data): return hashlib.sha256(data).hexdigest()

def index():
    cd=(SOURCE/'training_zip_central.bin').read_bytes()
    tail=(SOURCE/'training_zip_tail.bin').read_bytes()
    p=tail.rfind(b'PK\x05\x06')
    fields=struct.unpack_from('<4s4H2LH',tail,p)
    assert fields[5]==len(cd) and fields[6]+len(cd)+22==SIZE
    eocd=struct.pack('<4s4H2LH',fields[0],0,0,fields[3],fields[4],len(cd),0,0)
    return zipfile.ZipFile(io.BytesIO(cd+eocd))

def get_range(start,end):
    request=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{end}','If-Match':ETAG})
    with urllib.request.urlopen(request,timeout=60) as response:
        data=response.read()
        assert response.status==206, 'Server did not honor the range request'
        assert response.headers['Content-Range']==f'bytes {start}-{end}/{SIZE}'
        assert response.headers['ETag']==ETAG
    assert len(data)==end-start+1
    return data

def extract_assembly(aid):
    assert aid.isdigit() and len(aid)==5
    z=index()
    members=[i for i in z.infolist() if Path(i.filename).parent.name==aid and not i.is_dir()]
    assert members and all(Path(i.filename).suffix in ('.obj','.json') for i in members)
    last=max(members,key=lambda i:i.header_offset)
    header=get_range(last.header_offset,last.header_offset+29)
    fields=struct.unpack('<4s5H3L2H',header)
    assert fields[0]==b'PK\x03\x04'
    start=min(i.header_offset for i in members)
    end=last.header_offset+30+fields[-2]+fields[-1]+last.compress_size-1
    data=get_range(start,end)
    folder=SOURCE/'asap_training'/aid
    folder.mkdir(parents=True,exist_ok=True)
    receipts=[]
    for info in members:
        pos=info.header_offset-start
        values=struct.unpack_from('<4s5H3L2H',data,pos)
        assert values[0]==b'PK\x03\x04'
        name=data[pos+30:pos+30+values[-2]].decode('utf-8')
        assert name==info.filename
        payload_start=pos+30+values[-2]+values[-1]
        compressed=data[payload_start:payload_start+info.compress_size]
        raw=zlib.decompress(compressed,-15) if info.compress_type==8 else compressed
        assert info.compress_type in (0,8)
        assert len(raw)==info.file_size and zlib.crc32(raw)==info.CRC
        destination=folder/Path(info.filename).name
        if destination.exists(): assert destination.read_bytes()==raw
        else: destination.write_bytes(raw)
        receipts.append(dict(member=info.filename,path=str(destination.relative_to(ROOT)),
                             bytes=len(raw),sha256=sha(raw),zip_crc32=info.CRC,
                             compression=info.compress_type,header_offset=info.header_offset))
    result=dict(source_assembly_id=aid,url=URL,etag=ETAG,remote_archive_bytes=SIZE,
                complete_archive_sha256=None,central_directory_sha256=sha((SOURCE/'training_zip_central.bin').read_bytes()),
                fetched_range=[start,end],fetched_bytes=len(data),fetched_range_sha256=sha(data),
                members=receipts,created_utc=datetime.now(timezone.utc).isoformat())
    receipt=folder/'source_receipt.json'
    if not receipt.exists():receipt.write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    import sys
    for aid in sys.argv[1:]:
        receipt=extract_assembly(aid)
        print(json.dumps(dict(id=aid,files=len(receipt['members']),bytes=receipt['fetched_bytes'])),flush=True)

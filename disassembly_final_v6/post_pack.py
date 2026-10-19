"""Small self-contained public replay;no raw model logs or CAD archives."""
import gzip
import json
import os
from pathlib import Path
import re
import shutil
from .common import ROOT,WORKSPACE,read,write,sha,utc

SAFE_KEYS={'title','parts','target_id','frames','events','summary','schema','case_id','condition',
    'assembly_display_name','reference_sequence','document_reads','document_application_claims',
    'document_application_plans','physics_scope','memory_scope','timeline_scope','replay_scope',
    'planner_start_frame','failure_frames','restore_frames','changed_restore_frames','api_timeline'}

def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,str) and value.startswith(('/Users/','/private/','/tmp/')):
        return '[local path removed]/'+Path(value).name
    return value

def main():
    assert read(ROOT/'replay/audit.json')['status']=='PASS'
    manifest=read(ROOT/'outputs/evaluation/manifest.json');catalog=read(ROOT/'replay/index.json')
    target=ROOT/'public_demo';target.mkdir(exist_ok=True)
    shutil.copytree(ROOT/'viewer',target/'viewer',dirs_exist_ok=True)
    episode_map={};items=[];refs=[];meshes={}
    for row in catalog['episodes']:
        source=(ROOT/'viewer'/row['url']).resolve()
        episode_map[source]=target/'replay/data'/row['case_id']/row['arm']/'episode.json.gz'
    for row in catalog.get('references',[]):
        source=(ROOT/'viewer'/row['url']).resolve()
        episode_map[source]=target/'replay/reference'/row['case_id']/'episode.json.gz'
    for source,destination in episode_map.items():
        original=read(source);episode=clean({k:v for k,v in original.items() if k in SAFE_KEYS})
        for part,raw in zip(episode['parts'],original['parts']):
            mesh=(source.parent/raw['mesh_url']).resolve()
            assert str(mesh) in manifest['asset_sha256'] and sha(mesh)==manifest['asset_sha256'][str(mesh)]
            digest=sha(mesh);export=target/'replay/meshes'/(digest+'.obj');export.parent.mkdir(parents=True,exist_ok=True)
            if not export.exists():shutil.copy2(mesh,export)
            assert export.stat().st_size<4_000_000,'Large replay mesh requires separate delivery'
            meshes[digest]=dict(path=str(export.relative_to(target)),sha256=digest,bytes=export.stat().st_size)
            part['mesh_url']=os.path.relpath(export,destination.parent)
        reference=original.get('reference_sequence',{}).get('episode_url')
        if reference:
            rp=(source.parent/reference).resolve();assert rp in episode_map
            episode['reference_sequence']['episode_url']=os.path.relpath(episode_map[rp],destination.parent)
        payload=json.dumps(episode,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        text=payload.decode();assert '/Users/' not in text and '/private/' not in text
        assert not re.search(r'\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_\-]{20,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----',text)
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(gzip.compress(payload,mtime=0))
        assert gzip.decompress(destination.read_bytes())==payload
        assert destination.stat().st_size<4_000_000,'Large replay JSON requires separate delivery'
    for row in catalog['episodes']:
        source=(ROOT/'viewer'/row['url']).resolve()
        items.append(dict(case_id=row['case_id'],arm=row['arm'],label=row['label'],
            url=os.path.relpath(episode_map[source],target/'viewer'),
            episode_sha256=sha(episode_map[source]),summary=clean(row['summary'])))
    for row in catalog.get('references',[]):
        source=(ROOT/'viewer'/row['url']).resolve()
        refs.append(dict(case_id=row['case_id'],url=os.path.relpath(episode_map[source],target/'viewer'),after_evaluation=True))
    write(target/'replay/index.json',dict(status='PASS',episodes=items,references=refs,default_url=items[0]['url']))
    license_path=WORKSPACE/'disassembly_real_v3/vendor/ASAP/LICENSE'
    if license_path.exists():shutil.copy2(license_path,target/'ASAP_LICENSE.txt')
    (target/'README.md').write_text('''# Portable native replay

This is saved MuJoCo event replay,not a live physical solver or robot controller. All final episodes,including failures/native-warning outcomes,are retained. Raw and warning-free goals are separate. Reference sequences are derived after evaluation from actual successful warning-free episodes;they are not unique optimal answers.

From this directory run `python3 -m http.server 8783 --bind 127.0.0.1`,then open http://127.0.0.1:8783/viewer/index.html . The viewer uses browser gzip decompression. Source CAD archives,native libraries,credentials and model CLI logs are not included.

Selected visual meshes are normalized derivatives of the official ASAP dataset,not CAD designed by this project. Original rights remain with the respective sources. Upstream repository:https://github.com/yunshengtian/ASAP ;dataset:https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/test_assembly.zip . The upstream software MIT notice is included when available;this project does not grant a new license over third-party CAD. Three.js notices remain in viewer/vendor/LICENSE.
''')
    assets=[p for p in target.rglob('*') if p.is_file()];size=sum(p.stat().st_size for p in assets)
    assert size<=50*1024*1024,'Public replay exceeds50MiB allowance;preserve local bundle and report before upload'
    receipt=dict(status='READY',utc=utc(),episodes=len(items),references=len(refs),unique_visual_meshes=len(meshes),
        total_bytes=size,assets={str(p.relative_to(target)):sha(p) for p in assets},
        no_raw_model_logs=True,no_credentials=True,no_source_archives=True,
        raw_episode_scores_unchanged=True,frames_and_event_order_preserved=True)
    write(ROOT/'analysis/public_replay_bundle.json',receipt)
    return receipt

if __name__=='__main__':main()

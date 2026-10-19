import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from disassembly_final_v5 import post_pack
from disassembly_final_v5.common import read,write,sha


class PublicReplayTests(unittest.TestCase):
    def test_public_bundle_keeps_frame_order_and_scores_without_private_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);viewer=root/'viewer';viewer.mkdir();(viewer/'index.html').write_text('test viewer')
            mesh=root/'visual.obj';mesh.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
            rows=[];frames=[dict(time=0,removed=[],poses={}),dict(time=1,removed=['0'],poses={})]
            for arm in ['A','B']:
                ep=root/'replay/data/asap_fixture'/arm/'episode.json'
                ep.parent.mkdir(parents=True,exist_ok=True)
                import os
                body=dict(title='fixture',case_id='asap_fixture',condition=arm,target_id='0',frames=frames,
                    events=[],summary={'success':False,'checks':2,'native_engine_health':'NATIVE_ENGINE_WARNINGS_RECORDED'},
                    parts=[dict(id='0',mesh_url=os.path.relpath(mesh,ep.parent),color=[1,0,0],fixed=False)],
                    actual_source={'result_url':'/Users/private/run/result.json'},provenance={'path':'/Users/private/cad'})
                write(ep,body)
                rows.append(dict(case_id='asap_fixture',arm=arm,label=arm,url=os.path.relpath(ep,viewer),summary=body['summary']))
            write(root/'replay/index.json',dict(episodes=rows,references=[]))
            write(root/'replay/audit.json',{'status':'PASS'})
            write(root/'outputs/evaluation/manifest.json',{'asset_sha256':{str(mesh.resolve()):sha(mesh)}})
            with patch.object(post_pack,'ROOT',root),patch.object(post_pack,'WORKSPACE',root):receipt=post_pack.main()
            self.assertEqual(receipt['unique_visual_meshes'],1)
            self.assertEqual(receipt['episodes'],2)
            for p in (root/'public_demo/replay/data').glob('*/*/episode.json.gz'):
                payload=gzip.decompress(p.read_bytes()).decode();self.assertNotIn('/Users/',payload)
                episode=json.loads(payload)
                self.assertEqual(episode['frames'],frames)
                self.assertEqual(episode['summary']['checks'],2)
                self.assertFalse(episode['summary']['success'])
                self.assertTrue((p.parent/episode['parts'][0]['mesh_url']).exists())

if __name__=='__main__':unittest.main()

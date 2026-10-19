from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from disassembly_final_v5 import protocol
from disassembly_final_v5.common import read,write,sha


class FreezeDestinationTests(unittest.TestCase):
    def test_freeze_writes_separate_receipt_without_overwriting_negative_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);scope=dict(full_discovery_CADs=5,validation_CADs=3,evaluation_CADs=4)
            cases=[dict(case_id='validation'+str(i)) for i in range(3)]
            write(root/'outputs/input_audit/selected_development.json',dict(discovery_cases=[{}]*5,validation_cases=cases))
            collected=[]
            for i in range(5):
                p=root/f'development{i}.json';write(p,{'trace':[{'observed':True}] if i==0 else []})
                collected.append({'result_path':str(p)})
            write(root/'outputs/development/discovery_complete.json',{'cases':collected})
            preserved={}
            for case in cases:
                p=root/'outputs/development/full_validation'/case['case_id']/'result.json'
                write(p,{'trace':[],'success':False,'error':'retained zero-query infrastructure result'})
                preserved[p]=sha(p)
            write(root/'memory/S3.json',{'version':'test','skills':[]})
            (root/'outputs/regressions.log').write_text('OK\n')
            source=root/'watched.py';source.write_text('test source\n')
            with patch.object(protocol,'ROOT',root),patch.object(protocol,'source_paths',return_value=[source]),patch.object(protocol,'study_scope',return_value=scope):
                receipt=protocol.freeze()
                self.assertTrue((root/'outputs/protocol/freeze.json').exists())
                self.assertEqual(receipt['actual_attempted_full_discovery_CADs'],5)
                self.assertEqual(receipt['actual_physically_observed_full_discovery_CADs'],1)
                self.assertEqual(receipt['actual_physically_observed_validation_CADs'],0)
                self.assertEqual(protocol.verify()['minimum_CAD_requirements']['evaluation'],4)
            for p,digest in preserved.items():self.assertEqual(sha(p),digest)

if __name__=='__main__':unittest.main()

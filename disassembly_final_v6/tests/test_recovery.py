import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from disassembly_final_v6.common import write,read,sha
from disassembly_final_v6 import preparation
from disassembly_final_v6 import driver
from disassembly_final_v6.data_tools import convert_cad as c


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name).resolve()

    def test_exclusive_atomic_json_never_replaces_preserved_bytes(self):
        p=self.root/'receipt.json';write(p,{'status':'original'},exclusive=True);digest=sha(p)
        with self.assertRaises(FileExistsError):write(p,{'status':'replacement'},exclusive=True)
        self.assertEqual(sha(p),digest);self.assertEqual(list(self.root.glob('*.partial')),[])

    def test_existing_source_inventory_resumes_instead_of_exclusive_create_error(self):
        folder=self.root/'outputs/input_audit/development/12345';folder.mkdir(parents=True)
        p=folder/'source_inventory.json'
        write(p,dict(parts=[],geometry_eligible=False,assembly_geometry_fingerprint='test-only'))
        before=sha(p)
        with patch.object(preparation,'ROOT',self.root),patch.object(preparation,'configure',return_value=None),patch.object(preparation,'source_record',side_effect=AssertionError('must reuse inventory')):
            outcome=preparation.worker('development','12345')
        self.assertEqual(outcome['status_record']['status'],'source_geometry_excluded')
        self.assertEqual(sha(p),before)

    def test_completed_input_receipt_reused_without_spawning_worker(self):
        p=self.root/'outputs/input_audit/development/12345/qualification.json'
        write(p,dict(status_record={'id':'12345','status':'initial_physics_or_capacity_excluded'},case=None))
        with patch.object(preparation,'ROOT',self.root),patch.object(preparation.subprocess,'run',side_effect=AssertionError('must not repeat completed input')):
            result=preparation.run_one('development','12345')
        self.assertIsNone(result['case'])

    def test_orphan_part_log_archived_before_new_input_attempt(self):
        manifest=self.root/'manifest.json';write(manifest,dict(id='fixture_only',parts=[]))
        folder=self.root/'fixture_only/prepared';folder.mkdir(parents=True)
        (folder/'part_7.log').write_text('interrupted input preparation')
        with patch.object(c,'ROOT',self.root),patch.object(c,'ASSEMBLIES',self.root),patch.object(c.subprocess,'run',return_value=subprocess.CompletedProcess([],1)):
            result=c.prepare_part(manifest,'7')
        self.assertEqual(result['status'],'worker_failed')
        self.assertEqual((folder/'interrupted_attempts/part_7_001.log').read_text(),'interrupted input preparation')
        self.assertNotEqual(result['status'],'preparation_error')

    def test_completed_exact_case_physics_result_reused_without_simulation(self):
        p=self.root/'case.json';case={'id':'test-only'};write(p,case)
        write(p.with_suffix('.physics_result.json'),dict(report={'accepted':True,'status':'accepted'},poses={'test':{}}))
        with patch.object(c.subprocess,'run',side_effect=AssertionError('must not recompute')):
            report,poses=c.timed_physical_trial(case,p)
        self.assertTrue(report['accepted']);self.assertEqual(poses,{'test':{}})
        with self.assertRaises(AssertionError):c.timed_physical_trial({'id':'changed'},p)

    def test_started_first_episode_is_finalized_without_another_execution(self):
        folder=self.root/'trial';folder.mkdir()
        case=self.root/'case.json';shared=self.root/'shared.json'
        write(case,dict(id='test-only',parts=[{},{}]))
        write(shared,dict(state={'checks':0,'trace':[],'actions':[]},recovery_state={},observation={}))
        job=dict(folder=str(folder),case_path=str(case),shared_path=str(shared),architecture='code',bank_path='unused',limits={},arm='B',phase='evaluation',protocol_sha256='unchanged')
        write(folder/'job.json',job)
        write(folder/'progress.json',dict(checker_calls=9,llm_calls=2,completed_removals=1,trace=[],actions=[],success=True))
        with patch.object(driver,'ROOT',self.root),patch.object(driver.subprocess,'Popen',side_effect=AssertionError('Never retry a started episode')):
            result=driver.run(job)
        self.assertEqual(result['checker_calls'],9);self.assertEqual(result['llm_calls'],2)
        self.assertFalse(result['success']);self.assertTrue(result['interrupted_episode_retained_without_retry'])
        self.assertEqual(driver.finalize_interrupted(job),result)

    def test_preparation_completion_speed_does_not_choose_the_cohort(self):
        gate=threading.Event()
        pool=dict(development_target=2,validation_target=0,development_candidates=[dict(id=p) for p in ['first','excluded','third','fourth']],preparation_concurrency=4,selection='fixed metadata order')
        def outcome(stage,aid):
            if aid=='first':self.assertTrue(gate.wait(2))
            if aid=='third':gate.set()
            valid=aid!='excluded'
            return dict(status_record=dict(id=aid,status='qualified' if valid else 'excluded'),
                case=dict(case_id=aid,geometry_fingerprint=aid) if valid else None,geometry_fingerprint=aid)
        with patch.object(preparation,'ROOT',self.root),patch.object(preparation,'pools',return_value=pool),patch.object(preparation,'run_one',side_effect=outcome),patch.object(preparation,'progress'):
            result=preparation.select('development')
        self.assertEqual([c['case_id'] for c in result['cases']],['first','third'])
        self.assertEqual([r['id'] for r in result['statuses']],['first','excluded','third'])


if __name__=='__main__':unittest.main()

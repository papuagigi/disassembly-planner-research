import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from disassembly_final_v4 import final_learning,cohort
from disassembly_final_v4.common import write,read,sha
from disassembly_final_v4.contracts import LIMITS,ARMS
from disassembly_final_v4.scope import DEFAULT_SCOPE

class FinalProtocolTests(unittest.TestCase):
    def test_learning_prompt_includes_late_dead_end_and_restore_context(self):
        trace=[dict(checker_call=i+1,valid=True) for i in range(100)]
        trace[89].update(valid=False,reason='unstable_remainder')
        events=[dict(operation='restore',checks_before=90)]
        selected=final_learning.evidence_indices(trace,events,[])
        self.assertIn(89,selected);self.assertIn(90,selected);self.assertLessEqual(len(selected),24)

    def test_repair_requires_actual_commit_and_not_same_rejected_action(self):
        trace=[dict(checker_call=1,part_id='a',direction='+x',valid=False,reason='path_collision',physical_state_key_before='s'),
               dict(checker_call=2,part_id='a',direction='-x',valid=True,committed=False,physical_state_key_before='s'),
               dict(checker_call=3,part_id='a',direction='+x',valid=False,physical_state_key_before='s')]
        self.assertEqual(final_learning.repairs({'trace':trace}),[])
        trace.append(dict(checker_call=4,part_id='a',direction='-x',valid=True,committed=True,physical_state_key_before='s'))
        self.assertEqual(final_learning.repairs({'trace':trace})[0]['accepted_check'],4)

    def test_instability_repair_requires_changed_geometry_and_original_direction(self):
        bad=dict(checker_call=1,part_id='a',direction='+x',valid=False,reason='unstable_remainder',physical_state_key_before='s')
        other=dict(checker_call=2,part_id='b',direction='+z',valid=True,committed=True,physical_state_key_before='s')
        good=dict(checker_call=3,part_id='a',direction='+x',valid=True,committed=True,physical_state_key_before='t')
        self.assertEqual(len(final_learning.repairs({'trace':[bad,other,good]})),1)
        self.assertEqual(final_learning.repairs({'trace':[bad,{**good,'direction':'-x'}]}),[])
        self.assertEqual(final_learning.repairs({'trace':[bad,good]}),[])

    def test_admission_retains_negative_cases_and_safety_veto(self):
        rows=[dict(passed=i<7,physical_audit='PASS') for i in range(10)]
        self.assertTrue(final_learning.admission_decision(rows)['status'].startswith('ADMITTED'))
        rows[0]['unsafe_fixed_attempt']=True
        self.assertEqual(final_learning.admission_decision(rows)['status'],'REJECTED')
        self.assertEqual(final_learning.admission_decision(rows[:7],minimum=10)['status'],'REJECTED')

    def test_single_started_proposal_is_not_silently_repeated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write(root/'outputs/development/new_document/attempt_started.json',{'started':True})
            with patch.object(final_learning,'ROOT',root):
                with self.assertRaisesRegex(RuntimeError,'single proposal attempt'):final_learning.propose()

    def test_long_budget_keeps_shared_restoration_caps_and_same_bc_bank(self):
        self.assertEqual(LIMITS['timeout_seconds'],900.)
        self.assertEqual(LIMITS['max_checks'],240)
        self.assertEqual(ARMS['B']['bank'],ARMS['C']['bank'])
        self.assertEqual((LIMITS['max_checkpoints'],LIMITS['max_restores']),(128,256))

    def test_role_assignment_respects_original_and_deadline_scopes_without_leakage(self):
        scopes=[DEFAULT_SCOPE,{**DEFAULT_SCOPE,'full_discovery_CADs':5,'new_discovery_CADs':1,'validation_CADs':3,'evaluation_CADs':4}]
        for scope in scopes:
            with self.subTest(scope=scope),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);reused=[]
                for i in range(4):
                    p=root/f'prior{i}.json';write(p,{'test_fixture':i})
                    reused.append(dict(case_id=f'old{i}',case_path=str(p),case_sha256=sha(p),shared_path=str(p),source_inventory_path=str(p),geometry_fingerprint=f'old{i}'))
                target=scope['new_discovery_CADs']+scope['validation_CADs']
                pool=dict(reused_discovery_cases=reused,development_candidates=[dict(id=str(i)) for i in range(target)],selection='test fixed order')
                write(root/'outputs/input_audit/previous_geometry_fingerprints.json',{'records':[]})
                def outcome(stage,row_id):
                    c=dict(case_id=row_id,part_count=11,geometry_fingerprint=row_id)
                    return dict(case=c,geometry_fingerprint=row_id,status_record={'id':row_id,'status':'qualified'})
                with patch.object(cohort,'ROOT',root),patch.object(cohort,'pools',return_value=pool),patch.object(cohort,'run_one',side_effect=outcome),patch.object(cohort,'progress'),patch.object(cohort,'probe',return_value={'eligible':True}),patch.object(cohort,'study_scope',return_value=scope):
                    result=cohort.select('development')
                d={c['case_id'] for c in result['discovery_cases']};v={c['case_id'] for c in result['validation_cases']}
                self.assertEqual((len(d),len(v)),(scope['full_discovery_CADs'],scope['validation_CADs']));self.assertFalse(d&v)
                self.assertEqual(v,{str(i) for i in range(scope['new_discovery_CADs'],target)})

    def test_three_case_validation_still_needs_two_passes_and_all_safety_gates(self):
        rows=[dict(passed=i<2,physical_audit='PASS') for i in range(3)]
        self.assertTrue(final_learning.admission_decision(rows,minimum=3)['status'].startswith('ADMITTED'))
        rows[2]['native_engine_warning_veto']=True
        self.assertEqual(final_learning.admission_decision(rows,minimum=3)['status'],'REJECTED')

if __name__=='__main__':unittest.main()

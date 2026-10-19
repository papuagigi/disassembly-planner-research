import tempfile
from pathlib import Path
import unittest
from disassembly_final_v4.native_health import inspect_log
from disassembly_final_v4.post_native_classify import failure_class
from disassembly_final_v4.final_learning import admission_decision


class NativeHealthTests(unittest.TestCase):
    def test_actual_contact_and_constraint_warnings_are_not_physical_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'worker.log'
            p.write_text('WARNING: Insufficient arena memory for the number of constraints generated. Increase arena memory allocation above 17M bytes. Time = 0.0000.\n\n'
                         'WARNING: Too many contacts. The arena memory is full, increase arena memory allocation.(ncon = 26454) Time = 0.0340.\n')
            report=inspect_log(p)
            self.assertEqual(report['warning_count'],2)
            self.assertFalse(report['warning_free_observed'])
            rows=[dict(passed=True,physical_audit='PASS') for _ in range(10)]
            rows[0]['native_engine_warning_veto']=True
            self.assertEqual(admission_decision(rows)['status'],'REJECTED')

    def test_missing_log_stays_unknown_and_does_not_become_zero_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=inspect_log(Path(tmp)/'absent.log')
            self.assertIsNone(report['warning_count'])
            self.assertFalse(report['warning_free_observed'])

    def test_checker_limit_does_not_hide_solver_resource_failure(self):
        result=dict(success=False,termination='check_budget_exhausted',error=None)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'worker.log';p.write_text('WARNING: Too many contacts. The arena memory is full.\n')
            self.assertEqual(failure_class(result,inspect_log(p),p),'mujoco_resource_failure_or_warning')
            p.write_text('')
            self.assertEqual(failure_class(result,inspect_log(p),p),'planner_check_budget_exhausted')


if __name__=='__main__':unittest.main()

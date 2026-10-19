import tempfile
from pathlib import Path
import unittest
from disassembly_final_v4.native_health import inspect_log
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


if __name__=='__main__':unittest.main()

import unittest
from disassembly_final_v6.learning_evidence import eligibility


class LearningEvidenceTests(unittest.TestCase):
    def test_accepted_only_memory_stop_cannot_teach_failure_repair(self):
        result={'termination':'limit','error':{'type':'LimitError','message':'same 1 GiB resident-memory ceiling exceeded'},
                'trace':[{'reason':'ok','valid':True,'committed':True}]}
        r=eligibility(result,{'warning_free_observed':True},'PASS')
        self.assertFalse(r['usable'])
        self.assertTrue(r['actor_memory_limited'])
        self.assertEqual(r['observed_physical_failure_queries'],0)

    def test_verified_failure_prefix_survives_operational_stop(self):
        result={'termination':'limit','error':{'message':'same 1 GiB resident-memory ceiling exceeded'},
                'trace':[{'reason':'path_collision','valid':False},{'reason':'ok','valid':True}]}
        r=eligibility(result,{'warning_free_observed':True},'PASS_VERIFIED_PREFIX')
        self.assertTrue(r['usable'])
        self.assertEqual(r['observed_physical_failure_queries'],1)

    def test_solver_warning_vetoes_apparent_physical_rejection(self):
        r=eligibility({'trace':[{'reason':'unstable_remainder'}]},
                      {'warning_free_observed':False},'PASS')
        self.assertFalse(r['usable'])

    def test_unverified_events_are_not_admitted_as_evidence(self):
        r=eligibility({'trace':[{'reason':'path_collision'}]},
                      {'warning_free_observed':True},'FAIL')
        self.assertFalse(r['usable'])

    def test_api_errors_are_not_physical_failures(self):
        r=eligibility({'trace':[{'reason':'invalid_arguments'},{'reason':'fixed_part'}]},
                      {'warning_free_observed':True},'PASS')
        self.assertFalse(r['usable'])


if __name__=='__main__':
    unittest.main()

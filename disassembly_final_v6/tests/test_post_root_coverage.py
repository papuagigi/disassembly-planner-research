import unittest
from disassembly_final_v6.post_root_coverage import coverage,DIRECTIONS


class RootCoverageEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.obs={'state_key':'initial','remaining_parts':[{'id':'fixture','fixed':True},{'id':'moving'}]}
        self.bad=[dict(physical_state_key_before='initial',part_id='moving',direction=d,valid=False,reason='path_collision') for d in DIRECTIONS]

    def compute(self,trace,**kw):
        return coverage(self.obs,trace,**({'replay_ok':True,'health_ok':True}|kw))

    def test_complete_verified_physical_rejections_support_only_local_certificate(self):
        self.assertTrue(self.compute(self.bad)['no_admissible_first_action_in_local_finite_API'])

    def test_untried_direction_stays_unknown(self):
        r=self.compute(self.bad[:-1]);self.assertFalse(r['no_admissible_first_action_in_local_finite_API']);self.assertEqual(len(r['missing_pairs']),1)

    def test_contradictory_valid_observation_prevents_certificate(self):
        good={**self.bad[0],'valid':True,'reason':'removed'}
        r=self.compute(self.bad+[good]);self.assertFalse(r['no_admissible_first_action_in_local_finite_API']);self.assertEqual(len(r['conflicting_pairs']),1)

    def test_operational_error_is_not_physical_rejection(self):
        rows=self.bad[:-1]+[{**self.bad[-1],'reason':'budget_exhausted'}]
        self.assertFalse(self.compute(rows)['no_admissible_first_action_in_local_finite_API'])

    def test_native_warning_or_missing_replay_vetoes_certificate(self):
        self.assertFalse(self.compute(self.bad,health_ok=False)['no_admissible_first_action_in_local_finite_API'])
        self.assertFalse(self.compute(self.bad,replay_ok=False)['no_admissible_first_action_in_local_finite_API'])


if __name__=='__main__':unittest.main()

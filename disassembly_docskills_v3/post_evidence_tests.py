"""Post-score verification regressions;no model calls or actor modifications."""
import json
import unittest
from unittest.mock import patch
from .tests.test_document_system import SystemTests
from .post_evidence import replay_result
from disassembly_real_v3.simulator import FullDisassemblySim
from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_recovery.shared_api import RecoveryBudgetLimit
from disassembly_real_v3.runtime import guards


class EvidenceTests(unittest.TestCase):
    setUp=SystemTests.setUp

    def record(self,sim,api):
        p=self.folder/'result.json'
        p.write_text(json.dumps(dict(case_path=str(self.case),
            limits=dict(max_checks=sim.max_checks,max_checkpoints=128,max_restores=256),
            state=sim.export_state(),trace=sim.trace,checker_calls=sim.checks,
            recovery_state=api.export_recovery_state())))
        return p

    def test_uncharged_budget_rejection_is_reexecuted_without_physics(self):
        sim=FullDisassemblySim(self.case,max_checks=0);api=SharedAPI(sim,max_checks=0)
        with self.assertRaises(RecoveryBudgetLimit):api.remove('a','+z')
        audit,replayed,_=replay_result(self.record(sim,api))
        self.assertEqual(audit['status'],'PASS')
        self.assertEqual(audit['physical_queries_replayed'],0)
        self.assertEqual(len(audit['uncharged_API_errors_verified']),1)
        self.assertEqual(replayed.checks,0)

    def test_public_code_budget_exception_alias_has_identical_boundary(self):
        sim=FullDisassemblySim(self.case,max_checks=0)
        api=SharedAPI(sim,max_checks=0,budget_exception=guards.BudgetLimit)
        with self.assertRaises(guards.BudgetLimit):api.remove('a','+z')
        audit,_,_=replay_result(self.record(sim,api))
        self.assertEqual(len(audit['documented_budget_exception_name_aliases']),1)

    def test_invented_error_message_is_rejected(self):
        sim=FullDisassemblySim(self.case,max_checks=0);api=SharedAPI(sim,max_checks=0)
        with self.assertRaises(RecoveryBudgetLimit):api.remove('a','+z')
        p=self.record(sim,api);d=json.loads(p.read_text())
        d['recovery_state']['events'][-1]['error']['message']='not the observed API guard'
        p.write_text(json.dumps(d))
        with self.assertRaises(AssertionError):replay_result(p)

    def test_charged_unfinished_query_keeps_unknown_outcome(self):
        sim=FullDisassemblySim(self.case,max_checks=5);api=SharedAPI(sim,max_checks=5)
        def interrupted(part,direction):
            sim.checks+=1
            raise TimeoutError('native operation interrupted before result')
        with patch.object(sim,'remove',side_effect=interrupted):
            with self.assertRaises(TimeoutError):api.remove('a','+z')
        p=self.record(sim,api)
        audit,replayed,_=replay_result(p,allow_incomplete=True)
        self.assertEqual(audit['status'],'PASS_VERIFIED_PREFIX')
        self.assertEqual(audit['charged_unfinished_checks'],1)
        self.assertFalse(audit['unfinished_result_invented'])
        self.assertEqual(replayed.trace,[])
        with self.assertRaises(AssertionError):replay_result(p)

    def test_completed_queries_and_restore_remain_exact(self):
        sim=FullDisassemblySim(self.case,max_checks=5);api=SharedAPI(sim,max_checks=5)
        root=api.checkpoint();api.remove('a','+z');api.restore(root)
        api.remove('a','+z');api.remove('b','+z')
        audit,replayed,_=replay_result(self.record(sim,api))
        self.assertEqual(audit['status'],'PASS')
        self.assertEqual(audit['physical_queries_replayed'],3)
        self.assertEqual(audit['restores_verified'],1)
        self.assertTrue(replayed.success)


if __name__=='__main__':unittest.main()

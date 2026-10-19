import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from disassembly_final_v6.actors import solve
from disassembly_final_v6.documents import materialize,make_bank,DocumentBank
from disassembly_final_v6.controller import DFS
from disassembly_real_v3.tests.test_task_adapter import CUBE
from disassembly_real_v3.simulator import FullDisassemblySim
from disassembly_learning_v3.shared_api import SharedAPI
from disassembly_hybrid.graph import physical_state_key

class Provider:
    timeout=60
    def __init__(self,read=False):self.read=read;self.prompts=[]
    def complete(self,prompt,schema,index):
        self.prompts.append(prompt)
        empty=dict(operation='execute',skill_ids=[],code='',ordered_actions=[],applied_skill_ids=[],document_plan=[],summary='local deterministic regression')
        if self.read and index==1:return {**empty,'operation':'read_skills','skill_ids':['fixture-aware-test']},{}
        if self.read:
            assert 'TEST_SENTINEL_9876' in prompt
            empty['applied_skill_ids']=['fixture-aware-test']
            empty['document_plan']=[dict(skill_id='fixture-aware-test',observed_trigger='two removable parts',procedure_step='test procedure',intended_action_change='remove both with trusted check')]
        empty['code']="for p in api.snapshot()['remaining_parts']:\n    if not p['fixed']:\n        api.remove(p['id'], '+z')"
        return empty,{}

class SystemTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.folder=Path(self.t.name)
        (self.folder/'cube.obj').write_text(CUBE)
        parts=[]
        for pid,x,fixed in [('a',-.03,False),('b',.03,False),('base',.08,True)]:
            parts.append(dict(id=pid,position=[x,0,.005],quaternion=[1,0,0,0],fixed=fixed,visual_mesh='cube.obj',collision_meshes=['cube.obj'],local_bounds=[[-.005]*3,[.005]*3],mass_kg=.001,allowed_directions=['+z']))
        self.case=self.folder/'case.json';self.case.write_text(json.dumps(dict(id='development_only_regression',target_id='a',parts=parts,physics=dict(settle_seconds=.04))))
        make_bank(self.folder/'S0.json',[],version='S0')
        p=materialize(self.folder/'docs','fixture-aware-test','Read only for this regression.','TEST_SENTINEL_9876\n'+('Retain all procedural document bytes while history grows. '*10))
        make_bank(self.folder/'S1.json',[p],version='test')
    def test_model_explicitly_reads_then_code_executes_without_hidden_skill(self):
        provider=Provider(True);result=solve(self.case,provider,self.folder/'S1.json','code')
        self.assertTrue(result['success'],result.get('error'))
        self.assertEqual(result['llm_calls'],2);self.assertEqual(result['checker_calls'],2)
        self.assertEqual(len(result['document_reads']),1)
        self.assertNotIn('TEST_SENTINEL_9876',provider.prompts[0])
        self.assertIn('TEST_SENTINEL_9876',provider.prompts[1])
        self.assertGreater(result['execution_steps'],0)
    def test_empty_bank_same_actor_permits_episode_feedback_but_no_reusable_doc(self):
        result=solve(self.case,Provider(),self.folder/'S0.json','code')
        self.assertTrue(result['success'],result.get('error'));self.assertEqual(result['document_reads'],[])
        self.assertEqual(result['checker_calls'],2)
    def test_document_read_consumes_only_model_call_and_no_free_execution(self):
        for architecture in ['code','graph_dfs']:
            result=solve(self.case,Provider(True),self.folder/'S1.json',architecture,limits={'max_calls':1})
            self.assertFalse(result['success']);self.assertEqual(result['checker_calls'],0);self.assertEqual(result['llm_calls'],1)

    def test_document_hash_change_rejected(self):
        bank=DocumentBank(self.folder/'S1.json');p=self.folder/bank.manifest['skills'][0]['path']
        p.write_text(p.read_text()+'changed')
        with self.assertRaises(ValueError):DocumentBank(self.folder/'S1.json')
    def test_same_physical_restore_api_retains_cost_and_failed_history(self):
        sim=FullDisassemblySim(self.case,max_checks=5);api=SharedAPI(sim,max_checks=5)
        key=physical_state_key(sim.export_state());h=api.checkpoint();api.remove('a','+z');api.restore(h)
        self.assertEqual(physical_state_key(sim.export_state()),key)
        self.assertEqual(sim.checks,1);self.assertEqual(len(sim.trace),1)
        self.assertEqual(api.export_recovery_state()['restore_count'],1)
    def test_document_read_is_not_application(self):
        class ReadOnly(Provider):
            def complete(self,prompt,schema,index):
                v,m=super().complete(prompt,schema,index)
                if index>1:v['applied_skill_ids']=[]
                return v,m
        result=solve(self.case,ReadOnly(True),self.folder/'S1.json','code')
        self.assertEqual(len(result['document_reads']),1)
        self.assertFalse(result['success']);self.assertIn('review was omitted',result['error']['message'])
    def test_loaded_procedure_survives_long_observation_history(self):
        class LongHistorySim(FullDisassemblySim):
            def snapshot(self):
                value=super().snapshot();value['diagnostic_long_history']='old feedback record; '*12000
                return value
        provider=Provider(True)
        with patch('disassembly_final_v6.actors.FullDisassemblySim',LongHistorySim):
            result=solve(self.case,provider,self.folder/'S1.json','code')
        self.assertTrue(result['success'],result.get('error'))
        self.assertGreater(len(provider.prompts[-1]),200000)
        self.assertIn('TEST_SENTINEL_9876',provider.prompts[-1])
    def test_c_model_order_controls_candidates_after_explicit_document_read(self):
        class RankProvider(Provider):
            def complete(self,prompt,schema,index):
                self.prompts.append(prompt)
                value=dict(operation='execute',skill_ids=[],code='',ordered_actions=[dict(part_id=p,direction='+z') for p in ['b','a']],applied_skill_ids=['fixture-aware-test'],document_plan=[dict(skill_id='fixture-aware-test',observed_trigger='two available actions',procedure_step='test priority',intended_action_change='b before a')],summary='test observed ranking')
                if index==1:return {**value,'operation':'read_skills','skill_ids':['fixture-aware-test'],'ordered_actions':[],'applied_skill_ids':[],'document_plan':[]},{}
                assert 'TEST_SENTINEL_9876' in prompt
                return value,{}
        result=solve(self.case,RankProvider(True),self.folder/'S1.json','graph_dfs')
        self.assertTrue(result['success'],result.get('error'))
        self.assertEqual([a['part_id'] for a in result['actions']],['b','a'])
        self.assertGreater(result['execution_steps'],0)
    def test_common_api_progress_retains_authoritative_code_registry(self):
        path=self.folder/'live.json'
        result=solve(self.case,Provider(True),self.folder/'S1.json','code',progress_path=path)
        logged=json.loads(path.read_text())
        self.assertEqual(logged['checker_calls'],result['checker_calls'])
        self.assertEqual(logged['state'],result['state'])
        self.assertEqual(logged['recovery_state'],result['recovery_state'])
        self.assertNotIn('unfinished_operation',logged)

    def test_interrupted_native_query_replay_keeps_charge_without_inventing_a_result(self):
        from disassembly_final_v6.evidence_replay import replay_result
        sim=FullDisassemblySim(self.case,max_checks=5);api=SharedAPI(sim,max_checks=5)
        def interrupted(part,direction):
            sim.checks+=1
            raise TimeoutError('native operation interrupted before a result')
        with patch.object(sim,'remove',side_effect=interrupted):
            with self.assertRaises(TimeoutError):api.remove('a','+z')
        result=dict(case_path=str(self.case),limits=dict(max_checks=5,max_checkpoints=128,max_restores=256),
            state=sim.export_state(),trace=sim.trace,checker_calls=sim.checks,recovery_state=api.export_recovery_state())
        p=self.folder/'interrupted_result.json';p.write_text(json.dumps(result))
        audit,replayed,_=replay_result(p,allow_incomplete=True)
        self.assertEqual(audit['status'],'PASS_VERIFIED_PREFIX')
        self.assertEqual(audit['charged_unfinished_checks'],1)
        self.assertEqual(replayed.trace,[]);self.assertFalse(audit['unfinished_result_invented'])

    def test_code_operation_start_logs_the_current_authoritative_recovery_registry(self):
        path=self.folder/'live_start.json';original=FullDisassemblySim.remove;observed=[]
        def inspect_start(sim,part,direction):
            row=json.loads(path.read_text());last=row['recovery_state']['events'][-1]
            self.assertEqual(last['operation'],'remove');self.assertEqual(last['status'],'started')
            self.assertEqual(last['part_id'],part)
            self.assertEqual(row['checker_calls'],sim.checks+1);observed.append(part)
            return original(sim,part,direction)
        with patch.object(FullDisassemblySim,'remove',inspect_start):
            result=solve(self.case,Provider(),self.folder/'S0.json','code',progress_path=path)
        self.assertTrue(result['success']);self.assertEqual(observed,['a','b'])

class SearchTests(unittest.TestCase):
    def test_shared_seed_rejection_is_imported_without_globally_pruning_other_states(self):
        class Sim:
            trace=[]
            def export_state(self):return dict(remaining=['a','base'],poses={p:dict(position=[0,0,0]) for p in ['a','base']})
        class API:
            def checkpoint(self):return 'seed'
            def snapshot(self):return dict(remaining_parts=[dict(id='a',fixed=False,allowed_directions=['+x','-x']),dict(id='base',fixed=True)])
        sim=Sim();key=physical_state_key(sim.export_state())
        sim.trace=[dict(physical_state_key_before=key,part_id='a',direction='+x',valid=False,reason='unstable_remainder',blockers=[]),
            dict(physical_state_key_before='different_state',part_id='a',direction='-x',valid=False,reason='path_collision',blockers=['base'])]
        dfs=DFS();actions=dfs.candidates(sim,API())
        self.assertEqual(actions,[dict(part_id='a',direction='-x')])
        self.assertIn(('a','+x'),dfs.graph.rejected(key))

    def test_real_dfs_backtrack_resumes_parent_without_repeating_failed_edge(self):
        class Sim:
            remaining=['payload','support','base'];checks=0
            @property
            def success(self):return len(self.remaining)<=1
            def export_state(self):return dict(remaining=self.remaining,poses={p:dict(position=[0,0,0]) for p in self.remaining})
        class API:
            def __init__(self,sim):self.sim=sim;self.saved={};self.restores=[];self.actions=[]
            def checkpoint(self):
                h=str(len(self.saved));self.saved[h]=list(self.sim.remaining);return h
            def restore(self,h):self.sim.remaining=list(self.saved[h]);self.restores.append(h)
            def snapshot(self):return dict(remaining_parts=[dict(id=p,fixed=p=='base',allowed_directions=['+z']) for p in self.sim.remaining])
            def remove(self,p,d):
                self.sim.checks+=1;self.actions.append((tuple(self.sim.remaining),p,d))
                valid=not(p=='payload' and 'support' not in self.sim.remaining)
                if valid:self.sim.remaining=[x for x in self.sim.remaining if x!=p]
                return dict(valid=valid,reason='ok' if valid else 'unstable_remainder',part_id=p,direction=d,blockers=[])
        sim=Sim();api=API(sim);dfs=DFS();dfs.order=[dict(part_id='support',direction='+z')]
        statuses=[]
        while not sim.success and len(statuses)<20:statuses.append(dfs.step(sim,api))
        self.assertTrue(sim.success);self.assertIn('restored',statuses);self.assertEqual(len(api.restores),1)
        self.assertEqual(len(api.actions),len(set(api.actions)))
        self.assertEqual(api.actions[-2][1:],('payload','+z'))

if __name__=='__main__':unittest.main()

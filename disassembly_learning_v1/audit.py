"""Independent retained-record audit; no actor imports/model/physics execution."""
from __future__ import annotations
import argparse
import ast
import collections
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
LIMITS = dict(max_calls=8, max_checks=120, max_steps=10000000, timeout_seconds=480., max_checkpoints=128, max_restores=256)

def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value, ensure_ascii=False):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=ensure_ascii,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
def key(state):
    ids=sorted(state['remaining'])
    return digest({'remaining':ids,'poses':{p:state['poses'][p]for p in ids}},True)
def neutral(value):
    if isinstance(value,dict):return {k:neutral(v)for k,v in value.items()if k!='elapsed_seconds'}
    if isinstance(value,list):return [neutral(v)for v in value]
    return value
def score(results):
    return dict(successes=sum(bool(r['success'])for r in results),checks=sum(r['checker_calls']for r in results),
        failed_checks=sum(sum(not t.get('valid')for t in r['trace'])for r in results),
        committed=sum(sum(bool(t.get('committed'))for t in r['trace'])for r in results))
def acceptable(before,after):
    pairs=list(zip(before,after));successful=[(x,y)for x,y in pairs if x['success']and y['success']]
    return (len(before)==len(after)and all(not x['success']or y['success']for x,y in pairs)
        and all(not(x['success']and y['success'])or len(y['actions'])<=len(x['actions'])for x,y in pairs)
        and not any(r.get('error')for r in after)and (score(after)['successes']>score(before)['successes']or
        (bool(successful)and sum(y['checker_calls']for x,y in successful)<sum(x['checker_calls']for x,y in successful))))
def compact(result):
    obs=copy.deepcopy(result['initial_observation'])
    for p in obs.get('remaining_parts',[]):
        for k in list(p):
            if k not in {'id','bounds','center','mass','fixed','allowed_directions'}:p.pop(k)
    return dict(initial_observation=obs,success=result['success'],termination=result['termination'],checker_calls=result['checker_calls'],
        actions=[{k:a.get(k)for k in ['part_id','direction']}for a in result.get('actions',[])],
        failed_checks=[{k:t.get(k)for k in ['part_id','direction','reason','blockers','valid','committed','physical_state_key_before','stability']}
            for t in result['trace']if not t.get('valid')][:100],
        note='An action-check failure can be training evidence even when the overall target recovery eventually succeeds.')
def action(a): return a['part_id'],a['direction']
def prompt_payload(text): return json.loads(text.split('\nTASK AND FEEDBACK:\n',1)[1])

class Audit:
    def __init__(self):self.checks=[];self.sources={};self.learning={};self.evaluation=None;self.auxiliary=None
    def check(self,name,value,evidence=None):self.checks.append(dict(check=name,pass_=bool(value),evidence=evidence))
    def load(self,path):
        path=Path(path);self.sources[str(path.relative_to(ROOT))]=sha(path);return read(path)
    def results(self,folder):return [self.load(p)for p in sorted(Path(folder).glob('*/result.json'))]
    def provider(self,folder):
        m=self.load(folder/'metadata.json');p=(folder/'prompt.txt').read_text();label=str(folder.relative_to(ROOT))
        self.check('provider:'+label,m['requested_model']=='gpt-6-luna'and m['requested_reasoning_effort']=='low'
            and m.get('tool_activity_count')==0 and m['prompt_sha256']==sha(folder/'prompt.txt'))
        forbidden=('/Users/','part_roles','selection_report','full_reachable_graph','minimum_removals','good_reference','certificate.json')
        self.check('no_privileged_material:'+label,not any(t in p for t in forbidden))
        return m,p
    def learning_audit(self):
        ledger=self.load(ROOT/'outputs/learning/ledger.json')
        self.check('learning_complete_no_weights_or_eval_learning',ledger['status']=='complete'and
            ledger['weight_updates']is False and ledger['evaluation_learning']is False)
        banks={p.stem:self.load(p)for p in (ROOT/'memory/banks').glob('*.json')};byhash={b['bank_sha256']:b for b in banks.values()}
        self.banks=banks
        for name,b in banks.items():
            self.check('bank_hash:'+name,digest({k:v for k,v in b.items()if k!='bank_sha256'})==b['bank_sha256'])
            self.check('base_frozen:'+name,b['base_source_sha256']==sha(WORKSPACE/'disassembly_recovery/library_functions.py'))
            for s in b['skills']:
                tree=ast.parse(s['source'])
                self.check('skill_hash_and_no_import_private:'+name+':'+s['id'],hashlib.sha256(s['source'].encode()).hexdigest()==s['source_sha256']and
                    not any(isinstance(n,(ast.Import,ast.ImportFrom,ast.ClassDef,ast.Global,ast.Nonlocal))or
                        isinstance(n,ast.Attribute)and n.attr.startswith('_')for n in ast.walk(tree)))
        self.check('S0_empty_new_entries',banks['S0']['skills']==[])
        self.check('S1_ledger_hash',banks['S1']['bank_sha256']==ledger['learned_bank_sha256']and len(banks['S1']['skills'])==ledger['admitted_skills'])
        previous_hash=banks['S0']['bank_sha256'];rows=[];usage=collections.Counter();calls=0;devpaths=set();valpaths=set()
        for item in ledger['rounds']:
            n=item['round'];folder=ROOT/'outputs/learning'/f'round_{n:02d}';ad=self.load(folder/'admission.json');parent=byhash[ad['parent_bank_sha256']]
            self.check('ledger_and_parent:'+str(n),ad==item and ad['parent_bank_sha256']==previous_hash)
            devpaths.update(ad['development_cases']);valpaths.update(ad['validation_cases'])
            bd=self.results(folder/'baseline_development');bv=self.results(folder/'baseline_validation')
            self.check('parent_loaded_into_actual_episodes:'+str(n),all(r['bank_sha256']==parent['bank_sha256']for r in bd+bv))
            self.check('actual_baseline_score:'+str(n),score(bv)==ad['baseline_validation'])
            prior=[];selected=[]
            for a in ad['attempts']:
                d=folder/f"candidate_{a['candidate']:02d}";review=self.load(d/'review.json');m,p=self.provider(d/'llm/call_01')
                response=self.load(d/'llm/call_01/response.json');calls+=1
                usage.update({k:v for k,v in m.get('usage',{}).items()if isinstance(v,(int,float))})
                self.check('candidate_retained:'+str(d.relative_to(ROOT)),review==a)
                evidence,rest=p.split('\nACTUAL DEVELOPMENT FAILURE EVIDENCE:\n',1)[1].split('\nCURRENT REUSABLE REPAIRS:\n',1)
                repairs,feedback=rest.split('\nPREVIOUS CANDIDATE FEEDBACK:\n',1)
                fields=['name','failure_signature','when_to_apply','strategy','triggers','source']
                self.check('actual_development_only:'+str(d.relative_to(ROOT)),json.loads(evidence)==[compact(r)for r in bd])
                self.check('persisted_parent_in_prompt:'+str(d.relative_to(ROOT)),json.loads(repairs)==[{k:s[k]for k in fields}for s in parent['skills']])
                self.check('no_validation_feedback_to_proposer:'+str(d.relative_to(ROOT)),json.loads(feedback)==prior and
                    not any(Path(validation_path).stem in p for validation_path in ad['validation_cases']))
                if a['syntax_ok']:
                    s=self.load(d/'skill.json');cr=self.results(d/'development')
                    self.check('source_exact_actual_response:'+s['id'],all(s[k]==response[k]for k in fields)and s['provenance']['response_sha256']==digest(response))
                    self.check('dev_selection_recomputed:'+s['id'],score(cr)==a['development_score']and score(bd)==a['baseline_development_score']
                        and acceptable(bd,cr)==a['development_improves'])
                    prior.append(dict(rationale=response['rationale'],source=response['source'],development_score=score(cr),baseline_score=score(bd),
                        failure_evidence=[compact(r)for r in cr]))
                    if a.get('selected_for_validation'):selected.append(s)
                else:prior.append({'candidate_error':a['error']})
            vr=self.results(folder/'selected_validation');admitted=bool(selected)and acceptable(bv,vr)
            self.check('admission_recomputed:'+str(n),len(selected)<=1 and admitted==ad['admitted'])
            self.check('validation_not_proposal_feedback:'+str(n),ad['validation_feedback_used_for_proposal']is False and
                (not selected or ad['attempts'][-1].get('selected_for_validation')))
            if vr:self.check('validation_score:'+str(n),score(vr)==ad['candidate_validation'])
            rb=byhash[ad['result_bank_sha256']]
            if admitted:self.check('bank_exact_parent_plus_candidate:'+str(n),rb['skills'][:-1]==parent['skills']and all(rb['skills'][-1][k]==selected[0][k]for k in selected[0]))
            else:self.check('rejection_preserves_bank:'+str(n),ad['result_bank_sha256']==ad['parent_bank_sha256'])
            previous_hash=ad['result_bank_sha256'];rows.append(dict(round=n,candidates=len(ad['attempts']),admitted=admitted,
                baseline_validation=score(bv),candidate_validation=score(vr)if vr else None))
        self.check('dev_validation_disjoint',devpaths.isdisjoint(valpaths)and {sha(p)for p in devpaths}.isdisjoint(sha(p)for p in valpaths))
        self.check('S1_exact_final_admission',banks['S1']['parent_sha256']==previous_hash and banks['S1']['skills']==byhash[previous_hash]['skills'])
        probe=self.load(ROOT/'outputs/learning/persisted_reload_probe.json')
        self.check('separate_reload_record_matches_bank',probe['fresh_process_load']and probe['bank_sha256']==banks['S1']['bank_sha256']
            and probe['skill_ids']==[s['id']for s in banks['S1']['skills']])
        rollout_paths=list((ROOT/'outputs/learning').rglob('result.json'))
        rollouts=[read(p)for p in rollout_paths]
        comparison=[read(p)for p in rollout_paths if 'S0_comparison' in p.parts]
        self.learning=dict(rounds=rows,proposal_model_calls_including_rejections=calls,model_usage=dict(usage),
            physics_rollouts_including_baselines_validation=len(rollouts),physics_checks_total=sum(r['checker_calls']for r in rollouts),
            admission_rollouts=len(rollouts)-len(comparison),admission_physics_checks=sum(r['checker_calls']for r in rollouts)-sum(r['checker_calls']for r in comparison),
            additional_S0_comparison_rollouts=len(comparison),additional_S0_comparison_checks=sum(r['checker_calls']for r in comparison),
            development_paths=sorted(devpaths),validation_paths=sorted(valpaths),admitted_skills=len(banks['S1']['skills']),
            S0_sha256=banks['S0']['bank_sha256'],S1_sha256=banks['S1']['bank_sha256'])
    def freeze_audit(self):
        path=ROOT/'outputs/protocol/freeze.json';f=self.load(path);self.freeze=f
        self.check('freeze_digest',digest({k:v for k,v in f.items()if k!='manifest_sha256'})==f['manifest_sha256'])
        self.check('known_freeze_file',sha(path)=='87f31f3d034740529d51aec4a3ae5ec8ea0bf9302d593925a1c51f7694b1e852')
        self.check('model_caps_2x2',f['model']=='gpt-6-luna'and f['reasoning_effort']=='low'and f['limits']==LIMITS
            and f['conditions']==['S0_off','S0_on','S1_off','S1_on']and f['planned_trials']==36)
        for p,h in f['source_sha256'].items():
            q=ROOT/'outputs/protocol/source_snapshot'/Path(p).relative_to(WORKSPACE)
            self.check('frozen_source:'+str(Path(p).relative_to(WORKSPACE)),sha(p)==h and sha(q)==h)
        for v,b in f['banks'].items():self.check('frozen_bank:'+v,sha(b['path'])==b['file_sha256']and self.banks[v]['bank_sha256']==b['bank_sha256'])
        self.check('learning_ledger_frozen',sha(ROOT/'outputs/learning/ledger.json')==f['learning_ledger_sha256'])
    def inputs_audit(self):
        m=self.load(ROOT/'outputs/evaluation/manifest.json');self.manifest=m;self.shared={}
        self.check('evaluation_manifest_digest',digest({k:v for k,v in m.items()if k!='manifest_sha256'})==m['manifest_sha256']
            and m['manifest_sha256']=='86ed15d3cf5aff2287374aa800539290fb8fe6800a1dcd0964b209fc46a70725')
        self.check('manifest_retains_frozen_protocol',all(m[k]==v for k,v in self.freeze.items()if k!='manifest_sha256')
            and m['freeze_file_sha256']==sha(ROOT/'outputs/protocol/freeze.json'))
        for p,h in m['asset_sha256'].items():self.check('immutable_asset:'+str(Path(p).relative_to(ROOT)),sha(p)==h)
        idx=self.load(ROOT/'outputs/input_audit/heldout_cases.json');protocol=self.load(ROOT/'outputs/input_audit/heldout_protocol.json')
        cert=self.load(ROOT/'outputs/input_audit/heldout_independent_verification.json')
        self.check('heldout_links_to_freeze',m['case_selection_sha256']==sha(ROOT/'outputs/input_audit/heldout_cases.json')==cert['index_sha256']
            and protocol['freeze_sha256']==m['freeze_file_sha256']==cert['freeze_sha256']
            and protocol['generator_sha256']==sha(ROOT/'data_tools/build_locking_cases.py'))
        self.check('heldout_physics_selection_not_actor_outcome',idx['status']=='PHYSICALLY_CERTIFIED_NO_LLM_RUNS'
            and len(idx['attempts'])==len(idx['cases'])==3 and cert['pass_'] and len(cert['cases'])==3)
        trained=set(self.learning['development_paths']+self.learning['validation_paths'])
        heldout={c['case_path']for c in m['cases']}
        self.check('heldout_disjoint_path_and_casebytes',heldout.isdisjoint(trained)and {sha(p)for p in heldout}.isdisjoint(sha(p)for p in trained))
        frozen_at=datetime.fromisoformat(self.freeze['created_utc']).timestamp()
        certificates={c['case_id']:c for c in cert['cases']}
        for c in m['cases']:
            name=c['case_id'];v=certificates[name];s=c['tracks']['normal'];shared=self.load(s['path']);self.shared[name]=shared
            self.check('heldout_certificate:'+name,v['pass_']and v['complete_bfs']and v['exact_initial_checkpoint_match']and
                v['case_sha256']==sha(c['case_path'])==c['case_sha256']and v['minimum_removals']==c['reference']['minimum_removals']>=4)
            self.check('heldout_created_after_actor_freeze:'+name,Path(c['case_path']).stat().st_mtime>=frozen_at,
                'Local file timestamp evidence, supplemented by generator freeze gate; not external preregistration.')
            self.check('identical_shared_input:'+name,sha(s['path'])==s['sha256']and digest(neutral(shared['observation']))==s['observation_sha256']
                and shared['observation']['state_key']==key(shared['state'])and shared['state']['checks']==s['preparation_checks']==6)
            self.check('normal_not_seeded:'+name,shared['state']['actions']==[]and shared['recovery_state']['restore_count']==0
                and len(shared['recovery_state']['checkpoints'])==1)
        for p in (ROOT/'outputs/learning').rglob('prompt.txt'):
            txt=p.read_text();self.check('no_heldout_in_learning:'+str(p.relative_to(ROOT)),not any(Path(c).stem in txt for c in heldout))
        schedule=self.load(ROOT/'outputs/evaluation/schedule.json');self.schedule=schedule
        expected=[(i,r,c)for i in range(3)for r in range(1,4)for c in m['conditions']]
        self.check('complete_balanced_schedule',len(schedule)==36 and sorted((s['case_index'],s['repeat'],s['condition'])for s in schedule)==sorted(expected)
            and [s['ordinal']for s in schedule]==list(range(1,37)))
        old=self.load(ROOT/'outputs/protocol/preexisting_sha256.json')
        # Include source dependencies recorded before this study even if an actor-freeze list omitted them.
        for rel,h in old['sha256'].items():
            if rel.endswith('.py')and ('build_part' in rel or rel in [str(Path(p).relative_to(WORKSPACE))for p in self.freeze['source_sha256']if 'disassembly_learning_v1/'not in p]):
                self.check('preexisting_dependency:'+rel,sha(WORKSPACE/rel)==h)
        self.evaluation={'planned_trials':36,'completed_trials':None,'cases':[{'case_id':c['case_id'],'minimum_removals':c['reference']['minimum_removals']}for c in m['cases']],
            'initial_inputs':'Exact saved state, observation and registry shared across all four conditions. Prompt strings later depend on actual search history.'}
    def trial_audit(self,folder,r,c,shared):
        label=str(folder.relative_to(ROOT));version=r['condition'].split('_')[0];on=r['condition'].endswith('_on');bank=self.banks[version]
        self.check('trial_identity:'+label,r['bank_sha256']==bank['bank_sha256']and r['llm_rank']==on and r['model']=='gpt-6-luna'
            and r['reasoning_effort']=='low'and r['protocol_sha256']==self.manifest['manifest_sha256']and r['track']=='normal')
        calls=sorted((folder/'llm_calls').glob('call_*'))
        self.check('model_call_caps:'+label,len(calls)==r['llm_calls']<=8 and (on or not calls))
        if 'state'not in r:
            self.check('worker_failure_retained:'+label,not r['success']and r['termination']in {'wall_budget_exhausted','worker_error'}and r['checker_calls']is None)
            return
        self.check('actual_initial_input:'+label,r['initial_observation']==shared['observation']and r['initial_observation_sha256']==c['tracks']['normal']['observation_sha256']
            and r['limits']==LIMITS and r['trace'][:6]==shared['state']['trace'])
        self.check('physical_budget_and_step_accounting:'+label,r['checker_calls']==r['state']['checks']==len(r['trace'])<=120
            and r['execution_steps']==r['controller_execution_steps']+r['bank_execution_steps']<=10000000
            and r['bank_execution_steps']==sum(x['execution_steps']for x in r['retrievals']))
        reg=r['recovery_state'];initialreg=shared['recovery_state'];events=reg['events'];cp=reg['checkpoints']
        self.check('common_episode_registry_prefix:'+label,reg['episode_id']==initialreg['episode_id']and reg['case_sha256']==initialreg['case_sha256']==digest(read(c['case_path']),True)
            and events[:len(initialreg['events'])]==initialreg['events']and all(cp[h]==v for h,v in initialreg['checkpoints'].items()))
        self.check('registry_caps:'+label,len(cp)<=128 and reg['restore_attempts']<=256 and reg['restore_count']==r['successful_restores'])
        self.check('registry_order_and_finalstate:'+label,[e['event_index']for e in events]==list(range(1,len(events)+1))
            and reg['next_event_index']==len(events)+1 and events[-1]['checks_after']==r['checker_calls']
            and events[-1]['state_key_after']==key(r['state'])==r['observation']['state_key'])
        for h,v in cp.items():self.check('exact_checkpoint:'+label+':'+h,v['episode_id']==reg['episode_id']and
            v['metadata']['handle']==h and v['metadata']['state_key']==key(v['state'])and set(v['state'])=={'remaining','poses','actions'})
        byevent={e['event_index']:e for e in events}
        for i,e in enumerate(events):
            tag=label+':'+str(e['event_index']);op=e['operation'];delta=e['checks_after']-e['checks_before']
            self.check('event_no_refund:'+tag,delta==(1 if op in {'check','remove'}and e['status']=='completed'else 0)
                and (i==0 or e['checks_before']==events[i-1]['checks_after']and e['state_key_before']==events[i-1]['state_key_after'])
                and e['started_at_utc']<=e['finished_at_utc'])
            if op=='restore'and e['status']=='completed':self.check('restore_exact:'+tag,e['state_key_after']==cp[e['handle']]['metadata']['state_key'])
        for t in r['trace']:
            e=byevent[t['api_event_index']];tag=label+':'+str(t['checker_call'])
            self.check('trace_event_evidence:'+tag,t['checker_call']==e['checks_after']and t['physical_state_key_before']==e['state_key_before']
                and t['physical_state_key_after']==e['state_key_after']and all(t[k]==e[k]for k in ['valid','committed','part_id','direction','operation']))
            if t.get('search_state_key'):self.check('exact_candidate_state:'+tag,t['search_state_key']==t['physical_state_key_before'])
        self.check('result_goal_and_counters:'+label,r['success']==(c['target_id']not in r['state']['remaining'])
            and r['actions']==r['state']['actions']and r['accepted_removals']==sum(bool(t['committed'])for t in r['trace'])
            and r['successful_restores']==sum(e['operation']=='restore'and e['status']=='completed'for e in events)
            and (not r['success']or r['termination']=='goal_reached'and len(r['actions'])>=c['reference']['minimum_removals']))
        learned={s['id']:s for s in bank['skills']}
        for x in r['retrievals']:
            a=x['retrieval'];tag=label+':'+str(x['application_index']);sid=x['skill_id']
            self.check('bank_fixed_activation:'+tag,x['activation']=='fixed_controller'and x['selected_by_model']is False
                and x['hard_pruning']is False and a['bank_sha256']==bank['bank_sha256']and a['state_key']==x['state_key']
                and x['execution_steps']==a['execution_steps']and (sid is None or sid in learned))
            if sid:self.check('retrieved_frozen_learned_source:'+tag,a['source_sha256']==learned[sid]['source_sha256']
                and set(learned[sid]['triggers']).issubset(a['features']))
            if x.get('api_event_index'):
                e=byevent[x['api_event_index']];self.check('bank_execution_trace:'+tag,x['state_key']==e['state_key_before']
                    and action(x['executed_action'])==action(e))
        self.check('retained_retrievals:'+label,r['retrievals']==r['learning_retrievals']and r['skill_calls']==[x for x in r['retrievals']if x['skill_id']])
        usage=collections.Counter()
        self.check('decisions_match_calls:'+label,len(r['decisions'])==len(calls)and (on or r['decisions']==[]))
        for i,call in enumerate(calls):
            meta,p=self.provider(call);payload=prompt_payload(p);obs=payload['observation'];decision=r['decisions'][i];k=obs['state_key'];tag=label+':call'+str(i+1)
            usage.update({k:v for k,v in meta.get('usage',{}).items()if isinstance(v,(int,float))})
            self.check('rank_only_schema:'+tag,set(self.load(call/'schema.json')['properties'])=={'ordered_actions','summary'})
            self.check('model_actual_input:'+tag,decision['prompt_sha256']==sha(call/'prompt.txt')and decision['state_key']==k
                and payload['limits']==LIMITS and payload['skill_activation']=='fixed bank application; model has no activation choice')
            if i==0:
                initial=copy.deepcopy(shared['observation']);initial.pop('common_probe_feedback',None)
                self.check('same_initial_actual_prompt_observation:'+tag,obs==initial)
            prior=[t for t in r['trace']if t['checker_call']<=decision['checks_before']and t['physical_state_key_before']==k]
            rejected={action(t)for t in prior if not t['valid']}
            g=payload['directed_graph'];edges={(b,t['part_id'],t['direction'])for t in prior if not t['valid']and t['reason']=='path_collision'for b in t['blockers']}
            self.check('graph_only_exact_observed_evidence:'+tag,g['state_key']==k and {action(a)for a in g['rejected_actions']}==rejected
                and {(e['from'],e['to'],e['direction'])for e in g['edges']}==edges and all(e['state_key']==k for e in g['edges']))
            legal={(part['id'],d)for part in obs['remaining_parts']if not part['fixed']for d in part['allowed_directions']}
            supplied={action(a)for a in payload['candidate_actions']}
            attempted={action(t)for t in prior if t['operation']=='remove'}
            self.check('legal_unrejected_candidates:'+tag,supplied.issubset(legal-rejected)and len(supplied)==len(payload['candidate_actions'])
                and (legal-rejected-attempted).issubset(supplied))
            self.check('same_state_feedback_only:'+tag,all(t['physical_state_key_before']==k for t in obs['current_state_feedback']))
        self.check('actual_token_usage:'+label,dict(usage)==r['token_usage'])
    def final_audit(self):
        done=self.load(ROOT/'outputs/evaluation/complete.json');m=self.manifest;rows=[]
        files=list((ROOT/'outputs/evaluation/trials').rglob('result.json'))
        self.check('all_scheduled_outcomes_retained',done['trials']==36 and done['source_verification']=='PASS'and len(files)==36)
        for s in self.schedule:
            c=m['cases'][s['case_index']];folder=ROOT/'outputs/evaluation/trials'/c['case_id']/f"repeat_{s['repeat']:02d}"/s['condition']
            r=self.load(folder/'result.json');self.check('scheduled_identity:'+str(folder.relative_to(ROOT)),r['condition']==s['condition']and r['repeat']==s['repeat'])
            self.trial_audit(folder,r,c,self.shared[c['case_id']]);rows.append(r)
        for c in m['cases']:
            first_prompts=list((ROOT/'outputs/evaluation/trials'/c['case_id']).glob('repeat_*/*_on/llm_calls/call_01/prompt.txt'))
            self.check('same_first_online_prompt_all_banks_repeats:'+c['case_id'],len(first_prompts)==6 and len({sha(p)for p in first_prompts})==1)
        summary={}
        for condition in m['conditions']:
            rr=[r for r in rows if r['condition']==condition]
            summary[condition]=dict(trials=len(rr),successes=sum(r['success']for r in rr),
                physics_checks=sum(r['checker_calls']for r in rr if r['checker_calls']is not None),unknown_physics_counts=sum(r['checker_calls']is None for r in rr),
                llm_calls=sum(r['llm_calls']for r in rr),terminations=dict(collections.Counter(r['termination']for r in rr)),
                restores=sum(r.get('successful_restores',0)for r in rr),learned_skill_applications=sum(sum(x.get('skill_applied',False)for x in r.get('retrievals',[]))for r in rr),
                bank_errors=sum(sum(bool(x.get('error'))for x in r.get('retrievals',[]))for r in rr),
                rank_errors=sum(sum(bool(x.get('ranking_error')or x.get('provider_error'))for x in r.get('decisions',[]))for r in rr))
        self.evaluation.update(completed_trials=len(rows),conditions=summary,
            failure_policy='Every scheduled trial retained; worker failures carry unknown physics counts, not fabricated zero costs.')
    def auxiliary_audit(self):
        p=ROOT/'coordinator.py'
        if not p.exists():return
        sources={}
        for path in [p,ROOT/'tests/test_coordinator.py']:
            if path.exists():
                h=sha(path);rel=str(path.relative_to(ROOT));sources[rel]=h
                q=ROOT/'outputs/independent_audit/auxiliary_source_snapshot'/h/path.name
                q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(path.read_bytes())
        references=[]
        for path in self.freeze['source_sha256']:
            tree=ast.parse(Path(path).read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom)and 'coordinator'in(node.module or ''):references.append(path)
                if isinstance(node,ast.Import)and any('coordinator'in a.name for a in node.names):references.append(path)
        self.check('auxiliary_not_imported_by_frozen_primary_sources',not references)
        self.auxiliary=dict(source_sha256=sources,primary_experiment_treatment=False,
            note='Post-freeze convenience coordinator is separate from the frozen study. Tests use a mocked learner; they do not demonstrate additional live skill discovery.',
            imported_by_primary_sources=references)
    def report(self,final=False):
        failures=[c for c in self.checks if not c['pass_']]
        status='FAIL'if failures else 'PASS_WITH_SCOPE_LIMITS'if final else 'LEARNING_FREEZE_PASS_EVALUATION_PENDING'
        value=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),status=status,
            method='Independent stdlib-only source/hash/retained-log audit; no models or physics executed.',
            learning=self.learning,evaluation=self.evaluation,auxiliary=self.auxiliary,check_count=len(self.checks),failures=failures,
            checks=self.checks,sources=self.sources,audit_source_sha256=sha(__file__),scope_limits=[
                'Guided skill code generation: proposal prompt includes economical-exit strategy hints; not unguided autonomous discovery.',
                'Physical check failures were used even when full development episodes succeeded; skill admission improved cost, not model weights.',
                'Two learning rounds reload persisted banks into fresh instances; a separately retained probe checks fresh-process loading.',
                'One validation geometry per round is small. Held-out cases are designed mechanisms, not a representative industrial sample.',
                'Three repeats reset the same three geometries; they are not nine independent product samples. Rank-OFF executions are deterministic repeats.',
                'Restricted pure Python has bounded containers/arithmetic and cooperative opcode/time guards; it is not an OS sandbox or hard native-code timeout.',
                'Skill retrieval may use historical failure signatures as soft hints. Hard pruning still requires exact-state action evidence.',
                'Online rank OFF still uses a library developed with offline LLM calls. Development and inference costs must be separate.',
                'S0 contains the pre-existing fixed baseline procedures. S1 adds one admitted learned repair; this is not an all-library versus no-library comparison.',
                'LLM ranking is subordinate to library priority rules; its measured contribution can be small or negative.',
                'Provider metadata proves the requested gpt-6-luna alias and low effort, not a version-pinned server-side model checkpoint.',
                'This audit verifies retained records and source hashes. Separate input certification/replay, not this script, executes physical checks.'])
        folder=ROOT/'outputs/independent_audit';folder.mkdir(parents=True,exist_ok=True)
        (folder/'audit.json').write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        print(json.dumps(dict(status=status,checks=len(self.checks),failures=failures,learning=self.learning,evaluation=self.evaluation),ensure_ascii=False))
        return not failures

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');args=parser.parse_args()
    if args.final and not(ROOT/'outputs/evaluation/complete.json').exists():
        raise SystemExit('Final audit waits for evaluation complete.json; no partial-results conclusion.')
    audit=Audit();audit.learning_audit();audit.freeze_audit();audit.inputs_audit()
    if args.final:audit.final_audit();audit.auxiliary_audit()
    raise SystemExit(0 if audit.report(args.final)else 1)

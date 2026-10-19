"""S5 executable memory: unchanged S4 repairs plus metered base/frontier repairs.

Both B and C invoke the same pure procedural source. The bank never performs
physics, checkpoint or restore calls. Episode-local ledger is not model learning.
"""
from __future__ import annotations
import ast, copy, hashlib, json, sys, time
from pathlib import Path
from disassembly_learning_v1.memory import digest, validate_skill
from disassembly_learning_v3.memory import SkillBank as OldSkillBank, ROLES, normalize_actions
from disassembly_learning_v1.memory import features
from disassembly_recovery.runtime import compile_restricted, _safe_builtins, guards
from disassembly_recovery import library_functions as old_base

from .state_transport import clone_json, clone_skill_state

SEMANTICS='v4_explicit_frontier_optimized_baseline_1'

def validate_record(record,role):
    if role in ('order','restore'):return validate_skill(record)
    export='next_step' if role=='frontier' else 'repair'
    source=record['source'];tree=ast.parse(source)
    node=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==export),None)
    expected=['observation','candidates','history','checkpoints','model_order']
    if role=='frontier':expected+=['memory','restore_hint']
    if node is None or [a.arg for a in node.args.args]!=expected:raise ValueError('Invalid new skill entry contract')
    for n in ast.walk(tree):
        if isinstance(n,ast.Constant) and isinstance(n.value,str) and (n.value.isdigit() or 'heldout_' in n.value or 'eval_' in n.value):
            raise ValueError('Hard-coded case/part identity forbidden')
    compile_restricted(source,[export],True)
    return hashlib.sha256(source.encode()).hexdigest()

def _execute_exact(record, role, arguments, max_steps, timeout=.3, capture_priority=False):
    """Same restricted procedure/caps, with exact semantic output transport."""
    source_sha=validate_record(record,role)
    export='next_step' if role=='frontier' else 'repair'
    count=0;deadline=time.monotonic()+timeout
    scope={'__builtins__':_safe_builtins(),'_binary':guards.safe_binary,'_attribute':guards.safe_attribute}
    code=compile_restricted(record['source'],[export],True)
    previous=sys.gettrace();sys._getframe().f_trace_opcodes=True
    priority_rows=[]
    def trace(frame,event,arg):
        nonlocal count
        if frame.f_code.co_filename!='<skills>':return None
        if event=='call':frame.f_trace_opcodes=True;frame.f_trace_lines=False
        elif event=='opcode':
            if count>=max_steps:raise RuntimeError(('frontier ' if role=='frontier' else '')+'skill opcode limit exceeded')
            count+=1
            if count%256==0 and time.monotonic()>deadline:raise RuntimeError(('frontier ' if role=='frontier' else '')+'skill deadline exceeded')
        elif event=='return' and capture_priority:
            # Read the sort keys produced by the actual, already metered S5
            # invocation. Never rerun a skill or copy its ranking algorithm.
            ranked=frame.f_locals.get('ranked')
            if role=='baseline' and frame.f_code.co_name=='rank_candidates' and isinstance(ranked,list):
                for item in ranked:
                    if len(item)==7 and isinstance(item[6],dict):
                        priority_rows.append({'action':copy.deepcopy(item[6]),'key':list(item[:3])})
            elif role=='order' and frame.f_code.co_name=='repair' and isinstance(ranked,list):
                for item in ranked:
                    if len(item)==3 and isinstance(item[2],dict):
                        priority_rows.append({'action':copy.deepcopy(item[2]),'key':[item[0]]})
        return trace
    result=error=None;transport={}
    try:
        if role=='frontier':
            memory,transport['memory_input']=clone_skill_state(arguments[5],with_metadata=True)
            arguments=(*arguments[:5],memory,arguments[6])
        # Isolation is exact; logging helpers never participate in executable input.
        arguments=copy.deepcopy(arguments)
        sys.settrace(trace);exec(code,scope,scope)
        raw=scope[export](*arguments)
        result,transport['proposal_output']=clone_json(raw,with_metadata=True)
        if not isinstance(result,dict):raise ValueError('skill must return a dictionary')
        if role=='frontier':
            if result.get('operation') not in ('remove','restore','checkpoint','exhausted'):raise ValueError('Invalid frontier proposal')
            _,transport['memory_output']=clone_skill_state(result.get('memory'),with_metadata=True)
            if type(result.get('memory')) is not dict:raise ValueError('Frontier memory must be dictionary')
        elif not isinstance(result.get('ordered_actions',[]),list) or not isinstance(result.get('restore_handle',''),str):
            raise ValueError('Malformed repair output')
    except Exception as exc:
        result=None
        error={'type':type(exc).__name__,'message':str(exc)[:600]}
    finally:sys.settrace(previous)
    answer={'output':result,'error':error,'execution_steps':count,'source_sha256':source_sha,'transport':transport}
    if capture_priority:answer['priority_rows']=priority_rows
    return answer


def run_frontier(record,observation,candidates,history,checkpoints,model_order,memory,restore_hint,max_steps,timeout=.3):
    return _execute_exact(record,'frontier',
                          (observation,candidates,history,checkpoints,model_order,memory,restore_hint),max_steps,timeout)

class SkillBank(OldSkillBank):
    runtime_semantics=SEMANTICS
    def __init__(self,path_or_bank,frontier_state=None):
        self.bank=copy.deepcopy(path_or_bank) if isinstance(path_or_bank,dict) else json.loads(Path(path_or_bank).read_text())
        if digest({k:v for k,v in self.bank.items() if k!='bank_sha256'})!=self.bank['bank_sha256']:raise ValueError('Invalid bank hash')
        if hashlib.sha256(Path(old_base.__file__).read_bytes()).hexdigest()!=self.bank['base_source_sha256']:raise ValueError('Retained base dependency changed')
        self.skill_roles=dict(self.bank['skill_roles'])
        if self.bank['runtime_semantics']!=SEMANTICS:raise ValueError('Invalid runtime semantics')
        if set(self.skill_roles)!={s['id'] for s in self.bank['skills']}:raise ValueError('Role coverage mismatch')
        for s in self.bank['skills']:
            if validate_record(s,self.skill_roles[s['id']])!=s['source_sha256']:raise ValueError('Invalid source hash')
        self.version=self.bank['version'];self.sha256=self.bank['bank_sha256'];self.remaining_steps=10000000
        self.frontier_state=clone_skill_state(frontier_state)
        self.optimized=next(s for s in self.bank['skills'] if self.skill_roles[s['id']]=='baseline')
        self.frontier=next(s for s in self.bank['skills'] if self.skill_roles[s['id']]=='frontier')
    def export_state(self):return clone_skill_state(self.frontier_state)
    def retrieve_stages(self,observation,history):
        tags=set(features(observation,history));selected={r:None for r in ROLES};scores={}
        for i,s in enumerate(self.bank['skills']):
            role=self.skill_roles[s['id']]
            if role not in ROLES or not set(s['triggers'])<=tags:continue
            score=(len(set(s['triggers'])),i)
            if role not in scores or score>scores[role]:scores[role]=score;selected[role]=s
        return selected,sorted(tags)
    def baseline(self,observation,candidates,history,checkpoints,model_order,capture_priority=False):
        run=_execute_exact(self.optimized,'baseline',(observation,candidates,history,checkpoints,model_order),min(150000,self.remaining_steps),capture_priority=capture_priority)
        proposal=run['output'] or {}
        answer=(proposal.get('ordered_actions',list(candidates)),proposal.get('restore_handle',''),run['execution_steps'],run['error'])
        return (*answer,run.get('priority_rows',[])) if capture_priority else answer
    def _apply_stages(self, observation, candidates, history, checkpoints, model_order, capture_priority=False):
        selected, tags = self.retrieve_stages(observation, history)
        baseline_result = self.baseline(observation,candidates,history,checkpoints,model_order,capture_priority)
        ordered,handle,base_steps,base_error=baseline_result[:4]
        base_priority=baseline_result[4] if capture_priority else []
        ordered, base_normalization = normalize_actions(ordered, candidates)
        stages = [{
            'role': 'base', 'skill_id': None, 'features': tags,
            'source_sha256': self.bank['base_source_sha256'],
            'execution_steps': base_steps, 'error': copy.deepcopy(base_error),
            'applied': not bool(base_error),
            'input_ordered_actions': copy.deepcopy(candidates),
            'ordered_actions': copy.deepcopy(ordered), 'restore_handle': handle,
            'normalization': base_normalization,
        }]
        retrieval = {
            'runtime_semantics': SEMANTICS,
            'bank_version': self.version, 'bank_sha256': self.sha256,
            'state_key': observation['state_key'], 'checks_before': len(history),
            'features': tags,
            'selected_skill_ids': {role: skill['id'] if skill else None
                                   for role, skill in selected.items()},
            'applied_skill_id': None, 'applied_skill_ids': [],
            'matched_triggers': [], 'source_sha256': None,
            'error': copy.deepcopy(base_error), 'execution_steps': base_steps,
            'base_execution_steps': base_steps, 'learned_execution_steps': 0,
            'applied': False, 'stages': stages,
        }
        output = {
            'ordered_actions': ordered, 'restore_handle': handle,
            'skill_id': None, 'retrieval': retrieval,
            'execution_steps': base_steps, 'error': copy.deepcopy(base_error),
        }
        if capture_priority:
            output['priority_contract']={'basis':[{'role':'base','source_sha256':self.optimized['source_sha256'],'rows':base_priority}],
                'key_semantics':['learned_order_category_if_active','base_category','negative_needed_height','direction_rank'],
                'excluded_arbitrary_tiebreaks':['part_id','direction_string'], 'source':'actual_metered_skill_return_locals'}
        if base_error:
            return output

        for role in ROLES:
            skill = selected[role]
            if skill is None:
                continue
            before_order = copy.deepcopy(output['ordered_actions'])
            run = _execute_exact(
                skill, role, (observation, before_order, history, checkpoints, model_order),
                max_steps=min(150000, max(0, self.remaining_steps - output['execution_steps'])),
                capture_priority=capture_priority and role=='order',
            )
            output['execution_steps'] += run['execution_steps']
            output['skill_id'] = skill['id']
            stage = {
                'role': role, 'skill_id': skill['id'], 'features': tags,
                'matched_triggers': list(skill['triggers']),
                'source_sha256': run['source_sha256'],
                'execution_steps': run['execution_steps'],
                'input_ordered_actions': before_order,
                'proposal': copy.deepcopy(run['output']),
                'error': copy.deepcopy(run['error']), 'applied': False,
                'transport': copy.deepcopy(run['transport']),
            }
            stages.append(stage)
            retrieval.update(
                applied_skill_id=skill['id'], matched_triggers=list(skill['triggers']),
                source_sha256=run['source_sha256'], execution_steps=output['execution_steps'],
                learned_execution_steps=output['execution_steps'] - base_steps,
            )
            if run['error']:
                output['error'] = copy.deepcopy(run['error'])
                retrieval['error'] = copy.deepcopy(run['error'])
                break

            proposal = run['output']
            if role == 'order':
                if capture_priority:
                    output['priority_contract']['basis'].append({'role':'order','source_sha256':skill['source_sha256'],'rows':run.get('priority_rows',[])})
                output['ordered_actions'], normalization = normalize_actions(
                    proposal.get('ordered_actions', []), before_order)
                stage['normalization'] = normalization
                stage['ignored_restore_handle'] = proposal.get('restore_handle', '')
            else:
                # A restore procedure receives the established order as input.
                # Its ordering output cannot replace the ordering procedure.
                stage['ordering_output_ignored'] = True
                stage['ordering_change_ignored'] = proposal.get('ordered_actions', []) != before_order
                proposed_handle = proposal.get('restore_handle', '')
                if proposed_handle and not any(
                        cp.get('handle') == proposed_handle for cp in checkpoints):
                    error = {'type': 'InvalidCheckpoint',
                             'message': 'skill suggested an unavailable checkpoint'}
                    stage['error'] = error
                    output['error'] = copy.deepcopy(error)
                    retrieval['error'] = copy.deepcopy(error)
                    break
                output['restore_handle'] = proposed_handle or output['restore_handle']
            stage.update(applied=True, ordered_actions=copy.deepcopy(output['ordered_actions']),
                         restore_handle=output['restore_handle'])
            retrieval['applied_skill_ids'].append(skill['id'])
            retrieval['applied'] = True
        return output

    def apply(self,observation,candidates,history,checkpoints,model_order,capture_priority=False):
        result=self._apply_stages(observation,candidates,history,checkpoints,model_order,capture_priority)
        stage=result['retrieval']['stages'][0]
        stage.update(skill_id=self.optimized['id'],source_sha256=self.optimized['source_sha256'],implementation='validated exact-semantic optimized baseline')
        result['retrieval'].update(runtime_semantics=SEMANTICS)
        return result
    def plan(self,observation,candidates,history,checkpoints,model_order):
        result=self.apply(observation,candidates,history,checkpoints,model_order)
        if result.get('error'):return result
        return self.finish_plan(result,observation,history,checkpoints,model_order,
                                min(150000,max(0,self.remaining_steps-result['execution_steps'])))
    def prepare_plan(self,observation,candidates,history,checkpoints):
        """C only: one ordering/recovery pass, no frontier-memory mutation."""
        return self.apply(observation,candidates,history,checkpoints,[],capture_priority=True)
    def finish_plan(self,result,observation,history,checkpoints,model_order,frontier_allowance=None):
        """One frontier execution after any legitimate within-tier LLM ranking."""
        if result.get('error'):return result
        if frontier_allowance is None:frontier_allowance=min(150000,max(0,self.remaining_steps))
        run=run_frontier(self.frontier,observation,result['ordered_actions'],history,checkpoints,model_order,
                         self.frontier_state,result.get('restore_handle',''),
                         frontier_allowance)
        result['execution_steps']+=run['execution_steps'];result['error']=copy.deepcopy(run['error'])
        stage={'role':'frontier','skill_id':self.frontier['id'],'source_sha256':run['source_sha256'],
               'execution_steps':run['execution_steps'],'error':copy.deepcopy(run['error']),'applied':not bool(run['error']),
               'proposal':copy.deepcopy(run['output']),'transport':copy.deepcopy(run['transport'])}
        result['retrieval']['stages'].append(stage);result['retrieval']['execution_steps']=result['execution_steps']
        result['retrieval']['learned_execution_steps']=result['execution_steps']-result['retrieval']['base_execution_steps']
        if run['error']:result['retrieval']['error']=copy.deepcopy(run['error']);return result
        proposal=run['output'];self.frontier_state=clone_skill_state(proposal['memory'])
        public={k:copy.deepcopy(v) for k,v in proposal.items() if k!='memory'}
        result['next_step']=public
        result['retrieval']['frontier_skill_id']=self.frontier['id']
        result['retrieval']['applied_skill_ids'].append(self.frontier['id']);result['retrieval']['applied']=True
        result['skill_id']=self.frontier['id']
        return result

"""Shared first-episode contract; B/C use the identical frozen S2 document bank."""
from disassembly_real_v3.code_actor import SPEC as OLD_SPEC

MODEL='gpt-6-luna'
EFFORT='low'
LIMITS=dict(max_calls=8,max_checks=240,timeout_seconds=900.,max_steps=10_000_000,
            max_checkpoints=128,max_restores=256,max_rss_bytes=4294967296,
            max_prompt_bytes=512000,max_response_bytes=64000)
DEV_LIMITS={**LIMITS,'max_checks':600,'timeout_seconds':900.}
ACTION={'type':'object','properties':{'part_id':{'type':'string'},'direction':{'type':'string','enum':['+x','-x','+y','-y','+z','-z']}},'required':['part_id','direction'],'additionalProperties':False}
SCHEMA={'type':'object','properties':{
    'operation':{'type':'string','enum':['read_skills','execute']},
    'skill_ids':{'type':'array','items':{'type':'string'}},
    'code':{'type':'string'},'ordered_actions':{'type':'array','items':ACTION},
    'applied_skill_ids':{'type':'array','items':{'type':'string'}},
    'document_plan':{'type':'array','items':{'type':'object','properties':{
        'skill_id':{'type':'string'},'observed_trigger':{'type':'string'},
        'procedure_step':{'type':'string'},'intended_action_change':{'type':'string'}},
        'required':['skill_id','observed_trigger','procedure_step','intended_action_change'],
        'additionalProperties':False}},
    'summary':{'type':'string'}},
    'required':['operation','skill_ids','code','ordered_actions','applied_skill_ids','document_plan','summary'],'additionalProperties':False}

COMMON='''You plan full disassembly in a finite first episode on one unseen product.
Do not use external tools, files, browsing or model-side execution. Only supplied public observations are available.
Model weights never update. Within-episode feedback is allowed. Cross-product knowledge exists ONLY in the supplied frozen document catalog.
The goal is n-1 committed stable removals. target_id is compatibility focus, not the goal.
Six labels refer to action_frame; use direction_vectors_world for actual world directions.
Removal is sampled kinematic straight translation, then MuJoCo remainder dynamics. A fixed fixture remains permanently anchored.
Every check/remove consumes one shared check, valid or rejected. restore refunds no work. All resource ceilings are cumulative.
The available library consists of physical disassembly-repair SKILL.md documents, not callable Python functions.
Progressive disclosure: initially only skill_ids/name/description are available. To read, return operation=read_skills with skill_ids from the catalog.
The next model call supplies those exact document bytes. Read requests consume model calls and time.
Guided retrieval intervention: when a nonempty catalog is present, read its physical procedure before your first execute response. This is required review, not a claim of autonomous retrieval.
When a selected document links its admission record, the exact validation reference is supplied with that document; read it in the next context, without using file tools.
For each execute response with a loaded document, provide document_plan explaining an observed trigger (or a prospective risk), the exact procedure step, and the concrete intended change to code or action priorities. Name the reviewed and applied ID in applied_skill_ids. Do not claim an unobserved repair happened. This declaration will be compared with actual actions; it does not establish compliance or efficacy.
Reading/claiming is not evidence of behavioral efficacy; all actions are independently recorded. Do not claim use of unloaded documents.
Return all fields in the schema. For read_skills use code='',ordered_actions=[],applied_skill_ids=[],document_plan=[]. For execute use skill_ids=[]. Without a catalog use applied_skill_ids=[],document_plan=[].
No hidden learned feature matcher chooses or executes a skill for you.
Public API type clarification, identical in all conditions: snapshot['remaining_parts'] contains part dictionaries, but checkpoint['remaining_parts'] contains string IDs. snapshot['state_key'] is the current state hash. api.checkpoints() returns dictionaries with handle and state_key. Use only the published fields. All builtins allowed by CODE_SPEC apply; isinstance and type are unavailable; reversed is available. No weights update.
Removal/check feedback and snapshot current_state_feedback entries always report valid/reason, but stability is OPTIONAL: a rejected path collision may have no stability key or a None value because residual dynamics were not run. Before reading nested stability metrics or unstable_parts,use feedback.get('stability') or {} and optional nested access. This is the common API contract for every condition,not a reusable learned physical skill.
'''
CODE_SPEC=OLD_SPEC.split('\nOptional B-only reusable API')[0]+'\nThere is NO skills Python object. Documents can guide code you generate.\n'
API_NOTES=COMMON[COMMON.index('Public API type clarification, identical in all conditions:'):]
C_SPEC='''Your execution role is to rank the supplied legal candidate actions only. AFTER the required JSON document-read phase, return operation=execute, code='', ordered_actions in preferred order. During a pending document-read phase return the read_skills JSON instead of ranking; never look up tools, MCP resources, or files to read it.
The fixed controller keeps exact-state collision edges and rejected-action evidence, a DFS frontier and parent checkpoints.
It never prunes unknown actions. It removes the next untried action in your order, descends after an accepted removal,
and restores the parent only after the child frontier is exhausted. Your ordering may change using failure feedback.
Omitted candidates remain after your list. Duplicate/malformed/unavailable entries are dropped individually.
There is no learned hard priority tier and no automatic skill execution: your order controls all candidates.
Your document procedures may inform ordering but cannot replace fixed DFS's recovery mechanism.
'''
ARMS={'A':dict(architecture='code',bank='S0'),'B':dict(architecture='code',bank='S3'),
      'C':dict(architecture='graph_dfs',bank='S3')}

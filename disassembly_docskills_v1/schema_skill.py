"""Third and last candidate: small API-schema repair, not an unverified DFS skill.

Two remaining allowed model calls draft the document and independently produce
a short verifier. No additional full search episode is allowed. Native unit
replays compare the actual faulty access with the document-guided access on two
development CAD states. Broader failed proposals remain rejected.
"""
import argparse
import copy
import json
from pathlib import Path
from .common import ROOT,read,write,sha,utc,progress
from .learning import CASES,MEM,DEV
from .documents import materialize,make_bank
from .contracts import MODEL,EFFORT

BASE=DEV/'schema_skill'

def propose():
    from disassembly_mujoco.agent import CodexCLIProvider
    amendment=dict(declared_before_unit_verification=utc(),candidate=3,max_candidates=3,
        reason='Twelve autonomous/explicit repair search episodes did not validate a complete search-recovery procedure. Do not admit those. Extract only the factual checkpoint-record repair and independently test that narrow API operation.',
        previous_model_validation_episodes=12,additional_search_episodes=0,
        additional_model_calls=['5: document proposal','6: independent short unit verifier from document only'],
        total_extra_model_call_ceiling=6,native_unit_cases=['00804','00749'],
        unit_criteria=['original faulty checkpoint part-record access raises TypeError in both actual CAD states',
            'new independent verifier receives document plus API schema, not proposer code or reference path',
            'new verifier processes existing checkpoint IDs using fresh snapshot part dictionaries without error and performs exactly one API check',
            'checker feedback/state/cost replay matches an independently reconstructed call'],
        scope='API-data-shape procedure only. Not validation of nearest-ancestor DFS, full-product success, autonomous retrieval or average performance.',
        autonomous_heldout_evaluation_unchanged=True,final_geometry_unopened=True,stop_after_this_candidate_regardless_of_result=True)
    write(BASE/'AMENDMENT.json',amendment,exclusive=True)
    prompt='''Create the THIRD AND LAST candidate SKILL.md. Scope is ONLY decoding the public checkpoint and feedback schema safely in generated code, not implementing DFS/backtracking or claiming task success.
Actual development errors: cp.remaining_parts was indexed as part dictionaries -> TypeError; snapshot.physical_state_key -> KeyError. The verified public schema is:
snapshot['state_key']: current physical hash string.
snapshot['remaining_parts']: list of part dicts, with id,fixed,allowed_directions.
api.checkpoints(): list of checkpoint dicts, each with remaining_parts as list[str] IDs, state_key,accepted_action_prefix,handle.
Some checkpoint IDs may no longer be present in current snapshot. Match IDs only against fresh current records; skip absent IDs or restore a genuinely appropriate ancestor using the separate search policy before reading its current records.
snapshot['history_feedback']: list[dict] compact past outcomes; each record has physical_state_key_before,part_id,direction,valid,committed.
snapshot['recovery']['physical_state_key'] is also supplied, but there is no top-level physical_state_key.
The skill should prevent these exact field/type errors when building a search program. Do not prescribe search order, checkpoint recovery policy, a whole program, or specific product/part IDs. Do not claim a physical rejection is fixed by correcting a Python type error.
Use lowercase-hyphen name, concise preventive description, purpose/applicability/cause/steps/expected feedback/exclusions/evidence/validation/version1.0. Include references/admission.json as authoritative pending validation. CODE applies the API procedure; GRAPH_DFS model ranks offered actions and leaves API handling to host.
This document is generated from actual failures at outputs/development/validation/00804/candidate/result.json and outputs/development/repair_verifier/trials/00804/repair_candidate/result.json. Earlier complete-search documents were rejected.\nReturn name,description,body,reasoning strings; no tools.'''
    schema={'type':'object','properties':{k:{'type':'string'} for k in ['name','description','body','reasoning']},'required':['name','description','body','reasoning'],'additionalProperties':False}
    provider=CodexCLIProvider(BASE/'llm_calls',model=MODEL,reasoning_effort=EFFORT,timeout=120)
    response,metadata=provider.complete(prompt,schema,5)
    path=materialize(MEM/'candidates/candidate_03',response['name'],response['description'],response['body'])
    write(BASE/'proposal.json',dict(response=response,metadata=metadata,path=str(path),sha256=sha(path)),exclusive=True)
    schema={'type':'object','properties':{'code':{'type':'string'},'summary':{'type':'string'}},'required':['code','summary'],'additionalProperties':False}
    task='''Independently write a SHORT restricted Python validation script for the supplied procedural document. Do not solve full disassembly or implement DFS.
Task: get a fresh snapshot, read its state_key and history_feedback, iterate api.checkpoints() and join each checkpoint remaining_parts ID string to CURRENT snapshot remaining_parts dictionaries, skipping IDs absent from the current snapshot. Read fixed/allowed_directions from the matched dictionaries, never from IDs. Select any matched current nonfixed part and perform exactly ONE api.check(part_id,one allowed direction). No remove,restore or new checkpoint. Physical rejection is allowed feedback; the test is schema-safe data handling plus one counted physical query.
No original proposer program or reference removal sequence is provided. The document is the only repair guidance. Available builtins: len,range,dict,list,set,enumerate,sorted,min,max,all,any,str,bool. No imports,classes,reflection,isinstance,type,exceptions,fstrings. Include a top-level invocation. Return code and summary. No tools.\nSKILL DOCUMENT:\n'''+path.read_text()
    verifier,metadata=provider.complete(task,schema,6)
    write(BASE/'independent_verifier.json',dict(response=verifier,metadata=metadata,proposer_code_supplied=False,reference_order_supplied=False),exclusive=True)

def verify_units():
    from disassembly_real_v3.simulator import FullDisassemblySim
    from disassembly_real_v3.runtime import execute_payload
    from .evidence_replay import equal
    verifier=read(BASE/'independent_verifier.json')['response']['code']
    faulty="for cp in api.checkpoints():\n    for part in cp['remaining_parts']:\n        fixed=part['fixed']\n"
    reports=[]
    for aid in ['00804','00749']:
        seed=read(DEV/'repair_verifier/probes'/aid/'shared.json');cp=CASES[aid];bytype={}
        for name,code in [('actual_faulty_access',faulty),('independent_document_verifier',verifier)]:
            sim=FullDisassemblySim(cp,max_checks=60,state=seed['state'])
            result=execute_payload(dict(code=code,exports=[],library_bank=None,max_checks=60,max_steps=100000,
                timeout_seconds=30.,recovery_state=seed['recovery_state'],max_checkpoints=128,max_restores=256),sim,callback=lambda e:None)
            new=result['trace'][len(seed['state']['trace']):]
            row=dict(error=result['error'],new_physical_checks=len(new),steps=result['steps'],source_sha256=sha(cp),
                seed_sha256=sha(DEV/'repair_verifier/probes'/aid/'shared.json'),new_trace=new)
            if name=='independent_document_verifier' and new:
                fresh=FullDisassemblySim(cp,max_checks=60,state=seed['state'])
                again=fresh.check(new[0]['part_id'],new[0]['direction'])
                for field in ['valid','reason','blockers','stability','path_samples','physics_steps']:equal(new[0][field],again[field],field)
                row['independent_physical_recheck']='PASS'
            bytype[name]=row
        before=bytype['actual_faulty_access'];after=bytype['independent_document_verifier']
        passed=bool(before['error'] and before['error']['type']=='TypeError' and after['error'] is None and after['new_physical_checks']==1 and after.get('independent_physical_recheck')=='PASS')
        reports.append(dict(source_id=aid,passed=passed,**bytype))
    passed=all(r['passed'] for r in reports);path=Path(read(BASE/'proposal.json')['path'])
    receipt=dict(status='ADMITTED' if passed else 'REJECTED',created_utc=utc(),criteria_sha256=sha(BASE/'AMENDMENT.json'),document_sha256=sha(path),
        validations=reports,validation_kind='narrow API-schema unit repair on actual CAD states with independent model-generated verifier and physical recheck',
        model_calls_total_for_document_development=6,full_search_validation_episodes_total=12,
        skill_scope='type/key-safe checkpoint record decoding, not a validated DFS or successful physical sequence',
        previous_search_documents_remain_rejected=True,unseen_product_effect_unknown=True,no_weight_update=True)
    write(BASE/'admission.json',receipt,exclusive=True);write(path.parent/'references/admission.json',receipt,exclusive=True)
    if passed:
        make_bank(MEM/'S1.json',[path],version='S1-schema-doc-1.0',evidence=str(BASE/'admission.json'))
        write(DEV/'selected_admission.json',dict(status='ADMITTED',receipt=str(BASE/'admission.json'),sha256=sha(BASE/'admission.json')),exclusive=True)
    progress('document_development_finished',schema_admission=receipt['status'],full_search_documents_admitted=0,remaining_development_search_episodes=0)
    print('NARROW_SCHEMA_SKILL',receipt['status'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['propose','verify_units']);a=p.parse_args();globals()[a.command]()

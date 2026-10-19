"""Verify exact document context retention and separate claims from behavior."""
import hashlib
import json
from pathlib import Path
from .common import ROOT,read,write,sha,utc
from .documents import DocumentBank

def main():
    manifest=read(ROOT/'outputs/evaluation/manifest.json')
    assert (ROOT/'outputs/evaluation/complete.json').exists()
    banks={name:DocumentBank(ROOT/'memory'/(name+'.json')) for name in ['S0','S1']}
    reports=[]
    for case in manifest['cases']:
        for arm,settings in manifest['arms'].items():
            bank=banks[settings['bank']]
            folder=ROOT/'outputs/evaluation/trials'/case['case_id']/arm
            result=read(folder/'result.json');calls=[];loaded=set()
            for d in result['decisions']:
                path=folder/'llm_calls'/('call_%02d'%d['call'])/'prompt.txt'
                text=path.read_text();assert hashlib.sha256(text.encode()).hexdigest()==d['prompt_sha256']
                payload=json.loads(text.rsplit('\nPUBLIC INPUT:\n',1)[1])
                assert payload['reusable_skill_catalog']==bank.catalog()
                assert set(payload['loaded_skill_documents'])==set(d['loaded_before'])
                for sid in d['loaded_before']:
                    assert payload['loaded_skill_documents'][sid]==bank.documents[sid]
                    if sid in bank.validation_references:
                        assert payload['loaded_skill_validation_references'][sid]==bank.validation_references[sid]
                response=d.get('response') or {}
                claimed=response.get('applied_skill_ids',[])
                assert set(claimed)<=set(d['loaded_before'])
                calls.append(dict(call=d['call'],prompt_bytes=d['prompt_bytes'],
                    document_body_ids=list(payload['loaded_skill_documents']),
                    explicit_read_request=response.get('skill_ids') if response.get('operation')=='read_skills' else [],
                    declared_application_ids=claimed,context_exact=True))
            reports.append(dict(case_id=case['case_id'],arm=arm,calls=calls,
                document_requests=len(result['document_reads']),
                post_read_contexts=sum(bool(c['document_body_ids']) for c in calls),
                semantic_application_proven=False,
                interpretation='Exact context bytes and model declarations verified. This does not verify attention, compliance, benefit or a counterfactual cause. Catalog metadata is still available when no body is requested.'))
    write(ROOT/'analysis/memory_context_audit.json',dict(status='PASS',created_utc=utc(),trials=reports,
        all_loaded_document_bytes_retained=True,all_declared_applications_were_loaded=True,
        no_silent_skill_truncation=True,scope='Model prompt payload, not internal model attention or learned weights'))
    print('EXACT_DOCUMENT_CONTEXT_AUDIT_PASS',len(reports),flush=True)

if __name__=='__main__':main()

"""Signed infrastructure erratum: accept old inventory list/dict containers.

No frozen actor, bank, physics, candidate rule or qualification algorithm is
edited. The first input attempt never reached conversion or physics. All its
receipts are retained under an explicit archived path, not recast as CAD failures.
"""
from pathlib import Path
from .common import ROOT,read,write,sha,utc,progress
from .protocol import verify
from . import qualification as q

def main():
    verify();receipt=ROOT/'outputs/protocol/metadata_parser_erratum.json'
    source=ROOT/'outputs/input_audit/qualification'
    archive=ROOT/'outputs/input_audit/qualification_before_metadata_parser_fix'
    if not receipt.exists():
        rows=[]
        for path in sorted(source.glob('*/qualification.json')):
            data=read(path);record=data['status_record']
            assert data.get('case') is None and record['status']=='qualification_error'
            assert "'list' object has no attribute 'get'" in record['details']['error']
            rows.append(dict(source_id=record['id'],path=str(path),sha256=sha(path)))
        assert rows and not (ROOT/'data/assemblies').exists(), 'Erratum applies only before any conversion/physics'
        assert not archive.exists();source.rename(archive)
        value=dict(status='SIGNED_INFRASTRUCTURE_ONLY_ERRATUM',created_utc=utc(),
            original_pre_geometry_freeze_sha256=sha(ROOT/'outputs/protocol/freeze.json'),
            wrapper_sha256=sha(__file__),unchanged_frozen_qualification_sha256=sha(ROOT/'qualification.py'),
            reason='Prior geometry inventory may be a JSON list or mapping. The old same-project metadata reader assumed mapping.get before any CAD conversion or physics.',
            parser_change='Wrap list inventory as assemblies list, preserve mapping inventory exactly; no geometry/eligibility/threshold/action change.',
            original_error_receipts=rows,archive_path=str(archive),original_log_path=str(ROOT/'outputs/qualification.log'),
            source_geometry_may_have_been_read_for_integrity=True,actor_exposure=False,
            conversion_runs_before_erratum=0,physics_runs_before_erratum=0,model_calls_before_erratum=0,
            candidate_reserve_changed=False,document_bank_changed=False,model_or_budget_changed=False)
        write(receipt,value,exclusive=True)
    else:
        value=read(receipt);assert value['wrapper_sha256']==sha(__file__)
    original=q.read
    def compatible_read(path):
        data=original(path)
        if str(path).endswith('geometry_inventory.json') and isinstance(data,list):
            return {'assemblies':data}
        return data
    q.read=compatible_read
    progress('qualification_resumed_after_metadata_container_fix',preserved_error_attempts=len(value['original_error_receipts']),no_actor_exposure=True)
    q.main()

if __name__=='__main__':main()

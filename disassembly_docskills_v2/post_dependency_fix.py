"""Preserve failed infrastructure receipts and connect the existing CoACD build.

This does not amend frozen actor, document, reserve or physics sources. No model
episode is retried: qualification failed before any evaluation episode started.
"""
from pathlib import Path
import importlib.metadata
import shutil
import sys
from .common import ROOT, WORKSPACE, read, write, sha, utc, progress
from .protocol import verify


def main():
    verify()
    receipt_path = ROOT/'outputs/infrastructure/missing_coacd/erratum.json'
    if receipt_path.exists():
        print('Already applied:', receipt_path)
        return
    assert not (ROOT/'outputs/evaluation/manifest.json').exists()
    assert not list((ROOT/'outputs').glob('evaluation/trials/**/job.json'))
    archive = receipt_path.parent
    archive.mkdir(parents=True, exist_ok=True)
    old_root = ROOT/'outputs/input_audit/qualification'
    retry_ids = []
    for folder in sorted(old_root.iterdir()):
        if not folder.is_dir():
            continue
        receipt = folder/'qualification.json'
        if receipt.exists():
            doc = read(receipt)
            assert doc['case'] is None
            assert doc['status_record']['status'] == 'collision_preparation_excluded'
            assert "No module named 'coacd'" in receipt.read_text()
        else:
            # The parent was interrupted before completing this preparation.
            assert (folder/'source_inventory.json').exists() or not list(folder.iterdir())
        retry_ids.append(folder.name)
    moves = []

    def preserve(path):
        if not path.exists():
            return
        target = archive/'original'/path.relative_to(ROOT)
        paths = list(path.rglob('*')) if path.is_dir() else [path]
        entries = [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p),
                    'bytes': p.stat().st_size}
                   for p in sorted(paths) if p.is_file()]
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists()
        shutil.move(str(path), str(target))
        for entry in entries:
            assert sha(archive/'original'/entry['path']) == entry['sha256']
        moves.append({'original': str(path.relative_to(ROOT)),
                      'archive': str(target.relative_to(ROOT)), 'files': entries})

    for aid in retry_ids:
        preserve(old_root/aid)
        preserve(ROOT/'data/assemblies/evaluation'/('asap_'+aid)/'prepared')
        preserve(ROOT/'outputs/input_audit'/('conversion_evaluation_asap_'+aid+'.json'))
    for path in ['outputs/input_audit/selection_progress.json',
                 'outputs/input_audit/selected_cases.json',
                 'outputs/input_audit/conversion_events.jsonl']:
        preserve(ROOT/path)
    target = (WORKSPACE/'disassembly_real_v1/.deps').resolve()
    link = ROOT/'.deps'
    assert (target/'coacd').is_dir()
    if not link.exists():
        link.symlink_to(target, target_is_directory=True)
    assert link.resolve() == target
    sys.path.insert(0, str(link))
    import coacd
    package_files = [p for p in (target/'coacd').rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts]
    installed = dict(version=importlib.metadata.version('coacd'),
                     module_path=str(Path(coacd.__file__).resolve()),
                     package_sha256={str(p.relative_to(target)): sha(p)
                                     for p in sorted(package_files)})
    verify()
    value = dict(status='INFRASTRUCTURE_PATH_CORRECTED', created_utc=utc(),
                 frozen_protocol_sha256=sha(ROOT/'outputs/protocol/freeze.json'),
                 reason='Existing CoACD dependency directory was not connected to the new study.',
                 retry_ids=retry_ids, preserved=moves,
                 symlink=str(link.relative_to(ROOT)), target=str(target), coacd=installed,
                 evaluation_model_episodes_started=0, qualification_only_retry=True,
                 frozen_actor_document_reserve_physics_unchanged=True,
                 obsolete_failure_classification='Infrastructure failure, not CAD or planner invalidity.',
                 original_freeze_package_note='CoACD was not discoverable on freeze process sys.path; runtime uses the same preserved dependency build as earlier studies.')
    write(receipt_path, value, exclusive=True)
    progress('qualification_dependency_repaired', retry_source_count=len(retry_ids),
             evaluation_episodes_started=0, erratum=str(receipt_path.relative_to(ROOT)))
    print('Archived infrastructure failures; same-build CoACD connected:', len(retry_ids), installed['version'])


if __name__ == '__main__':
    main()

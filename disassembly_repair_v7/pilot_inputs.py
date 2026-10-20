"""Pre-registered fresh-pilot input selection (no planner, model or policy outcome).

v7.1 amendment (2026-10-20, before any pilot episode or planner outcome; user-approved):
physics for the reference requirement is P2 (analysis/PHYSICS_DECISION.md), and a
backup pool of never-opened official TEST products (5-10 parts, part count
descending) follows the primary pool if it yields fewer than 3 cases.

Pool: official ASAP training_assembly products never opened by this project
(v6 prior_opened_ids + every 5-digit ID found under any disassembly_* study
folder), 11-20 parts. The official test split has only 23 unopened products,
all <= 10 parts, so it cannot keep v6's >= 10-removal range.
Order: v6 reserve rule (alternating <=15 / >=16-part bins, each sorted by
OBJ bytes, part count, ID). Frozen in outputs/protocol/pilot_candidates.json
before any candidate is extracted.

Stages per candidate, strictly in frozen order, first 3 passing are selected:
 1. v6 qualification, unchanged code/config (v7 copy): source geometry,
    collision preparation, initial physics screen with one fixture, native
    MuJoCo log health, shared initial state.
 2. Duplicate geometry fingerprint vs every earlier opened product: exclude.
 3. v7 sample-0 lock audit at evaluated poses: RECORDED ONLY (not an exclusion;
    residual settling can release a lock, as 06444 showed after 5 removals).
 4. v7 reference search (feasibility.py, 10 workers, cap 2500 physical checks
    (7200 s safety wall), remaining-set pruning) must find a complete n-1 sequence. The sequence is stored under
    outputs/pilot_inputs/<id>/reference_search.json and never enters a planner
    input (planners receive only the case JSON and shared initial state).
"""
from __future__ import annotations
import argparse
import collections
import copy
import glob
import json
import os
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

from .common import ROOT, WORKSPACE, V6, read, sha, utc, write

ARCHIVE = V6 / 'data/source/training_assembly.zip'
ARCHIVE_SHA = '0f21fa9642877c69078b5489bb6a86db3a5e786024cc2fdd19dfb25384a64968'
TRAIN_URL = 'https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/training_assembly.zip'
TEST_ARCHIVE = V6 / 'data/source/test_assembly.zip'
TEST_ARCHIVE_SHA = 'c89ea240b1962e3230b00487bf23f3fcbb8b5cd7b6ce1a6816e043a31cac09c2'
TEST_URL = 'https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/test_assembly.zip'
CANDIDATES = ROOT / 'outputs/protocol/pilot_candidates.json'
BACKUP_CANDIDATES = ROOT / 'outputs/protocol/pilot_backup_candidates.json'
PHYSICS = 'P2_persist_up_to_stable_penetration'  # v7.1 pilot physics (analysis/PHYSICS_DECISION.md)
SELECTED = ROOT / 'outputs/protocol/pilot_selected_P2.json'
INPUTS = ROOT / 'outputs/pilot_inputs'
CONFIG = ROOT / 'outputs/protocol/conversion_pilot.json'
TARGET = 3
REFERENCE_WALL = 7200.  # safety only
REFERENCE_CHECK_CAP = 2500  # deterministic qualification cap
REFERENCE_WORKERS = 10


def _groups(archive=ARCHIVE):
    g = collections.defaultdict(list)
    with zipfile.ZipFile(archive) as z:
        for i in z.infolist():
            if i.filename.endswith('.obj'):
                g[Path(i.filename).parent.name].append(i.file_size)
    return g


def opened_ids():
    ids = set(read(V6 / 'outputs/input_audit/pools.json')['prior_opened_ids'])
    pats = ['disassembly_*/outputs/input_audit/*/*', 'disassembly_*/outputs/input_audit/*/*/*', 'disassembly_*/data/assemblies/*/*',
            'disassembly_*/data/assemblies/*', 'disassembly_*/cases/*/*.json', 'disassembly_*/cases/*.json',
            'disassembly_*/data/source/*/*', 'disassembly_*/outputs/*/*/*']
    for pat in pats:
        for d in glob.glob(str(WORKSPACE / pat)):
            if '/disassembly_repair_v7/' in d:
                continue
            b = os.path.basename(d).replace('asap_', '').replace('.json', '')
            if b.isdigit() and len(b) == 5:
                ids.add(b)
    return ids


def known_fingerprints():
    prints = set()
    for p in [V6 / 'outputs/input_audit/previous_geometry_fingerprints.json',
              V6 / 'outputs/input_audit/current_opened_training_fingerprints.json']:
        prints.update(r['fingerprint'] for r in read(p)['records'])
    for p in glob.glob(str(WORKSPACE / 'disassembly_*/outputs/input_audit/**/source_inventory.json'), recursive=True):
        if '/disassembly_repair_v7/' not in p:
            prints.add(read(p)['assembly_geometry_fingerprint'])
    return prints


def freeze_candidates():
    if CANDIDATES.exists():
        return read(CANDIDATES)
    assert sha(ARCHIVE) == ARCHIVE_SHA
    g = _groups()
    opened = opened_ids()
    rows = sorted([dict(id=k, part_count=len(v), obj_bytes=sum(v)) for k, v in g.items()
                   if k not in opened and 11 <= len(v) <= 20], key=lambda r: (r['obj_bytes'], r['part_count'], r['id']))
    bins = [[r for r in rows if r['part_count'] <= 15], [r for r in rows if r['part_count'] >= 16]]
    ordered = []
    while any(bins):
        for b in bins:
            if b:
                ordered.append(b.pop(0))
    value = dict(created_utc=utc(), status='FROZEN_BEFORE_EXTRACTION', archive=str(ARCHIVE), archive_sha256=ARCHIVE_SHA,
                 split='official training_assembly (never opened by this project)', part_count_range=[11, 20],
                 order_rule='v6 reserve rule: alternating <=15/>=16 bins sorted by (obj_bytes, part_count, id)',
                 excluded_opened_ids=sorted(opened), candidates=ordered, target=TARGET,
                 test_split_note='Official test split: 23 never-opened products remain, all <=10 parts; not used.',
                 known_v6_regression_cads_excluded=True, selection_doc=__doc__.strip())
    write(CANDIDATES, value, exclusive=True)
    return value


def freeze_backup_candidates():
    """v7.1 amendment (user-approved before any pilot outcome): official test products never opened, 5-10 parts.
    Order: part count descending (closest to v6's >=11 range first), then OBJ bytes, then ID."""
    if BACKUP_CANDIDATES.exists():
        return read(BACKUP_CANDIDATES)
    assert sha(TEST_ARCHIVE) == TEST_ARCHIVE_SHA
    g = _groups(TEST_ARCHIVE)
    opened = opened_ids()
    rows = sorted([dict(id=k, part_count=len(v), obj_bytes=sum(v), split='test') for k, v in g.items() if k not in opened],
                  key=lambda r: (-r['part_count'], r['obj_bytes'], r['id']))
    value = dict(created_utc=utc(), status='FROZEN_BEFORE_EXTRACTION', archive=str(TEST_ARCHIVE), archive_sha256=TEST_ARCHIVE_SHA,
                 split='official test_assembly (never opened by this project)', candidates=rows,
                 used_only_if_primary_yields_fewer_than=TARGET, order_rule='part_count desc, obj_bytes, id')
    write(BACKUP_CANDIDATES, value, exclusive=True)
    return value


def extract(aid, split='training'):
    folder = ROOT / 'data/source' / ('asap_' + split) / aid
    receipt = folder / 'source_receipt.json'
    if receipt.exists():
        old = read(receipt)
        for m in old['members']:
            assert sha(ROOT / m['path']) == m['sha256']
        return old
    folder.mkdir(parents=True, exist_ok=True)
    members = []
    archive, archive_sha, url = (ARCHIVE, ARCHIVE_SHA, TRAIN_URL) if split == 'training' else (TEST_ARCHIVE, TEST_ARCHIVE_SHA, TEST_URL)
    with zipfile.ZipFile(archive) as z:
        infos = [i for i in z.infolist() if Path(i.filename).parent.name == aid and not i.is_dir()]
        assert infos
        for info in infos:
            assert Path(info.filename).suffix in ('.obj', '.json')
            payload = z.read(info)
            p = folder / Path(info.filename).name
            p.write_bytes(payload)
            members.append(dict(member=info.filename, path=str(p.relative_to(ROOT)), sha256=sha(p), bytes=len(payload), zip_crc32=info.CRC))
    value = dict(source_assembly_id=aid, split=split, url=url, archive_path=str(archive), archive_sha256=archive_sha,
                 members=members, created_utc=utc())
    write(receipt, value, exclusive=True)
    return value


def source_record(aid, split='training'):
    from disassembly_docskills_v1.data_tools.inventory_sources import load_mesh, shape_fingerprint, assembly_fingerprint
    source = extract(aid, split)
    parts, meshes, reasons = [], [], []
    for entry in source['members']:
        if not entry['path'].endswith('.obj'):
            continue
        p = ROOT / entry['path']
        mesh = load_mesh(p.read_bytes())
        meshes.append(mesh)
        count = len(mesh.split(only_watertight=False))
        if not mesh.is_watertight:
            reasons.append('nonwatertight')
        if count != 1:
            reasons.append('multiple_components')
        if mesh.volume <= 0:
            reasons.append('nonpositive_volume')
        parts.append(dict(id=p.stem, source_member=entry['member'], raw_relative_path=entry['path'], source_sha256=sha(p),
                          source_bytes=p.stat().st_size, shape_fingerprint=shape_fingerprint(mesh), watertight=bool(mesh.is_watertight),
                          connected_components=count, volume=float(mesh.volume), bounds=mesh.bounds.tolist()))
    return dict(id=aid, case_id='asap_' + aid, source_assembly_id=aid, source_group=split + '_assembly',
                source_repository_commit='3727e716b57e0b508c4e9ecd9fefa6953e8f72da', source_archive_url=source['url'],
                part_count=len(parts), parts=parts, geometry_eligible=not reasons,
                geometry_exclusion_reasons=sorted(set(reasons)), assembly_geometry_fingerprint=assembly_fingerprint(meshes))


def shared_input(case_path):
    from disassembly_real_v3.simulator import FullDisassemblySim
    from disassembly_learning_v3.shared_api import SharedAPI
    from .contracts import LIMITS
    sim = FullDisassemblySim(case_path, max_checks=LIMITS['max_checks'])
    api = SharedAPI(sim, max_checks=LIMITS['max_checks'])
    api.checkpoint()
    return dict(state=sim.export_state(), recovery_state=api.export_recovery_state(), observation=api.snapshot())


def qualify_worker(aid, split='training'):
    """v6 preparation.worker logic with v7 paths. Runs in its own process."""
    os.environ['DISASSEMBLY_REAL_CONVERSION_CONFIG'] = str(CONFIG)
    from .data_tools import convert_cad as c
    folder = INPUTS / aid
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / 'qualification.json'
    if final.exists():
        return read(final)
    began = time.monotonic()
    details, entry, signature = {}, None, None
    try:
        inv = folder / 'source_inventory.json'
        record = read(inv) if inv.exists() else source_record(aid, split)
        if not inv.exists():
            write(inv, record, exclusive=True)
        signature = record['assembly_geometry_fingerprint']
        if not record['geometry_eligible']:
            status = 'source_geometry_excluded'
        else:
            metadata = dict(source_archive_url=record['source_archive_url'], source_repository_commit=record['source_repository_commit'],
                            source_group=record['source_group'], source_record_path=str(inv))
            manifest = c.normalize_source(record, sha(inv), metadata)
            parts = c.prepare_assembly(c.ASSEMBLIES / record['case_id'] / 'manifest.json')
            details['parts'] = parts
            if any(p['status'] != 'ready' for p in parts):
                status = 'collision_preparation_excluded'
            else:
                physics = c.screen_case(c.make_case(manifest))
                details['physics_status'] = physics['status']
                if physics['status'] != 'physical_valid':
                    status = 'initial_physics_or_capacity_excluded'
                else:
                    setup = physics['selected']
                    case = ROOT / setup['case_path']
                    from disassembly_final_v6.native_health import inspect_log
                    native = inspect_log((ROOT / setup['initial_physics']['trial_case']).with_suffix('.physics_worker.log'))
                    details['selected_initial_native_health'] = native
                    if not native['warning_free_observed']:
                        status = 'initial_native_engine_warning_or_unknown_excluded'
                    else:
                        sp = folder / 'shared.json'
                        write(sp, shared_input(case), exclusive=True)
                        assert record['part_count'] >= (11 if split == 'training' else 3) and len(setup['fixture_ids']) == 1
                        entry = dict(case_id=record['case_id'], source_assembly_id=aid, part_count=record['part_count'],
                                     required_removals=record['part_count'] - 1, case_path=str(case), case_sha256=sha(case),
                                     shared_path=str(sp), shared_sha256=sha(sp), fixture_ids=setup['fixture_ids'],
                                     source_inventory_path=str(inv), source_split=record['source_group'], geometry_fingerprint=signature)
                        status = 'v6_initially_qualified'
    except Exception as exc:
        status = 'preparation_error'
        details.update(error=repr(exc), traceback=traceback.format_exc())
    result = dict(status_record=dict(id=aid, status=status, elapsed_seconds=time.monotonic() - began, details=details),
                  case=entry, geometry_fingerprint=signature)
    write(final, result, exclusive=True)
    return result


def run_qualify(aid, split='training'):
    final = INPUTS / aid / 'qualification.json'
    if final.exists():
        return read(final)
    (INPUTS / aid).mkdir(parents=True, exist_ok=True)
    log = INPUTS / aid / ('worker_%d.log' % (len(list((INPUTS / aid).glob('worker_*.log'))) + 1))
    with log.open('x') as f:
        subprocess.run([sys.executable, '-B', '-m', 'disassembly_repair_v7.pilot_inputs', 'worker', aid, '--split', split], stdout=f, stderr=subprocess.STDOUT,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'},
                       cwd=str(WORKSPACE))
    if not final.exists():
        raise RuntimeError('qualification worker did not finish: ' + str(log))
    return read(final)


def physical_screen(entry):
    """v7 stages 3-4 for a v6-qualified case."""
    from .physics_audit import audit_case
    from .feasibility import search
    folder = INPUTS / entry['source_assembly_id']
    lock_path = folder / 'lock_audit.json'
    if not lock_path.exists():
        write(lock_path, audit_case(entry['case_path']), exclusive=True)
    # Recorded, not an exclusion: 06444 showed a fixture lock released by residual settling after 5 removals.
    ref_path = folder / ('reference_search_' + PHYSICS.split('_')[0] + '.json')
    if not ref_path.exists() or not read(ref_path).get('final'):
        search(entry['case_path'], REFERENCE_WALL, REFERENCE_WORKERS, ref_path, prune_remaining_set=True, max_checks=REFERENCE_CHECK_CAP,
               variant=PHYSICS)
    ref = read(ref_path)
    return ('reference_complete' if ref['status'] == 'complete_reference_found' else 'no_reference_' + ref['status']), ref['status']


def select():
    frozen = freeze_candidates()
    backup = freeze_backup_candidates()
    final = SELECTED
    if final.exists():
        return read(final)
    seen = known_fingerprints()
    rows = [dict(r, split='training') for r in frozen['candidates']] + [dict(r, split='test', backup_pool=True) for r in backup['candidates']]
    selected, statuses = [], []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {}
        cursor = 0

        def fill():
            while len(futures) < 2 and cursor + len(futures) < len(rows):
                i = cursor + len(futures)
                futures[i] = ex.submit(run_qualify, rows[i]['id'], rows[i]['split'])
        fill()
        while cursor < len(rows) and len(selected) < TARGET:
            result = futures.pop(cursor).result()
            cursor += 1
            row = copy.deepcopy(result['status_record'])
            row.pop('details', None)
            row['split'] = rows[cursor - 1]['split']
            entry = result.get('case')
            sig = result.get('geometry_fingerprint')
            if sig and sig in seen:
                row['status'], entry = 'duplicate_geometry_excluded', None
            if sig:
                seen.add(sig)
            if entry:
                fill()  # keep conversion of the next candidates going during the physical screen
                status, ref_status = physical_screen(entry)
                row.update(v7_physical_screen=status, reference_status=ref_status)
                if status == 'reference_complete':
                    selected.append(dict(entry, physics_variant=PHYSICS, reference_path=str(INPUTS / entry['source_assembly_id'] / ('reference_search_' + PHYSICS.split('_')[0] + '.json'))))
            statuses.append(row)
            write(ROOT / 'outputs/pilot_inputs/progress.json', dict(utc=utc(), cursor=cursor, selected=[c['case_id'] for c in selected], statuses=statuses))
            print(json.dumps(dict(cursor=cursor, id=row['id'], status=row['status'], v7=row.get('v7_physical_screen'), selected=len(selected))), flush=True)
            fill()
        for f in futures.values():
            f.cancel()
    value = dict(status='FINITE_SELECTION_COMPLETE' if len(selected) >= TARGET else 'RESERVE_EXHAUSTED_BELOW_TARGET',
                 utc=utc(), target=TARGET, cases=selected, statuses=statuses, attempted=len(statuses),
                 candidates_frozen_sha256=sha(CANDIDATES), backup_candidates_frozen_sha256=sha(BACKUP_CANDIDATES),
                 physics_variant=PHYSICS, no_planner_outcome_used=True,
                 reference_search_used_for_selection=True, reference_given_to_planners=False)
    write(final, value, exclusive=True)
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['freeze', 'select', 'worker'])
    p.add_argument('aid', nargs='?')
    p.add_argument('--split', default='training')
    a = p.parse_args()
    if a.command == 'freeze':
        v = freeze_candidates()
        b = freeze_backup_candidates()
        print(len(v['candidates']), 'candidates frozen;', len(b['candidates']), 'backup candidates frozen')
    elif a.command == 'select':
        print(json.dumps({k: v for k, v in select().items() if k != 'statuses'}, ensure_ascii=False)[:2000])
    else:
        qualify_worker(a.aid, a.split)

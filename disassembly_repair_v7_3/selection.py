"""v7.3 pre-registered selection of NEW evaluation CADs (no planner, model or policy outcome used).

Adapted copy of disassembly_repair_v7/pilot_inputs.py (+ amendment A1) with v7.3 paths.
Fixed before any candidate is extracted (outputs/protocol/selection_candidates.json):

Pool: official ASAP training_assembly products never opened by ANY disassembly_* study in
this workspace (v6 prior_opened_ids + every 5-digit ID under any study folder, v7 pilot
inputs and v7.2 included; v7.3 itself excluded while it builds the list).
  Tier 1: 11-20 parts, v6 reserve order (alternating <=15/>=16-part bins, each sorted by
          OBJ bytes, part count, ID) — the v7 rule.
  Tier 2 (only after tier 1 is exhausted): 8-10 parts, ordered by part count descending,
          OBJ bytes, ID (closest to the >=10-removal range first).
Target 4 cases; candidates are processed strictly in frozen order and the first 4 that pass are selected.
Amendment (2026-10-20 20:40 UTC, no planner outcome involved): conversions in flight reduced from 4 to 2 (the v7
value) after candidate 40, because CoACD 90 s per-part timeouts dominated collision-preparation exclusions under
the extra CPU contention (26/40 vs v7 37/75). Statuses already recorded are kept; the frozen order is unchanged.
Stages (unchanged from v7.1): v6 qualification (source geometry, collision preparation,
initial physics screen with one fixture, native MuJoCo log health, shared initial state);
duplicate geometry fingerprint vs every earlier opened product -> excluded; sample-0 lock
audit (recorded only); P2 reference search (10 workers, cap 2500 checks, 7200 s safety
wall, remaining-set pruning) must find a complete n-1 sequence. A native MuJoCo failure in
the reference search excludes the candidate (v7 amendment A1). Reference sequences are
stored under outputs/selection_inputs/<id>/ and never enter any planner input.
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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import ROOT, WORKSPACE, V6, read, sha, utc, write

from disassembly_repair_v7.pilot_inputs import (ARCHIVE, ARCHIVE_SHA, TRAIN_URL, _groups,  # noqa: F401
                                                known_fingerprints as v7_known_fingerprints)

CANDIDATES = ROOT / 'outputs/protocol/selection_candidates.json'
SELECTED = ROOT / 'outputs/protocol/selection_selected.json'
INPUTS = ROOT / 'outputs/selection_inputs'
CONFIG = ROOT / 'outputs/protocol/conversion_pilot.json'   # byte-identical copy of the v7.1 conversion config
PHYSICS = 'P2_persist_up_to_stable_penetration'
TARGET = 4
IN_FLIGHT = 2   # v7 value; was 4 until candidate 40 (see docstring amendment)
REFERENCE_WALL = 7200.
REFERENCE_CHECK_CAP = 2500
REFERENCE_WORKERS = 10
MIN_PARTS = 8


def opened_ids():
    ids = set(read(V6 / 'outputs/input_audit/pools.json')['prior_opened_ids'])
    pats = ['disassembly_*/outputs/input_audit/*/*', 'disassembly_*/outputs/input_audit/*/*/*', 'disassembly_*/data/assemblies/*/*',
            'disassembly_*/data/assemblies/*', 'disassembly_*/cases/*/*.json', 'disassembly_*/cases/*.json',
            'disassembly_*/data/source/*/*', 'disassembly_*/outputs/*/*/*', 'disassembly_*/outputs/*/*']
    for pat in pats:
        for d in glob.glob(str(WORKSPACE / pat)):
            if '/disassembly_repair_v7_3/' in d:
                continue
            b = os.path.basename(d).replace('asap_', '').replace('.json', '')
            if b.isdigit() and len(b) == 5:
                ids.add(b)
    return ids


def known_fingerprints():
    prints = set(v7_known_fingerprints())
    for p in glob.glob(str(WORKSPACE / 'disassembly_repair_v7/outputs/pilot_inputs/*/source_inventory.json')):
        prints.add(read(p)['assembly_geometry_fingerprint'])
    return prints


def freeze_candidates():
    if CANDIDATES.exists():
        return read(CANDIDATES)
    assert sha(ARCHIVE) == ARCHIVE_SHA
    g = _groups()
    opened = opened_ids()
    fresh = [dict(id=k, part_count=len(v), obj_bytes=sum(v)) for k, v in g.items() if k not in opened]
    tier1 = sorted([r for r in fresh if 11 <= r['part_count'] <= 20], key=lambda r: (r['obj_bytes'], r['part_count'], r['id']))
    bins = [[r for r in tier1 if r['part_count'] <= 15], [r for r in tier1 if r['part_count'] >= 16]]
    ordered = []
    while any(bins):
        for b in bins:
            if b:
                ordered.append(dict(b.pop(0), tier=1))
    tier2 = sorted([r for r in fresh if MIN_PARTS <= r['part_count'] <= 10], key=lambda r: (-r['part_count'], r['obj_bytes'], r['id']))
    ordered += [dict(r, tier=2) for r in tier2]
    value = dict(created_utc=utc(), status='FROZEN_BEFORE_EXTRACTION', archive=str(ARCHIVE), archive_sha256=ARCHIVE_SHA,
                 split='official training_assembly (never opened by this project)', excluded_opened_ids=sorted(opened),
                 tier_counts=dict(tier1=len(tier1), tier2=len(tier2)), candidates=ordered, target=TARGET, selection_doc=__doc__.strip())
    write(CANDIDATES, value, exclusive=True)
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
    with zipfile.ZipFile(ARCHIVE) as z:
        infos = [i for i in z.infolist() if Path(i.filename).parent.name == aid and not i.is_dir()]
        assert infos
        for info in infos:
            assert Path(info.filename).suffix in ('.obj', '.json')
            payload = z.read(info)
            p = folder / Path(info.filename).name
            p.write_bytes(payload)
            members.append(dict(member=info.filename, path=str(p.relative_to(ROOT)), sha256=sha(p), bytes=len(payload), zip_crc32=info.CRC))
    value = dict(source_assembly_id=aid, split=split, url=TRAIN_URL, archive_path=str(ARCHIVE), archive_sha256=ARCHIVE_SHA,
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
    from disassembly_repair_v7.pilot_inputs import shared_input as v7_shared_input
    return v7_shared_input(case_path)


def qualify_worker(aid, split='training'):
    """v6 preparation.worker logic (via the v7 copy) with v7.3 paths. Runs in its own process."""
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
                        assert record['part_count'] >= MIN_PARTS and len(setup['fixture_ids']) == 1
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
        subprocess.run([sys.executable, '-B', '-m', 'disassembly_repair_v7_3.selection', 'worker', aid, '--split', split],
                       stdout=f, stderr=subprocess.STDOUT,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'},
                       cwd=str(WORKSPACE))
    if not final.exists():
        raise RuntimeError('qualification worker did not finish: ' + str(log))
    return read(final)


def _native(exc):
    return type(exc).__module__.startswith('mujoco') or 'mj_' in str(exc) or type(exc).__name__ == 'FatalError'


def physical_screen(entry):
    from disassembly_repair_v7.physics_audit import audit_case
    from disassembly_repair_v7.feasibility import search
    folder = INPUTS / entry['source_assembly_id']
    marker = folder / 'native_engine_error.json'
    if marker.exists():
        return 'native_engine_resource_excluded', 'native_engine_error'
    lock_path = folder / 'lock_audit.json'
    ref_path = folder / 'reference_search_P2.json'
    try:
        if not lock_path.exists():
            write(lock_path, audit_case(entry['case_path']), exclusive=True)
        if not ref_path.exists() or not read(ref_path).get('final'):
            search(entry['case_path'], REFERENCE_WALL, REFERENCE_WORKERS, ref_path, prune_remaining_set=True,
                   max_checks=REFERENCE_CHECK_CAP, variant=PHYSICS)
    except Exception as exc:
        if not _native(exc):
            raise
        write(marker, dict(utc=utc(), error_type=type(exc).__name__, error=str(exc)[:2000], amendment='v7 A1',
                           scope='Native engine resource failure during qualification; not physical evidence.'), exclusive=True)
        return 'native_engine_resource_excluded', 'native_engine_error'
    ref = read(ref_path)
    return ('reference_complete' if ref['status'] == 'complete_reference_found' else 'no_reference_' + ref['status']), ref['status']


def select():
    frozen = freeze_candidates()
    if SELECTED.exists():
        return read(SELECTED)
    seen = known_fingerprints()
    rows = [dict(r, split='training') for r in frozen['candidates']]
    selected, statuses = [], []
    with ThreadPoolExecutor(max_workers=IN_FLIGHT) as ex:
        futures, cursor = {}, 0

        def fill():
            while len(futures) < IN_FLIGHT and cursor + len(futures) < len(rows):
                i = cursor + len(futures)
                futures[i] = ex.submit(run_qualify, rows[i]['id'], rows[i]['split'])
        fill()
        while cursor < len(rows) and len(selected) < TARGET:
            result = futures.pop(cursor).result()
            cursor += 1
            row = copy.deepcopy(result['status_record'])
            row.pop('details', None)
            row.update(split=rows[cursor - 1]['split'], tier=rows[cursor - 1]['tier'], part_count=rows[cursor - 1]['part_count'])
            entry = result.get('case')
            sig = result.get('geometry_fingerprint')
            if sig and sig in seen:
                row['status'], entry = 'duplicate_geometry_excluded', None
            if sig:
                seen.add(sig)
            if entry:
                fill()
                status, ref_status = physical_screen(entry)
                row.update(v7_physical_screen=status, reference_status=ref_status)
                if status == 'reference_complete':
                    selected.append(dict(entry, physics_variant=PHYSICS, tier=row['tier'],
                                         reference_path=str(INPUTS / entry['source_assembly_id'] / 'reference_search_P2.json')))
            statuses.append(row)
            write(INPUTS / 'progress.json', dict(utc=utc(), cursor=cursor, selected=[c['case_id'] for c in selected], statuses=statuses))
            print(json.dumps(dict(cursor=cursor, id=row['id'], tier=row['tier'], status=row['status'],
                                  v7=row.get('v7_physical_screen'), selected=len(selected))), flush=True)
            fill()
        for f in futures.values():
            f.cancel()
    value = dict(status='FINITE_SELECTION_COMPLETE' if len(selected) >= TARGET else 'POOL_EXHAUSTED_BELOW_TARGET',
                 utc=utc(), target=TARGET, cases=selected, statuses=statuses, attempted=len(statuses),
                 candidates_frozen_sha256=sha(CANDIDATES), physics_variant=PHYSICS, no_planner_outcome_used=True,
                 reference_search_used_for_selection=True, reference_given_to_planners=False)
    write(SELECTED, value, exclusive=True)
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['freeze', 'select', 'worker'])
    p.add_argument('aid', nargs='?')
    p.add_argument('--split', default='training')
    a = p.parse_args()
    if a.command == 'freeze':
        v = freeze_candidates()
        print(v['tier_counts'], 'candidates frozen;', [c['id'] for c in v['candidates'][:8]])
    elif a.command == 'select':
        print(json.dumps({k: v for k, v in select().items() if k != 'statuses'}, ensure_ascii=False)[:2000])
    else:
        qualify_worker(a.aid, a.split)

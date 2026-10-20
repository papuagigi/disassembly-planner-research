"""[v7.3 copy of disassembly_repair_v7/data_tools/convert_cad.py (itself a v6 verbatim copy except the .deps lookup); ROOT = disassembly_repair_v7_3]
Source-preserving ASAP CAD conversion and score-independent physical screening.

This module has no import-time writes. Only this study's directories are writable.
No actor, bank, reference path or model is loaded. Resume reuses completed receipts;
failures stay in the ledger and are never replaced by redesigned geometry.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
sys.path.insert(0, str(WORKSPACE))
# v7 copy: identical conversion code; only the CoACD dependency folder is read from v6.
for _deps in (ROOT / '.deps', WORKSPACE / 'disassembly_final_v6/.deps'):
    if _deps.exists():
        sys.path.insert(0, str(_deps))
        break

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
import trimesh

AUDIT = ROOT / 'outputs/input_audit'
ASSEMBLIES = ROOT / 'data/assemblies'
CASES = ROOT / 'cases'
CATALOG = AUDIT / 'source_catalog.json'
RUN_NAME = None
COACD_SETTINGS = dict(threshold=0.005, preprocess_mode='off', resolution=1500,
                      mcts_iterations=100, mcts_max_depth=4, seed=0,
                      max_convex_hull=-1, merge=True, real_metric=False)
CONFIG = dict(
    version=1, longest_dimension_m=0.24, source_geometry_redesign=False,
    source_final_state='apply when supplied; XYZ Euler radians then translation',
    collision='actual mesh.is_convex else seeded precise uncapped CoACD; no fallback',
    coacd=COACD_SETTINGS, part_timeout_seconds=90, workers=2,
    source_collision_quality=dict(grid_axis_count=7, face_samples=64,
                                  surface_offsets_m=[-0.0005, 0.0005],
                                  sample_material_error_limit_m=0.001,
                                  limitation='Finite deterministic samples, not an exact equality proof.'),
    pose_candidates=dict(stable_pose_top=3, stable_pose_sigma=0.0, stable_pose_seed=0,
                         canonical_order=['z_up', 'z_down', 'x_up', 'x_down', 'y_up', 'y_down'],
                         transform='whole-assembly rigid transform only; ground actual mesh min z'),
    fixture_policy='All zero-clamp poses first; then one deterministic grounded original part per pose. No added support geometry or second clamp.',
    initial_screen=dict(static_penetration_m=0.001, intervals=2, seconds_each=1.5,
                        total_translation_m=0.005, total_rotation_deg=5.0,
                        strict_all_original_stability_criteria=True,
                        arbitrary_fall_adoption=False),
    selection='First five physically valid IDs in predeclared ten-ID reserve. No path search or actor outcome gating.',
    endpoint='Full assembly disassembly to at most one remaining original component (n-1 removals).',
    legacy_target='Nonfixed focus ID is compatibility metadata, not a selective-retrieval goal.',
)
if os.environ.get('DISASSEMBLY_REAL_CONVERSION_CONFIG'):
    _config_path=Path(os.environ['DISASSEMBLY_REAL_CONVERSION_CONFIG']).resolve()
    _config_path.relative_to(ROOT)
    CONFIG=json.loads(_config_path.read_text())
COACD_SETTINGS=copy.deepcopy(CONFIG['coacd'])
if CONFIG.get('asset_namespace'):
    ASSEMBLIES=ROOT/'data/assemblies'/CONFIG['asset_namespace']
if CONFIG.get('case_namespace'):
    CASES=ROOT/'cases'/CONFIG['case_namespace']
COLORS = [[.18,.48,.72,1], [.9,.45,.18,1], [.28,.68,.47,1],
          [.65,.4,.72,1], [.86,.71,.2,1], [.3,.7,.76,1]]


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def dump(path, value):
    """Atomic writes, restricted to the new study, with finite JSON numbers."""
    path = Path(path).resolve()
    path.relative_to(ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(text + '\n')
    temporary.replace(path)


def event(kind, **details):
    AUDIT.mkdir(parents=True, exist_ok=True)
    suffix='_'+RUN_NAME if RUN_NAME else ''
    with (AUDIT / f'conversion_events{suffix}.jsonl').open('a') as f:
        f.write(json.dumps(dict(time_utc=utc(), event=kind, **details),
                           ensure_ascii=False, allow_nan=False) + '\n')
    print(kind, json.dumps(details, ensure_ascii=False), flush=True)


def load_mesh(path):
    """Merge coincident indices for topology; never repair or move source surfaces."""
    raw = trimesh.load(path, force='mesh', process=False)
    if not len(raw.vertices) or not len(raw.faces):
        raise ValueError('Empty mesh')
    if not np.isfinite(raw.vertices).all():
        raise ValueError('Nonfinite source vertices')
    # Default merge_vertices rounds by tolerance; after physical normalization it
    # may collapse distinct tiny CAD features. Exact numeric identity only.
    vertices,inverse=np.unique(np.asarray(raw.vertices),axis=0,return_inverse=True)
    mesh=trimesh.Trimesh(vertices=vertices,faces=inverse[np.asarray(raw.faces)],process=False)
    if not np.array_equal(raw.triangles,mesh.triangles):
        raise ValueError('Exact-coordinate dedup changed a source triangle')
    return mesh


def geometry(mesh):
    return dict(vertices=len(mesh.vertices), faces=len(mesh.faces),
                finite=bool(np.isfinite(mesh.vertices).all()),
                watertight=bool(mesh.is_watertight), winding_consistent=bool(mesh.is_winding_consistent),
                connected_components=len(mesh.split(only_watertight=False)),
                volume=float(mesh.volume), bounds=mesh.bounds.tolist(),
                is_convex=bool(mesh.is_convex))


def export(mesh, path):
    Path(path).write_text(trimesh.exchange.obj.export_obj(mesh, digits=17))


def oriented_convex_mesh(vertices):
    points = np.asarray(vertices)
    hull = ConvexHull(points)
    faces = hull.simplices.copy()
    triangles = points[faces]
    normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    inward = np.einsum('ij,ij->i', normal, hull.equations[:, :3]) < 0
    faces[inward] = faces[inward][:, ::-1]
    mesh = trimesh.Trimesh(vertices=points, faces=faces, process=False)
    mesh.remove_unreferenced_vertices()
    return mesh


def exact_occupancy(mesh, points):
    """Deterministic solid-angle winding; independent of optional rtree installs."""
    result = []
    triangles = np.asarray(mesh.triangles)
    for point in np.asarray(points):
        t = triangles - point
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        la, lb, lc = (np.linalg.norm(x, axis=1) for x in (a, b, c))
        numerator = np.einsum('ij,ij->i', a, np.cross(b, c))
        denominator = (la * lb * lc + np.einsum('ij,ij->i', a, b) * lc
                       + np.einsum('ij,ij->i', b, c) * la
                       + np.einsum('ij,ij->i', c, a) * lb)
        winding = np.sum(2 * np.arctan2(numerator, denominator)) / (4 * np.pi)
        result.append(abs(winding) > .5)
    return np.asarray(result, dtype=bool)


def quality_sample(mesh, hulls):
    """Test source material/voids against union of convex collision pieces."""
    cfg = CONFIG['source_collision_quality']
    axes = [np.linspace(a, b, cfg['grid_axis_count'])
            for a, b in zip(mesh.bounds[0], mesh.bounds[1])]
    grid = np.stack(np.meshgrid(*axes, indexing='ij'), axis=-1).reshape(-1, 3)
    indices = np.unique(np.linspace(0, len(mesh.faces) - 1,
                                   min(len(mesh.faces), cfg['face_samples']), dtype=int))
    centers, normals = mesh.triangles_center[indices], mesh.face_normals[indices]
    points = np.concatenate([grid] + [centers + normals * d
                                     for d in cfg['surface_offsets_m']])
    source_inside = exact_occupancy(mesh, points)
    collision_inside = np.zeros(len(points), dtype=bool)
    for hull in hulls:
        equations = ConvexHull(hull.vertices).equations
        collision_inside |= np.all(points @ equations[:, :3].T + equations[:, 3] <= 1e-10,
                                   axis=1)
    mismatched = source_inside != collision_inside
    mismatch_points = points[mismatched]
    distances = []
    for start in range(0, len(mismatch_points), 32):
        _, d, _ = trimesh.proximity.closest_point_naive(mesh, mismatch_points[start:start+32])
        distances.extend(d.tolist())
    max_error = max(distances, default=0.0)
    worst = []
    indices_mismatch = np.flatnonzero(mismatched)
    for i in np.argsort(distances)[-8:][::-1] if distances else []:
        idx = int(indices_mismatch[i])
        worst.append(dict(point_m=points[idx].tolist(), source_inside=bool(source_inside[idx]),
                          collision_union_inside=bool(collision_inside[idx]),
                          distance_to_source_surface_m=float(distances[i])))
    return dict(sample_count=len(points), source_material_samples=int(source_inside.sum()),
                false_material_samples=int((~source_inside & collision_inside).sum()),
                missing_material_samples=int((source_inside & ~collision_inside).sum()),
                maximum_mismatch_surface_distance_m=float(max_error),
                error_limit_m=cfg['sample_material_error_limit_m'],
                passed=bool(max_error <= cfg['sample_material_error_limit_m']),
                worst_samples=worst, limitation=cfg['limitation'])


def normalize_source(record, catalog_sha, source_metadata=None):
    """Write original shapes in assembled coordinates with one common 0.24m scale."""
    aid = record['case_id']
    destination = ASSEMBLIES / aid
    path = destination / 'manifest.json'
    if path.exists():
        previous = json.loads(path.read_text())
        if previous['catalog_sha256'] != catalog_sha or previous['config_sha256'] != canonical_sha(CONFIG):
            raise ValueError('Existing normalization belongs to another frozen catalog/config')
        for p in previous['parts']:
            if sha(ROOT / p['mesh']) != p['normalized_sha256']:
                raise ValueError('Existing normalized mesh hash changed')
        return previous
    destination.mkdir(parents=True, exist_ok=True)
    raw_dir = (ROOT / record['parts'][0]['raw_relative_path']).parent
    config_path = raw_dir / 'config.json'
    source_config = json.loads(config_path.read_text()) if config_path.exists() else {}
    meshes, parts = {}, []
    for entry in sorted(record['parts'], key=lambda p: int(p['id'])):
        source = ROOT / entry['raw_relative_path']
        if sha(source) != entry['source_sha256']:
            raise ValueError(f'Source bytes changed: {source}')
        mesh = load_mesh(source)
        source_geometry = geometry(mesh)
        if not source_geometry['watertight'] or source_geometry['volume'] <= 0:
            raise ValueError(f'Invalid source solid: {entry["id"]}')
        transform = np.eye(4)
        if entry['id'] in source_config:
            raw_state = source_config[entry['id']].get('final_state')
            state = np.zeros(6) if raw_state is None else np.asarray(raw_state, dtype=float)
            if state.shape == (3,):
                state = np.r_[state, np.zeros(3)]
            if state.shape != (6,) or not np.isfinite(state).all():
                raise ValueError('Invalid source final_state')
            transform[:3, :3] = Rotation.from_euler('xyz', state[3:]).as_matrix()
            transform[:3, 3] = state[:3]
            mesh.apply_transform(transform)
        meshes[entry['id']] = mesh
        parts.append(dict(id=entry['id'], source_member=entry['source_member'],
                          source_file=entry['raw_relative_path'], source_sha256=entry['source_sha256'],
                          source_geometry=source_geometry, source_assembled_transform=transform.tolist()))
    lo = np.min([m.bounds[0] for m in meshes.values()], axis=0)
    hi = np.max([m.bounds[1] for m in meshes.values()], axis=0)
    scale = CONFIG['longest_dimension_m'] / float(np.max(hi - lo))
    center = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    normalization = np.eye(4)
    normalization[:3, :3] *= scale
    normalization[:3, 3] = -center * scale
    for part in parts:
        mesh = meshes[part['id']]
        mesh.apply_transform(normalization)
        target = destination / (part['id'] + '.obj')
        export(mesh, target)
        part.update(mesh=str(target.relative_to(ROOT)), normalized_sha256=sha(target),
                    normalized_geometry=geometry(mesh))
    source_metadata=source_metadata or {}
    manifest = dict(id=aid, source_assembly_id=record['id'], part_count=len(parts),
                    catalog_sha256=catalog_sha, config_sha256=canonical_sha(CONFIG),
                    source_url=source_metadata.get('source_archive_url','https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/test_assembly.zip'),
                    source_group=record.get('source_group',source_metadata.get('source_group','test_assembly')),
                    source_repository_commit=source_metadata.get('source_repository_commit','3727e716b57e0b508c4e9ecd9fefa6953e8f72da'),
                    source_provenance=source_metadata,
                    source_config_sha256=sha(config_path) if config_path.exists() else None,
                    normalization=dict(longest_dimension_m=0.24, scale=scale,
                                       common_transform=normalization.tolist(),
                                       source_units='not declared; benchmark coordinates',
                                       physical_scale_is_assumption=True,
                                       part_shape_or_relative_placement_redesigned=False), parts=parts)
    dump(path, manifest)
    return manifest


def selected_contract(summary):
    """Stable interface consumed by the root's full-disassembly study runner."""
    records=[]
    for selected in summary['selected']:
        case_path=ROOT/selected['case_path']
        case=json.loads(case_path.read_text())
        aid=case['id']
        records.append(dict(case_id=aid,case_path=str(case_path.resolve()),
             case_sha256=sha(case_path),source_assembly_id=selected['source_assembly_id'],
             part_count=len(case['parts']),fixture_ids=selected['fixture_ids'],
             initial_validity_path=str((ROOT/selected['physics_report']).resolve()) if selected.get('physics_report') else str((AUDIT/f'physics_{aid}.json').resolve()),
             conversion_path=str((ROOT/selected['conversion_report']).resolve()) if selected.get('conversion_report') else str((AUDIT/f'conversion_{aid}.json').resolve()),
             accepted=bool(selected.get('candidate_protocol_complete',True)),
             candidate_protocol_complete=bool(selected.get('candidate_protocol_complete',True)),
             pose=selected['pose'],setup_mode=selected['mode'],goal=case['goal'],
             full_disassembly_path_known=False,path_search_or_actor_results_used=False))
    return dict(status=summary['status'],cases=records,
                all_selected_valid=bool(records) and all(x['accepted'] for x in records),
                requested_count=summary.get('requested_count',5),selected_count=len(records),
                requested_five_available=len(records)==5,
                requested_count_available=len(records)==summary.get('requested_count',5),
                stage_role=summary.get('stage_role','evaluation'),
                eligible_for_scored_evaluation=summary.get('stage_role','evaluation')=='evaluation' and bool(records),
                source_catalog_path=summary.get('source_catalog_path',str(CATALOG.resolve())),
                source_catalog_sha256=summary['catalog_sha256'],
                conversion_config_path=summary.get('conversion_config_path',str((AUDIT/'conversion_config.json').resolve())),
                case_selection_path=summary.get('selection_receipt_path',str((AUDIT/'case_selection.json').resolve())),
                rule=summary.get('selection_rule',CONFIG['selection']),declared_order=summary['declared_order'],
                all_reserve_statuses=[*summary['considered'],*
                    [dict(id=aid,status=('not_attempted_after_five_valid' if len(records)==5 else
                                        'not_attempted_pending_input_semantic_review'))
                     for aid in summary.get('unexamined',[])]],
                no_model_or_reference_path_gating=True)


def part_worker(manifest_path, part_id):
    manifest = json.loads(Path(manifest_path).read_text())
    record = next(p for p in manifest['parts'] if p['id'] == part_id)
    mesh = load_mesh(ROOT / record['mesh'])
    center = mesh.bounds.mean(axis=0)
    mesh.apply_translation(-center)
    directory = ASSEMBLIES / manifest['id'] / 'prepared'
    directory.mkdir(parents=True, exist_ok=True)
    visual = directory / ('visual_' + part_id + '.obj')
    export(mesh, visual)
    began = time.monotonic()
    if mesh.is_convex:
        hulls = [oriented_convex_mesh(mesh.vertices)]
        method = 'source_mesh_is_convex'
        settings = None
    else:
        import coacd
        coacd.set_log_level('warn')
        result = coacd.run_coacd(coacd.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces)),
                                 **COACD_SETTINGS)
        if not result:
            raise ValueError('CoACD returned no hulls; fallback forbidden')
        hulls = [oriented_convex_mesh(v) for v, _ in result]
        method, settings = 'coacd', COACD_SETTINGS
    records = []
    for i, hull in enumerate(hulls):
        info = geometry(hull)
        if not info['finite'] or not info['watertight'] or not info['is_convex'] or info['volume'] <= 0:
            raise ValueError('Invalid collision hull')
        target = directory / f'collision_{part_id}_{i:04d}.obj'
        export(hull, target)
        records.append(dict(file=str(target.relative_to(ROOT)), sha256=sha(target), **info))
    sample = quality_sample(mesh, hulls)
    volume = float(mesh.volume)
    metadata = dict(id=part_id, visual_mesh=str(visual.relative_to(ROOT)),
                    collision_meshes=[x['file'] for x in records],
                    position=center.tolist(), quaternion=[1, 0, 0, 0],
                    local_bounds=mesh.bounds.tolist(), mass_kg=max(volume * 1000, .001),
                    fixed=False, normalized_sha256=record['normalized_sha256'],
                    config_sha256=canonical_sha(CONFIG),
                    collision_preparation=dict(method=method, settings=settings,
                         source_is_convex=bool(mesh.is_convex), hull_count=len(hulls),
                         source_volume_m3=volume, sum_hull_volume_m3=sum(x['volume'] for x in records),
                         hull_volume_is_sum_not_union=True, source_quality_samples=sample,
                         hulls=records, centered_visual_sha256=sha(visual),
                         wall_seconds=time.monotonic() - began))
    dump(directory / f'part_{part_id}_preparation.json', metadata)


def prepare_part(manifest_path, part_id, receipt_suffix=''):
    aid = json.loads(Path(manifest_path).read_text())['id']
    directory = ASSEMBLIES / aid / 'prepared'
    directory.mkdir(parents=True, exist_ok=True)
    result_path = directory / f'part_{part_id}_result{receipt_suffix}.json'
    if result_path.exists():
        prior=json.loads(result_path.read_text())
        if prior['status']=='ready':
            metadata=json.loads((directory/f'part_{part_id}_preparation.json').read_text())
            expected=next(r for r in json.loads(Path(manifest_path).read_text())['parts'] if r['id']==part_id)
            assert metadata['normalized_sha256']==expected['normalized_sha256']
            assert metadata['config_sha256']==canonical_sha(CONFIG)
            assert sha(ROOT/metadata['visual_mesh'])==metadata['collision_preparation']['centered_visual_sha256']
            for hull in metadata['collision_preparation']['hulls']:assert sha(ROOT/hull['file'])==hull['sha256']
        return prior
    log_path = directory / f'part_{part_id}{receipt_suffix}.log'
    if log_path.exists():
        history=directory/'interrupted_attempts';history.mkdir(exist_ok=True)
        n=len(list(history.glob(f'part_{part_id}_*.log')))+1
        log_path.rename(history/f'part_{part_id}_{n:03d}.log')
    metadata_path=directory/f'part_{part_id}_preparation.json'
    if metadata_path.exists():
        metadata=json.loads(metadata_path.read_text())
        expected=next(r for r in json.loads(Path(manifest_path).read_text())['parts'] if r['id']==part_id)
        assert metadata['normalized_sha256']==expected['normalized_sha256']
        assert metadata['config_sha256']==canonical_sha(CONFIG)
        for hull in metadata['collision_preparation']['hulls']:assert sha(ROOT/hull['file'])==hull['sha256']
        assert sha(ROOT/metadata['visual_mesh'])==metadata['collision_preparation']['centered_visual_sha256']
        sample=metadata['collision_preparation']['source_quality_samples']
        recovered=dict(id=part_id,status='ready' if sample['passed'] else 'source_collision_sample_mismatch',
            metadata_path=str(metadata_path.relative_to(ROOT)),metadata_sha256=sha(metadata_path),
            hull_count=len(metadata['collision_meshes']),quality_sample=sample,
            recovered_from_completed_metadata=True,wall_seconds=0)
        dump(result_path,recovered);return recovered
    began = time.monotonic()
    result = dict(id=part_id, status='running', time_utc=utc())
    try:
        with log_path.open('x') as log:
            child = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
                                    '--part-worker', str(manifest_path), part_id],
                                   stdout=log, stderr=subprocess.STDOUT,
                                   timeout=CONFIG['part_timeout_seconds'],
                                   env={**os.environ, 'OMP_NUM_THREADS': '1',
                                        'OPENBLAS_NUM_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
        if child.returncode:
            result.update(status='worker_failed', returncode=child.returncode,
                          error_tail=log_path.read_text(errors='replace')[-4000:])
        else:
            metadata_path = directory / f'part_{part_id}_preparation.json'
            metadata = json.loads(metadata_path.read_text())
            sample = metadata['collision_preparation']['source_quality_samples']
            result.update(status='ready' if sample['passed'] else 'source_collision_sample_mismatch',
                          metadata_path=str(metadata_path.relative_to(ROOT)),
                          metadata_sha256=sha(metadata_path),
                          hull_count=len(metadata['collision_meshes']),
                          quality_sample=sample)
    except subprocess.TimeoutExpired:
        result.update(status='timeout', error='No convex-hull fallback permitted')
    except Exception as exc:
        result.update(status='preparation_error', error=repr(exc), traceback=traceback.format_exc())
    result.update(wall_seconds=time.monotonic() - began)
    dump(result_path, result)
    return result


def prepare_assembly(manifest_path):
    """Retain fatal part results and cancel unnecessary unstarted part work."""
    manifest=json.loads(Path(manifest_path).read_text())
    aid=manifest['id']
    directory=ASSEMBLIES/aid/'prepared'
    directory.mkdir(parents=True,exist_ok=True)
    prior={}
    for part in manifest['parts']:
        result_path=directory/f'part_{part["id"]}_result.json'
        if result_path.exists():
            prior[part['id']]=json.loads(result_path.read_text())
    fatal=[r for r in prior.values() if r['status'] not in ['ready','not_attempted_after_part_failure']]
    if fatal:
        retained=[]
        for part in manifest['parts']:
            if part['id'] in prior:
                retained.append(prior[part['id']])
                continue
            partial=(directory/f'part_{part["id"]}.log').exists()
            retained.append(dict(id=part['id'],
                  status='aborted_after_known_assembly_rejection' if partial else 'not_attempted_after_part_failure',
                  fatal_part_ids=[r['id'] for r in fatal],partial_log_retained=partial))
        return retained
    results=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending={pool.submit(prepare_part,manifest_path,p['id']):p['id'] for p in manifest['parts']}
        for future in as_completed(pending):
            if future.cancelled():
                result=dict(id=pending[future],status='not_attempted_after_part_failure')
            else:
                result=future.result()
            results.append(result)
            event('conversion_part_completed',id=aid,part=result['id'],status=result['status'],hulls=result.get('hull_count'))
            dump(conversion_receipt_path(aid),dict(id=aid,status='converting',
                 parts=sorted(results,key=lambda x:int(x['id']))))
            if result['status']!='ready':
                for queued in pending:
                    queued.cancel()
    return results


def make_case(manifest):
    parts = []
    for i, entry in enumerate(manifest['parts']):
        metadata_path = ASSEMBLIES / manifest['id'] / 'prepared' / f'part_{entry["id"]}_preparation.json'
        part = json.loads(metadata_path.read_text())
        part['color'] = COLORS[i % len(COLORS)]
        # Cases live under cases/; all paths resolve relative to their own file.
        part['visual_mesh'] = os.path.relpath(ROOT / part['visual_mesh'], CASES)
        part['collision_meshes'] = [os.path.relpath(ROOT / p, CASES) for p in part['collision_meshes']]
        parts.append(part)
    return dict(id=manifest['id'], source_assembly_id=manifest['source_assembly_id'],
                target_id=parts[0]['id'], target_status='legacy_nonfixed_focus_only_full_n_minus_1_goal',
                goal=dict(kind='full_disassembly', maximum_remaining_parts=1,
                          original_part_count=len(parts), required_removals=len(parts)-1),
                base_id=None, fixture_ids=[], parts=parts,
                physics=dict(gravity=[0,0,-9.81], friction=.5, density_kg_m3=1000,
                             path_mode=CONFIG.get('path_mode','straight_source_axes'),
                             extraction_collision=CONFIG.get('extraction_collision','source_mesh_bvh'),
                             mass_floor_kg=.001,
                             mass_source='Assumed density times closed source mesh volume',
                             inertia_model='Unchanged simulator AABB diagonal inertia at AABB origin; not calibrated product inertia',
                             base_fixture='None; setup decided solely by initial-physics screening'),
                provenance=dict(input_manifest=str((ASSEMBLIES / manifest['id'] / 'manifest.json').relative_to(ROOT)),
                                source_url=manifest['source_url'],
                                source_group=manifest.get('source_group','test_assembly'),
                                source_provenance=manifest.get('source_provenance',{}),
                                source_repository_commit=manifest['source_repository_commit'],
                                normalization=manifest['normalization'],
                                source_scope='Public anonymous research CAD; manufacturer/product/factory provenance unverified',
                                approximation='Convex collision decomposition and uncalibrated material/inertial assumptions'))


def candidate_poses(case):
    meshes = []
    for part in case['parts']:
        mesh = load_mesh(CASES / part['visual_mesh'])
        mesh.apply_translation(part['position'])
        meshes.append(mesh)
    combined = trimesh.util.concatenate(meshes)
    candidates, notes = [], []
    try:
        poses, probabilities = trimesh.poses.compute_stable_poses(
            combined, sigma=0., n_samples=1, seed=0)
        for i, (pose, probability) in enumerate(zip(poses[:3], probabilities[:3])):
            candidates.append((f'combined_stable_{i+1}', pose[:3,:3], float(probability)))
        notes.append(dict(kind='combined_stable_poses', generated=len(poses),
                          candidate_only=True,
                          limitation='Rigid combined-mesh pose is not individual-part dynamic stability'))
    except Exception as exc:
        notes.append(dict(kind='stable_pose_generation_error', error=repr(exc)))
    for label, euler in [('z_up',[0,0,0]), ('z_down',[180,0,0]),
                         ('x_up',[0,-90,0]), ('x_down',[0,90,0]),
                         ('y_up',[90,0,0]), ('y_down',[-90,0,0])]:
        candidates.append((label, Rotation.from_euler('xyz', euler, degrees=True).as_matrix(), None))
    results, seen = [], []
    for label, rotation, probability in candidates:
        if any(np.allclose(rotation, previous, atol=1e-10, rtol=0) for previous in seen):
            notes.append(dict(kind='duplicate_rotation', label=label))
            continue
        seen.append(rotation)
        vertices = np.asarray(combined.vertices) @ rotation.T
        lo, hi = vertices.min(axis=0), vertices.max(axis=0)
        translation = np.array([-(lo[0]+hi[0])/2, -(lo[1]+hi[1])/2, -lo[2]])
        transform = np.eye(4)
        transform[:3,:3], transform[:3,3] = rotation, translation
        results.append(dict(label=label, probability=probability, matrix=transform.tolist()))
    return results, notes


def apply_pose(case, pose):
    result = copy.deepcopy(case)
    transform = np.asarray(pose['matrix'])
    rotation, translation = transform[:3,:3], transform[:3,3]
    xyzw = Rotation.from_matrix(rotation).as_quat()
    for part in result['parts']:
        part['position'] = (rotation @ np.asarray(part['position']) + translation).tolist()
        part['quaternion'] = [float(xyzw[3]), *map(float, xyzw[:3])]
        part['fixed'] = False
    result['initial_orientation'] = pose['label']
    result['whole_assembly_rigid_transform'] = pose['matrix']
    return result


def grounded_base(case):
    """Choose exactly one grounded original member; never add fixture geometry."""
    candidates = []
    for part in case['parts']:
        mesh = load_mesh(CASES / part['visual_mesh'])
        q = part['quaternion']
        rotation = Rotation.from_quat([*q[1:], q[0]]).as_matrix()
        points = mesh.vertices @ rotation.T + np.asarray(part['position'])
        lo, hi = points.min(axis=0), points.max(axis=0)
        if lo[2] <= .0001:
            candidates.append((part['position'][2], -float(np.prod((hi-lo)[:2])), int(part['id']), part['id']))
    return min(candidates)[-1] if candidates else None


def ordered_single_anchors(case):
    """All original members, including above-floor members, in a fixed order."""
    rows=[]
    for part in case['parts']:
        mesh=load_mesh(CASES/part['visual_mesh'])
        q=part['quaternion']
        rotation=Rotation.from_quat([*q[1:],q[0]]).as_matrix()
        points=mesh.vertices@rotation.T+np.asarray(part['position'])
        lo,hi=points.min(axis=0),points.max(axis=0)
        rows.append(dict(id=part['id'],mass_kg=part['mass_kg'],
                         source_volume_m3=part.get('collision_preparation',{}).get('source_volume_m3',part['mass_kg']/1000.),
                         world_xy_aabb_footprint_m2=float(np.prod((hi-lo)[:2])),
                         grounded=bool(lo[2]<=.0001)))
    return sorted(rows,key=lambda p:(-p['mass_kg'],-p['source_volume_m3'],
                     -p['world_xy_aabb_footprint_m2'],int(p['id'])))


def physics_receipt_path(aid):
    namespace=CONFIG.get('receipt_namespace')
    return AUDIT/(f'physics_{namespace}_{aid}.json' if namespace else f'physics_{aid}.json')


def conversion_receipt_path(aid):
    namespace=CONFIG.get('receipt_namespace')
    return AUDIT/(f'conversion_{namespace}_{aid}.json' if namespace else f'conversion_{aid}.json')


def physical_trial(case, trial_path):
    """Strict static and two-interval screen; no arbitrary settled-state adoption."""
    from disassembly_mujoco.simulator import DisassemblySim, angle_degrees
    dump(trial_path, case)
    start = time.monotonic()
    sim = DisassemblySim(trial_path)
    # Paths were constructed relative to cases/, where every trial lives.
    build_start=time.monotonic()
    model, data, ids, geom_part = sim._build()
    initial_build_seconds=time.monotonic()-build_start
    deepest = sorted(data.contact, key=lambda c: float(c.dist))[:20]
    static_penetration = max([0.] + [-float(c.dist) for c in data.contact])
    static_contacts = [dict(part1=geom_part.get(int(c.geom1)), part2=geom_part.get(int(c.geom2)),
                            distance_m=float(c.dist), point_m=c.pos.tolist()) for c in deepest]
    report = dict(static_contact_count=data.ncon, static_max_penetration_m=static_penetration,
                  deepest_static_contacts=static_contacts, accepted=False,
                  initial_build_wall_seconds=initial_build_seconds)
    if static_penetration > CONFIG['initial_screen']['static_penetration_m']:
        report.update(status='static_penetration_exceeds_limit', wall_seconds=time.monotonic()-start)
        return report, None
    original = copy.deepcopy(sim.poses)
    first_start=time.monotonic()
    first, poses1 = sim.settle()
    report['first_settle'] = first
    report['first_settle_wall_seconds']=time.monotonic()-first_start
    if not first['stable']:
        report.update(status='first_strict_settle_failed', wall_seconds=time.monotonic()-start)
        return report, None
    second_start=time.monotonic()
    second, final = sim.settle(poses=poses1)
    report['second_settle'] = second
    report['second_settle_wall_seconds']=time.monotonic()-second_start
    shifts = {pid: float(np.linalg.norm(np.asarray(final[pid]['position']) - p['position']))
              for pid,p in original.items()}
    rotations = {pid: angle_degrees(final[pid]['quaternion'], p['quaternion'])
                 for pid,p in original.items()}
    total_displacement, total_rotation = max(shifts.values()), max(rotations.values())
    # Record changes in inter-part displacement, independently of center-of-mass drift.
    relative = 0.
    for a in original:
        for b in original:
            d0=np.asarray(original[a]['position'])-original[b]['position']
            d1=np.asarray(final[a]['position'])-final[b]['position']
            relative=max(relative,float(np.linalg.norm(d1-d0)))
    accepted = (second['stable'] and total_displacement <= .005 and total_rotation <= 5.)
    report.update(total_displacement_m=total_displacement, total_rotation_deg=total_rotation,
                  displacement_by_part_m=shifts, rotation_by_part_deg=rotations,
                  maximum_pair_relative_translation_change_m=relative,
                  accepted=bool(accepted), status='accepted' if accepted else 'second_or_total_drift_failed',
                  wall_seconds=time.monotonic()-start)
    return report, final if accepted else None


def physical_worker(trial_path, result_path):
    import resource
    case=json.loads(Path(trial_path).read_text())
    began=time.monotonic();cpu=time.process_time()
    report,poses=physical_trial(case,Path(trial_path))
    report['worker_total_wall_seconds']=time.monotonic()-began
    report['worker_cpu_seconds']=time.process_time()-cpu
    report['worker_peak_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin'else 1024)
    dump(Path(result_path),dict(report=report,poses=poses))


def timed_physical_trial(case, trial_path, timeout_override=None):
    """A capacity timeout does not prove the physical assembly is invalid."""
    if trial_path.exists():assert json.loads(trial_path.read_text())==case
    else:dump(trial_path,case)
    result_path=trial_path.with_suffix('.physics_result.json')
    log_path=trial_path.with_suffix('.physics_worker.log')
    if result_path.exists():
        cached=json.loads(result_path.read_text());return cached['report'],cached['poses']
    if log_path.exists():
        history=trial_path.parent/'interrupted_physics_logs';history.mkdir(exist_ok=True)
        n=len(list(history.glob(log_path.stem+'_*')))+1
        log_path.rename(history/(log_path.stem+f'_{n:03d}.log'))
    timeout=CONFIG.get('initial_setup_timeout_seconds',60)
    if timeout_override is not None:timeout=min(timeout,float(timeout_override))
    began=time.monotonic()
    with log_path.open('x') as log:
        try:
            proc=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),
                  '--physics-worker',str(trial_path),str(result_path)],
                  stdout=log,stderr=subprocess.STDOUT,timeout=timeout,
                  env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
        except subprocess.TimeoutExpired:
            return dict(status='initial_setup_capacity_timeout',accepted=False,
                 capacity_exclusion=True,physical_invalidity_proven=False,
                 timeout_seconds=timeout,wall_seconds=time.monotonic()-began),None
    if proc.returncode or not result_path.exists():
        return dict(status='physics_worker_failed',accepted=False,returncode=proc.returncode,
             physical_invalidity_proven=False,error_tail=log_path.read_text(errors='replace')[-3000:],
             wall_seconds=time.monotonic()-began),None
    result=json.loads(result_path.read_text())
    result['report']['subprocess_wall_seconds']=time.monotonic()-began
    result['report']['setup_timeout_seconds']=timeout
    return result['report'],result['poses']


def screen_case(case):
    aid=case['id']
    receipt=physics_receipt_path(aid)
    if receipt.exists():
        previous=json.loads(receipt.read_text())
        if previous['status']!='screening':return previous
        assert previous['configuration_sha256']==canonical_sha(CONFIG)
        history=AUDIT/'interrupted_physics_receipts';history.mkdir(exist_ok=True)
        i=len(list(history.glob(aid+'_*')))+1
        receipt.rename(history/f'{aid}_{i:03d}.json')
    poses,pose_notes=candidate_poses(case)
    policy=CONFIG.get('fixture_candidate_policy','lowest_grounded')
    report=dict(id=aid,status='screening',pose_candidates=poses,pose_notes=pose_notes,
        fixture_candidate_policy=policy,anchor_candidate_orders=[],
        configuration_sha256=canonical_sha(CONFIG),trials=[],selected=None,
        scope='At most one permanently world-fixed original component. No dynamic holding, anchor switching, robot or change to full n-1 endpoint.')
    dump(receipt,report)
    if any(n['kind']=='stable_pose_generation_error'for n in pose_notes):
        report['status']='pose_candidate_generation_failed';dump(receipt,report);return report
    loop_started=time.monotonic()
    case_limit=CONFIG.get('initialization_case_wall_seconds')

    def finish_capacity():
        report.update(status='initialization_case_capacity_exclusion',any_capacity_exclusion=True,
            physical_invalidity_proven=False,initialization_wall_limit_seconds=case_limit,
            initialization_elapsed_seconds=time.monotonic()-loop_started)
        dump(receipt,report);return report

    def attempt(pose,index,anchor=None):
        remaining=None if case_limit is None else case_limit-(time.monotonic()-loop_started)
        if remaining is not None and remaining<=0:return None
        trial=apply_pose(case,pose)
        fixtures=[]if anchor is None else[anchor]
        mode='natural_zero_clamp'if anchor is None else('any_single_original_anchor'if policy=='any_single_anchor'else'one_declared_original_part_clamp')
        for part in trial['parts']:part['fixed']=part['id']==anchor
        trial['base_id']=anchor
        trial['fixture_ids']=fixtures
        trial['target_id']=next(p['id']for p in trial['parts']if not p['fixed'])
        trial['physics']['base_fixture']='none'if anchor is None else'One permanently world-fixed original part '+anchor+'; external workholding assumed, may be above floor'
        if anchor is not None and isinstance(trial.get('goal'),dict):
            trial['goal']['required_remaining_id']=anchor
        suffix=''if anchor is None else'_anchor_'+anchor
        trial_path=CASES/f'.physics_{aid}_{mode}_{index:02d}{suffix}.json'
        try:result,final=timed_physical_trial(trial,trial_path,timeout_override=remaining)
        except Exception as exc:
            result,final=dict(status='physics_error',error=repr(exc),traceback=traceback.format_exc(),accepted=False),None
        result.update(mode=mode,pose=pose['label'],fixture_ids=fixtures,
            trial_case=str(trial_path.relative_to(ROOT)),trial_case_sha256=sha(trial_path)if trial_path.exists()else None)
        report['trials'].append(result);dump(receipt,report)
        event('physics_trial',id=aid,mode=mode,pose=pose['label'],anchor=anchor,status=result['status'])
        if not result['accepted']:return False
        trial['initial_poses']=final
        trial['provenance']['initial_physics_screen']=dict(report=str(receipt.relative_to(ROOT)),accepted_mode=mode,
            fixture_ids=fixtures,fixture_candidate_policy=policy,small_bounded_equilibration_only=True,
            pose_and_fixture_selected_without_actor_or_reference_path=True,
            anchor_fixed_for_entire_full_disassembly=bool(fixtures),dynamic_holding_reproduced=False)
        case_path=CASES/(aid+'.json');dump(case_path,trial)
        report.update(status='physical_valid',selected=dict(case_path=str(case_path.relative_to(ROOT)),
            case_sha256=sha(case_path),fixture_ids=fixtures,mode=mode,pose=pose['label'],
            physics_report=str(receipt.relative_to(ROOT)),initial_physics=result,candidate_protocol_complete=True,
            feasible_full_disassembly_path='unknown; not used for selection'))
        report['initialization_elapsed_seconds']=time.monotonic()-loop_started
        report['initialization_wall_limit_seconds']=case_limit
        dump(receipt,report);return True

    # Exhaust zero-anchor poses before trying any candidate permanent anchor.
    if CONFIG.get('allow_natural_zero_clamp',True):
        for i,pose in enumerate(poses):
            outcome=attempt(pose,i)
            if outcome is True:return report
            if outcome is None:return finish_capacity()
    for i,pose in enumerate(poses):
        posed=apply_pose(case,pose)
        if policy=='any_single_anchor':anchors=ordered_single_anchors(posed)
        else:
            base=grounded_base(posed);anchors=[]if base is None else[dict(id=base)]
        report['anchor_candidate_orders'].append(dict(pose=pose['label'],candidates=anchors))
        dump(receipt,report)
        for anchor in anchors:
            outcome=attempt(pose,i,anchor['id'])
            if outcome is True:return report
            if outcome is None:return finish_capacity()
    any_capacity=any(t.get('capacity_exclusion',False)for t in report['trials'])
    report.update(status=('no_initial_setup_passed_with_capacity_exclusions'if any_capacity else
        'no_initial_setup_passed_declared_zero_or_one_clamp_protocol'),
        physical_invalidity_proven=False,any_capacity_exclusion=any_capacity)
    dump(receipt,report);return report


def run(max_assemblies=None):
    global CONFIG,ASSEMBLIES,COACD_SETTINGS,CASES
    catalog=json.loads(CATALOG.read_text())
    catalog_sha=sha(CATALOG)
    reserve=catalog['declared_reserve']
    requested_count=int(CONFIG.get('requested_cases',5))
    stage_role=CONFIG.get('stage_role','evaluation')
    if not requested_count<=len(reserve)<=50 or [r['id'] for r in reserve]!=catalog['declared_reserve_ids'] or len(set(catalog['declared_reserve_ids']))!=len(reserve):
        raise ValueError('Need a unique explicitly predeclared ordered reserve of at most fifty IDs, sufficient for requested count')
    suffix='_'+RUN_NAME if RUN_NAME else ''
    if RUN_NAME:
        CONFIG=copy.deepcopy(CONFIG)
        CONFIG['version']=4 if CONFIG.get('fixture_candidate_policy')=='any_single_anchor' else(3 if CONFIG.get('asset_namespace')else 2)
        CONFIG['selection']=f'First {requested_count} physically valid IDs in this explicit source-only predeclared reserve; no path search or actor outcome gating.'
        CONFIG['cohort']=dict(run_name=RUN_NAME,catalog_path=str(CATALOG.resolve()),
                              catalog_sha256=catalog_sha,reserve_count=len(reserve))
    COACD_SETTINGS=copy.deepcopy(CONFIG['coacd'])
    if CONFIG.get('asset_namespace'):
        ASSEMBLIES=ROOT/'data/assemblies'/CONFIG['asset_namespace']
    if CONFIG.get('case_namespace'):
        CASES=ROOT/'cases'/CONFIG['case_namespace']
    config_path=AUDIT/f'conversion_config{suffix}.json'
    if config_path.exists():
        if json.loads(config_path.read_text())!=CONFIG:
            raise ValueError('Conversion configuration already frozen with different settings')
    else:
        dump(config_path,CONFIG)
    os.environ['DISASSEMBLY_REAL_CONVERSION_CONFIG']=str(config_path.resolve())
    summary_path=AUDIT/f'case_selection{suffix}.json'
    contract_path=AUDIT/(f'selected_cases_{RUN_NAME}.json'if stage_role!='evaluation'else'selected_cases.json')
    if summary_path.exists():
        saved=json.loads(summary_path.read_text())
        if saved.get('catalog_sha256')!=catalog_sha:
            raise ValueError('Catalog changed during conversion')
        if saved['status'] in ['FROZEN_FIVE_PHYSICAL_VALID_CASES','RESERVE_EXHAUSTED_FEWER_THAN_FIVE','DEVELOPMENT_PHYSICAL_SCREEN_COMPLETE']:
            if not contract_path.exists():
                dump(contract_path,selected_contract(saved))
            print('Existing final selection receipt; not rerunning.',flush=True)
            return saved
    selected_snapshot=None
    if RUN_NAME and contract_path.exists():
        selected_snapshot=AUDIT/f'selected_cases_before_{RUN_NAME}.json'
        if not selected_snapshot.exists():
            selected_snapshot.write_bytes(contract_path.read_bytes())
    started=AUDIT/f'conversion_run_started{suffix}.json'
    if started.exists():
        prior=json.loads(started.read_text())
        try:
            os.kill(prior['pid'],0)
        except ProcessLookupError:
            pass
        else:
            if prior['pid']!=os.getpid():
                raise RuntimeError('Another converter process is live; duplicate execution refused')
        history=AUDIT/f'conversion_run_previous_pid_{prior["pid"]}.json'
        if not history.exists():
            dump(history,prior)
    dump(started,dict(pid=os.getpid(),time_utc=utc(),catalog_sha256=catalog_sha,
                     configuration_sha256=canonical_sha(CONFIG),converter_sha256=sha(__file__),
                     selected_contract_snapshot=str(selected_snapshot.resolve()) if selected_snapshot else None,
                     python=sys.executable,versions={n:importlib.metadata.version(n) for n in ['trimesh','numpy','scipy','mujoco','coacd','networkx']}))
    summary=dict(status='CONVERSION_AND_INITIAL_PHYSICS_SCREENING',catalog_sha256=catalog_sha,
                 declared_order=catalog['declared_reserve_ids'],configuration_sha256=canonical_sha(CONFIG),
                 source_catalog_path=str(CATALOG.resolve()),conversion_config_path=str(config_path.resolve()),
                 selection_receipt_path=str(summary_path.resolve()),
                 selected_contract_path=str(contract_path.resolve()),requested_count=requested_count,stage_role=stage_role,
                 selection_rule=CONFIG['selection'],selected=[],considered=[],unexamined=[],
                 policy_or_library_or_model_loaded=False,feasibility_search_performed=False)
    dump(summary_path,summary)
    for index,record in enumerate(reserve):
        if max_assemblies is not None and index>=max_assemblies:
            summary['unexamined']=[r['id'] for r in reserve[index:]]
            break
        if len(summary['selected'])>=requested_count:
            summary['unexamined']=[r['id'] for r in reserve[index:]]
            break
        aid=record['case_id']
        event('conversion_assembly_started',id=aid,parts=record['part_count'])
        preparation_report=conversion_receipt_path(aid)
        try:
            provenance_keys=['source_group','source_archive_url','source_repository','source_repository_commit',
                             'official_split','source_archive_etag','source_archive_bytes',
                             'source_archive_sha256','source_archive_range_receipt','semantic_selection_receipt',
                             'upstream_split','our_use','full_archive_downloaded','full_archive_sha256',
                             'provenance','request_path','request_sha256',
                             'source_semantic_review_path','source_semantic_review_sha256']
            source_metadata={key:catalog[key] for key in provenance_keys if key in catalog}
            if 'source_group' not in source_metadata:
                source_metadata['source_group']='training_assembly' if 'training' in catalog.get('source_archive_url','') else 'test_assembly'
            manifest=normalize_source(record,catalog_sha,source_metadata)
            manifest_path=ASSEMBLIES/aid/'manifest.json'
            part_results=prepare_assembly(manifest_path)
            failures=[r for r in part_results if r['status']!='ready']
            conversion=dict(id=aid,status='conversion_rejected' if failures else 'conversion_ready',
                            manifest_sha256=sha(manifest_path),
                            hull_count=sum(r.get('hull_count',0) for r in part_results),
                            parts=sorted(part_results,key=lambda x:int(x['id'])),failures=failures)
            dump(preparation_report,conversion)
            if failures:
                considered=dict(id=record['id'],case_id=aid,status='conversion_rejected',
                                conversion_report=str(preparation_report.relative_to(ROOT)),
                                failure_statuses=[r['status'] for r in failures])
            else:
                case=make_case(manifest)
                physics=screen_case(case)
                considered=dict(id=record['id'],case_id=aid,status=physics['status'],
                                conversion_report=str(preparation_report.relative_to(ROOT)),
                                physics_report=str(physics_receipt_path(aid).relative_to(ROOT)))
                if physics['status']=='physical_valid':
                    summary['selected'].append(dict(source_assembly_id=record['id'],conversion_report=str(preparation_report.relative_to(ROOT)),**physics['selected']))
        except Exception as exc:
            considered=dict(id=record['id'],case_id=aid,status='conversion_error',
                            error=repr(exc),traceback=traceback.format_exc())
            dump(preparation_report,considered)
        summary['considered'].append(considered)
        dump(summary_path,summary)
        event('conversion_assembly_completed',id=aid,status=considered['status'],selected=len(summary['selected']))
    summary['status']=('DEVELOPMENT_PHYSICAL_SCREEN_COMPLETE'if stage_role!='evaluation'else
                       'FROZEN_FIVE_PHYSICAL_VALID_CASES' if len(summary['selected'])==5 else
                       'PAUSED_PENDING_SOURCE_SEMANTIC_REVIEW' if summary['unexamined'] else
                       'RESERVE_EXHAUSTED_FEWER_THAN_FIVE')
    summary['completed_utc']=utc()
    summary['limitations']=[
        'Uncalibrated scale/material/inertia; anonymous research CAD, no verified factory provenance.',
        'Physical-valid means initial pose passed this sampled collision and finite-horizon stability protocol.',
        'A full n-1 disassembly path may not exist under six-axis actions. Path feasibility was not a selection gate.',
        'Rejected conversions/setups retained; no redesigned parts or score-selected replacements.']
    dump(summary_path,summary)
    dump(contract_path,selected_contract(summary))
    event('conversion_selection_final',status=summary['status'],selected=len(summary['selected']))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--part-worker',nargs=2,metavar=('MANIFEST','PART_ID'))
    parser.add_argument('--physics-worker',nargs=2,metavar=('TRIAL','RESULT'))
    parser.add_argument('--max-assemblies',type=int,default=None,
                        help='Operational stop; preserves reserve, settings and selection criteria.')
    parser.add_argument('--catalog',type=Path,default=None,
                        help='Explicit newly frozen source catalog; original catalog is never replaced.')
    parser.add_argument('--run-name',default=None,
                        help='Distinct receipt namespace for a source-only cohort amendment.')
    parser.add_argument('--collision-profile',choices=['precise005','off020_uncapped'],default='precise005')
    parser.add_argument('--fixture-policy',choices=['lowest_grounded','any_single_anchor'],default='lowest_grounded')
    parser.add_argument('--stage-role',choices=['evaluation','development_only'],default='evaluation')
    parser.add_argument('--requested-cases',type=int,default=5)
    args=parser.parse_args()
    if args.part_worker:
        part_worker(*args.part_worker)
    elif args.physics_worker:
        physical_worker(*args.physics_worker)
    else:
        if args.catalog is not None:
            CATALOG=args.catalog.resolve()
            CATALOG.relative_to(ROOT)
        if args.run_name:
            if not all(ch.isalnum() or ch=='_' for ch in args.run_name):
                parser.error('--run-name accepts only letters, numbers and underscores')
            RUN_NAME=args.run_name
        if args.collision_profile=='off020_uncapped':
            if not RUN_NAME:parser.error('Amended collision profile requires distinct --run-name')
            CONFIG=copy.deepcopy(CONFIG)
            CONFIG['coacd']={**COACD_SETTINGS,'threshold':.02,'preprocess_mode':'off','max_convex_hull':-1}
            CONFIG['collision']='actual mesh.is_convex else seeded CoACD threshold0.02 uncapped; no fallback; finite original-source quality gate retained'
            CONFIG['asset_namespace']=RUN_NAME
            CONFIG['initial_setup_timeout_seconds']=60
            CONFIG['profile_adoption_development_receipt']='outputs/input_audit/collision_benchmark_02/summary.json'
        CONFIG['requested_cases']=args.requested_cases
        CONFIG['stage_role']=args.stage_role
        if args.fixture_policy=='any_single_anchor':
            if not RUN_NAME:parser.error('Amended fixture policy requires distinct --run-name')
            CONFIG['fixture_candidate_policy']='any_single_anchor'
            CONFIG['fixture_policy']='All natural poses first; then all original single permanent anchors per pose, descending mass then source volume for mass-floor ties, world XY AABB footprint, numeric ID. Above-floor anchors allowed; no second anchor, dynamic holding, or robot.'
            CONFIG['case_namespace']=RUN_NAME
            CONFIG['receipt_namespace']=RUN_NAME
        run(args.max_assemblies)

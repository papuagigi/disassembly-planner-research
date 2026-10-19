"""Frozen source-only selection; reads prior studies without executing their code.

Run with the existing environment from the workspace root and disable bytecode.
No simulator, actor, provider, model or physics module is imported here.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
ARCHIVE = WORKSPACE / "disassembly_mujoco/data/source/test_assembly.zip"
BASELINE = ROOT / "outputs/preservation/before.json"
AUDIT = ROOT / "outputs/input_audit"
SOURCE = ROOT / "data/source"
ARCHIVE_SHA256 = "c89ea240b1962e3230b00487bf23f3fcbb8b5cd7b6ce1a6816e043a31cac09c2"
URL = "https://people.csail.mit.edu/yunsheng/ASAP/dataset_2404/test_assembly.zip"
COMMIT = "3727e716b57e0b508c4e9ecd9fefa6953e8f72da"
EXPECTED_EXCLUDED_COUNT = 151
SKIP = {".venv", "node_modules", ".git", "vendor", "__pycache__", "source_snapshot"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def persist_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError(f"Refusing to replace different preserved source bytes: {path}")
    if not path.exists():
        path.write_bytes(data)


def prior_references(archive_ids, before):
    references = collections.defaultdict(set)
    extracted = set()
    for name, meta in sorted(before["files"].items()):
        path = Path(name)
        if not path.parts[0].startswith("disassembly_") or SKIP.intersection(path.parts):
            continue
        path_ids = set(re.findall(r"(?:asap_|asap_test/)(\d{5})", name)) & archive_ids
        extracted.update(path_ids)
        ids = set(path_ids)
        if path.suffix in {".json", ".py", ".md", ".txt"} and meta["bytes"] < 3_000_000:
            data = (WORKSPACE / path).read_bytes()
            if digest(data) != meta["sha256"]:
                raise RuntimeError(f"Baseline input changed before source selection: {name}")
            text = data.decode("utf-8", errors="replace")
            ids.update(re.findall(r"(?:asap_|asap_test/|test_assembly/)(\d{5})", text))
            ids.update(re.findall(r'"(?:source_assembly_id|id)"\s*:\s*"(?:asap_)?(\d{5})"', text))
        for aid in ids & archive_ids:
            references[aid].add(name)
    return references, extracted


def load_mesh(data):
    mesh = trimesh.load(io.BytesIO(data), file_type="obj", force="mesh", process=True)
    if not np.isfinite(mesh.vertices).all() or not len(mesh.faces):
        raise ValueError("Mesh must have finite vertices and at least one triangle")
    return mesh


def shape_fingerprint(mesh):
    """Permutation, rigid-transform and uniform-scale invariant heuristic signature.

    Quantization can have boundary false negatives; a match is a duplicate-review
    signal, never proof of mesh identity. Reflection is intentionally invariant.
    """
    vertices = np.asarray(mesh.vertices, dtype=float)
    centered = vertices - vertices.mean(axis=0)
    rms = float(np.sqrt(np.mean(np.sum(centered * centered, axis=1))))
    if rms <= 0:
        raise ValueError("Degenerate mesh")
    radial = np.sort(np.linalg.norm(centered, axis=1) / rms)
    triangles = vertices[np.asarray(mesh.faces)]
    edges = np.sort(np.linalg.norm(triangles - np.roll(triangles, 1, axis=1), axis=2).ravel() / rms)
    cov = np.linalg.eigvalsh(centered.T @ centered / len(vertices)) / (rms * rms)
    header = [len(vertices), len(mesh.faces)]
    hasher = hashlib.sha256(json.dumps(header).encode())
    for values in [radial, edges, cov, np.array([abs(float(mesh.volume)) / rms**3])]:
        hasher.update(np.rint(values * 1_000_000).astype("<i8").tobytes())
    return hasher.hexdigest()


def assembly_fingerprint(meshes):
    """Common rigid-transform/scale invariant shape-labeled centroid-distance hash."""
    clouds = [np.asarray(mesh.vertices) for mesh in meshes]
    vertices = np.concatenate(clouds)
    center = vertices.mean(axis=0)
    scale = float(np.sqrt(np.mean(np.sum((vertices - center) ** 2, axis=1))))
    centers = [cloud.mean(axis=0) for cloud in clouds]
    signatures = [shape_fingerprint(mesh) for mesh in meshes]
    pairs = []
    for i in range(len(meshes)):
        for j in range(i + 1, len(meshes)):
            labels = sorted([signatures[i], signatures[j]])
            distance = round(float(np.linalg.norm(centers[i] - centers[j]) / scale), 6)
            pairs.append([*labels, distance])
    payload = [sorted(signatures), sorted(pairs)]
    return digest(json.dumps(payload, separators=(",", ":")).encode())


def catalog():
    if (AUDIT / "source_catalog.json").exists():
        raise RuntimeError("Catalog already exists; use --phase novelty or --verify, never silently reselect")
    archive_bytes = ARCHIVE.read_bytes()
    if digest(archive_bytes) != ARCHIVE_SHA256:
        raise RuntimeError("Official source archive hash differs from the audited archive")
    before = json.loads(BASELINE.read_text())
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        groups = collections.defaultdict(list)
        for name in z.namelist():
            if name.endswith(".obj"):
                groups[Path(name).parent.name].append(name)
        references, extracted = prior_references(set(groups), before)
        if len(references) != EXPECTED_EXCLUDED_COUNT:
            raise RuntimeError(f"Expected 151 prior referenced IDs; found {len(references)}")
        candidates = []
        screened = []
        for aid, names in sorted(groups.items()):
            reasons = []
            if aid in references:
                reasons.append("previously_referenced_original_id")
            elif not 21 <= len(names) <= 32:
                reasons.append("outside_preregistered_21_to_32_part_bound")
            if reasons:
                screened.append({"id": aid, "part_count": len(names), "eligible": False, "reasons": reasons})
                continue
            face_count = sum(sum(line.startswith(b"f ") for line in z.read(n).splitlines()) for n in names)
            if face_count > 15_000:
                screened.append({"id": aid, "part_count": len(names), "total_faces": face_count,
                                 "eligible": False, "reasons": ["source_face_count_above_15000"]})
                continue
            parts, meshes = [], []
            for name in sorted(names, key=lambda n: int(Path(n).stem)):
                data = z.read(name)
                mesh = load_mesh(data)
                meshes.append(mesh)
                hull_volume = float(mesh.convex_hull.volume)
                part = {"id": Path(name).stem, "source_member": name,
                        "raw_relative_path": f"data/source/asap_test/{aid}/{Path(name).name}",
                        "source_sha256": digest(data), "source_bytes": len(data),
                        "vertices": len(mesh.vertices), "faces": len(mesh.faces),
                        "watertight": bool(mesh.is_watertight),
                        "connected_components": len(mesh.split(only_watertight=False)),
                        "volume": float(mesh.volume), "hull_volume": hull_volume,
                        "hull_ratio": float(mesh.volume / hull_volume) if hull_volume else 0,
                        "bounds": mesh.bounds.tolist(), "shape_fingerprint": shape_fingerprint(mesh)}
                parts.append(part)
            if not all(p["watertight"] for p in parts): reasons.append("nonwatertight_part")
            if not all(p["connected_components"] == 1 for p in parts): reasons.append("multipart_mesh_component")
            if min(p["hull_ratio"] for p in parts) <= .05: reasons.append("part_hull_ratio_not_above_0_05")
            total_faces = sum(p["faces"] for p in parts)
            if total_faces > 15_000: reasons.append("triangulated_face_count_above_15000")
            lo = np.min([p["bounds"][0] for p in parts], axis=0)
            hi = np.max([p["bounds"][1] for p in parts], axis=0)
            graph_name = f"test_assembly/{aid}/contact_graph.json"
            graph_bytes = z.read(graph_name)
            record = {"id": aid, "case_id": f"asap_{aid}", "part_count": len(parts),
                      "total_faces": total_faces, "watertight": all(p["watertight"] for p in parts),
                      "max_connected_components": max(p["connected_components"] for p in parts),
                      "min_hull_ratio": min(p["hull_ratio"] for p in parts),
                      "bounds": [lo.tolist(), hi.tolist()], "extents": (hi-lo).tolist(),
                      "assembly_geometry_fingerprint": assembly_fingerprint(meshes),
                      "contact_graph": {"source_member": graph_name,
                                        "raw_relative_path": f"data/source/asap_test/{aid}/contact_graph.json",
                                        "source_sha256": digest(graph_bytes)}, "parts": parts}
            screened.append({k: v for k, v in record.items() if k not in {"parts", "contact_graph"}} |
                            {"eligible": not reasons, "reasons": reasons})
            if not reasons: candidates.append(record)
        candidates.sort(key=lambda r: (r["total_faces"], r["id"]))
        reserve = candidates[:10]
        if len(reserve) < 10:
            raise RuntimeError("Fewer than the preregistered ten geometry-eligible reserve candidates")
        for rank, record in enumerate(candidates, 1):
            record["source_rank"] = rank
            record["declared_reserve"] = rank <= 10
        for record in reserve:
            for part in record["parts"]:
                persist_bytes(ROOT / part["raw_relative_path"], z.read(part["source_member"]))
            graph = record["contact_graph"]
            persist_bytes(ROOT / graph["raw_relative_path"], z.read(graph["source_member"]))
        license_files = []
        for name in ["ASAP_LICENSE", "Fusion360GalleryDataset_LICENSE.md", "ASAP_README.md"]:
            old = WORKSPACE / "disassembly_mujoco/data/source" / name
            data = old.read_bytes()
            persist_bytes(SOURCE / name, data)
            license_files.append({"path": f"data/source/{name}", "sha256": digest(data),
                                  "copied_from": str(old.relative_to(WORKSPACE))})
        receipt = {
            "schema_version": 1, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "study": "disassembly_real_v3", "selection_status": "source_metadata_only_prephysics_pre_actor",
            "source_repository": "https://github.com/yunshengtian/ASAP", "source_repository_commit": COMMIT,
            "source_archive": str(ARCHIVE.relative_to(WORKSPACE)), "source_archive_url": URL,
            "source_archive_sha256": ARCHIVE_SHA256, "source_archive_bytes": len(archive_bytes),
            "official_split": "ASAP test_assembly (240 assemblies; distinct from official 1906 training assemblies)",
            "official_split_evidence": "data/source/ASAP_README.md, Assembly dataset section",
            "archive_assembly_count": len(groups), "archive_obj_count": sum(map(len, groups.values())),
            "baseline_manifest": str(BASELINE.relative_to(ROOT)), "baseline_manifest_sha256": digest(BASELINE.read_bytes()),
            "previously_extracted_or_used_ids": sorted(extracted),
            "conservatively_excluded_ids": sorted(references), "previous_reference_evidence": {k: sorted(v) for k,v in sorted(references.items())},
            "rule": {"parts_min": 21, "parts_max": 32, "all_watertight": True,
                     "each_mesh_connected_components": 1, "min_signed_volume_hull_ratio_exclusive": .05,
                     "total_triangles_max": 15000, "ordering": ["total_faces", "original_id"],
                     "declared_reserve_count": 10,
                     "no_actor_outcomes_no_removal_probes_no_stability_results_used": True},
            "candidate_count": len(candidates), "ordered_eligible_candidates": candidates,
            "declared_reserve_ids": [r["id"] for r in reserve], "declared_reserve": reserve,
            "all_archive_screening_records": screened, "license_files": license_files,
            "task_endpoint": "Full disassembly: n-1 source components removed, one declared fixed base retained",
            "target_hint": {"success_criterion": False,
                            "note": "No target selection by outcomes; legacy target field may hold a deterministic source-ID hash focus only."},
            "units": "Source coordinate units not declared. Any meter normalization is a modeling assumption.",
            "limitations": ["Source CAD does not supply measured friction, density, inertia, joints or fasteners.",
                            "Published assembly IDs have no supplied manufacturer or semantic product-name mapping.",
                            "Metadata eligibility does not establish physical feasibility.",
                            "No whole-archive copy or additional download was made."]}
        write_json(AUDIT / "source_catalog.json", receipt)
        write_json(SOURCE / "index.json", {"source_catalog": "outputs/input_audit/source_catalog.json",
                   "source_catalog_sha256": digest((AUDIT / "source_catalog.json").read_bytes()),
                   "archive_sha256": ARCHIVE_SHA256, "raw_extracted_ids": receipt["declared_reserve_ids"],
                   "unmodified_source_bytes": True, "licenses": license_files})
        print("CATALOG_READY", str(AUDIT / "source_catalog.json"), receipt["declared_reserve_ids"], flush=True)
    return receipt


def novelty():
    receipt = json.loads((AUDIT / "source_catalog.json").read_text())
    before = json.loads(BASELINE.read_text())
    byte_paths = collections.defaultdict(list)
    old_meshes = {}
    groups = collections.defaultdict(list)
    shape_paths = collections.defaultdict(list)
    errors = []
    eligible_paths = []
    for name, meta in sorted(before["files"].items()):
        path = Path(name)
        if not path.parts[0].startswith("disassembly_") or path.suffix != ".obj" or SKIP.intersection(path.parts): continue
        if path.name.startswith("collision") or re.search(r"_c\d+\.obj$", path.name): continue
        eligible_paths.append(name)
        byte_paths[meta["sha256"]].append(name)
        try:
            if meta["sha256"] not in old_meshes:
                data = (WORKSPACE / path).read_bytes()
                if digest(data) != meta["sha256"]: raise ValueError("baseline hash mismatch")
                mesh = load_mesh(data)
                old_meshes[meta["sha256"]] = (mesh, shape_fingerprint(mesh))
            mesh, signature = old_meshes[meta["sha256"]]
            shape_paths[signature].append(name)
            groups[str(path.parent)].append((name, meta["sha256"]))
        except Exception as exc:
            errors.append({"path": name, "error": f"{type(exc).__name__}: {exc}"})
    old_assembly_paths = collections.defaultdict(list)
    for parent, items in groups.items():
        # Only complete candidate-sized directories can match a new source product.
        if 21 <= len(items) <= 32:
            signature = assembly_fingerprint([old_meshes[sha][0] for _, sha in items])
            old_assembly_paths[signature].append(parent)
    candidates = []
    for record in receipt["declared_reserve"]:
        components = []
        for part in record["parts"]:
            components.append({"id": part["id"], "source_sha256": part["source_sha256"],
                               "shape_fingerprint": part["shape_fingerprint"],
                               "same_bytes_prior_paths": byte_paths.get(part["source_sha256"], []),
                               "same_invariant_signature_prior_paths": shape_paths.get(part["shape_fingerprint"], [])})
        matches = old_assembly_paths.get(record["assembly_geometry_fingerprint"], [])
        candidates.append({"id": record["id"], "source_id_previously_referenced": record["id"] in receipt["conservatively_excluded_ids"],
                           "assembly_fingerprint": record["assembly_geometry_fingerprint"],
                           "same_assembly_signature_prior_directories": matches,
                           "parts": components, "components_with_byte_matches": sum(bool(p["same_bytes_prior_paths"]) for p in components),
                           "components_with_shape_signature_matches": sum(bool(p["same_invariant_signature_prior_paths"]) for p in components)})
    audit = {"schema_version": 1, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "catalog_sha256": digest((AUDIT / "source_catalog.json").read_bytes()),
             "baseline_manifest_sha256": receipt["baseline_manifest_sha256"],
             "prior_reference_count": len(receipt["conservatively_excluded_ids"]),
             "prior_reference_scan_scope": "Frozen baseline disassembly_* paths and JSON/Python/Markdown/text files under3MB; skip environments, vendor, source snapshots.",
             "old_visual_or_source_mesh_file_count": len(eligible_paths),
             "old_unique_byte_hash_meshes_loaded": len(old_meshes), "old_candidate_sized_assembly_directory_count": sum(21<=len(v)<=32 for v in groups.values()),
             "old_mesh_scan_exclusions": "collision*.obj and *_c<digits>.obj collision hulls; vendor, source_snapshot, environment directories",
             "fingerprint_method": "SHA256 of vertex/face counts and1e-6-quantized sorted vertex radii, triangle edge lengths, covariance eigenvalues and volume, normalized by vertex RMS radius. Product signature adds shape-labeled pairwise centroid distances normalized by assembly RMS radius.",
             "invariance": ["vertex/face permutation", "translation", "rotation", "reflection", "common uniform scale"],
             "interpretation": "A matching component is allowed common hardware, not automatically the same product. Matching product signature requires review. Fingerprints are heuristic, not a proof of geometric uniqueness; quantization boundaries can cause false negatives.",
             "selection_was_not_changed_after_duplicate_scan": True,
             "candidates": candidates, "read_errors": errors,
             "status": "review_required" if errors or any(c["same_assembly_signature_prior_directories"] for c in candidates) else "no_previously_referenced_id_or_matching_prior_product_signature_found"}
    write_json(AUDIT / "novelty_audit.json", audit)
    print("NOVELTY_READY", audit["status"], "old_unique_meshes", len(old_meshes), "errors", len(errors), flush=True)
    return audit


def verify():
    receipt = json.loads((AUDIT / "source_catalog.json").read_text())
    assert receipt["declared_reserve_ids"] == [r["id"] for r in receipt["ordered_eligible_candidates"][:10]]
    assert not set(receipt["declared_reserve_ids"]) & set(receipt["conservatively_excluded_ids"])
    assert len(receipt["conservatively_excluded_ids"]) == 151
    for record in receipt["declared_reserve"]:
        for part in [*record["parts"], record["contact_graph"]]:
            assert digest((ROOT / part["raw_relative_path"]).read_bytes()) == part["source_sha256"]
    assert digest(ARCHIVE.read_bytes()) == ARCHIVE_SHA256
    print("VERIFIED", len(receipt["declared_reserve_ids"]), "unmodified raw source assemblies", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["all", "catalog", "novelty"], default="all")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify: verify()
    else:
        if args.phase in {"all", "catalog"}: catalog()
        if args.phase in {"all", "novelty"}: novelty()

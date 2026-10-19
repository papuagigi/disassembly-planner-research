"""Auditable development and frozen paired LLM/library comparison.

Examples (run from the workspace):
  python -m disassembly_mujoco.study development --output PATH --cases CASE.json
  python -m disassembly_mujoco.study freeze --output PATH --cases EVAL.json --library LIB.json --development DEV_PATH
  python -m disassembly_mujoco.study evaluate --output PATH

No evaluation result is silently dropped or replaced. Freeze must follow skill
development, and every evaluated case must be absent from the development list.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import statistics
import sys

from .agent import CodexCLIProvider, MODEL, EFFORT, LIMITS, canonical_hash, solve_code, validate_library

PROJECT = Path(__file__).resolve().parent
METHODS = ("no_library", "with_library")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def utc():
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provider(folder, model=MODEL):
    return CodexCLIProvider(Path(folder) / "llm_calls", model=model, reasoning_effort=EFFORT, timeout=120)


def export_csv(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def row(result, repetition, order):
    usage = result.get("token_usage", {})
    return {"case_id": result["case_id"], "repeat": repetition, "method": result["method"],
            "order": order, "success": result["success"], "termination": result["termination"],
            "checker_calls": result["checker_calls"], "llm_calls": result["llm_calls"],
            "removed_count": result["removed_count"], "accepted_removals": result.get("accepted_removals", 0),
            "elapsed_seconds": result["elapsed_seconds"], "skill_calls": len(result.get("skill_calls", [])),
            "path_samples": sum(t.get("path_samples", 0) for t in result.get("trace", [])),
            "physics_steps": sum(t.get("physics_steps", 0) for t in result.get("trace", [])),
            "execution_steps": result.get("execution_steps", 0),
            "execution_error_turns": sum(bool(d.get("execution", {}).get("error")) for d in result.get("decisions", [])),
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
            "cached_input_tokens": usage.get("cached_input_tokens"), "provider_error": result.get("provider_error")}


def source_paths():
    paths = [p for p in PROJECT.rglob("*.py")
             if not any(x in p.relative_to(PROJECT).parts for x in ("outputs", "output", "source_snapshot", "tests", "__pycache__"))]
    paths.extend(PROJECT.parent / "disassembly_planner_2d" / "planner2d" / name
                 for name in ("llm.py", "code_runtime.py", "code_worker.py", "geometry.py"))
    return sorted(set(p.resolve() for p in paths))


def asset_paths(cases):
    # Small CAD input tree is frozen in full so mesh resolution, conversion,
    # physical configuration and case JSON cannot drift between study arms.
    folders = ["data", "cases", *[p.name for p in PROJECT.glob("prepared*") if p.is_dir()]]
    paths = [p for folder in folders
             for p in (PROJECT / folder).rglob("*") if p.is_file()
             and "__pycache__" not in p.parts and p.suffix.lower() in (".json", ".obj", ".stl", ".xml", ".npy")]
    return sorted(set([*map(Path.resolve, paths), *map(Path.resolve, cases)]))


def validate_case_list(cases):
    paths = [Path(p).resolve() for p in cases]
    identifiers = [read(p).get("id", p.stem) for p in paths]
    if len(set(paths)) != len(paths) or len(set(identifiers)) != len(paths):
        raise ValueError("case paths and case IDs must be unique")
    return paths


def development(output, cases, library=None, model=MODEL):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = validate_case_list(cases)
    lib = read(library) if library else None
    if lib is not None:
        validate_library(lib)
    record = {"phase": "development_only", "model": model, "reasoning_effort": EFFORT,
              "limits": LIMITS, "created_at_utc": utc(),
              "case_paths": [str(p) for p in cases], "case_sha256": {str(p): file_hash(p) for p in cases},
              "library": lib, "source_sha256": {str(p): file_hash(p) for p in source_paths()}}
    write(output / "development_manifest.json", record)
    rows = []
    for i, case in enumerate(cases):
        sid = read(case).get("id", case.stem)
        folder = output / sid
        folder.mkdir()
        result = solve_code(case, provider(folder, model), library=lib, **LIMITS)
        write(folder / "result.json", result)
        rows.append(row(result, 0, i + 1))
        write(output / "trial_rows.json", rows)
        print(json.dumps({"phase": "development", **rows[-1]}, ensure_ascii=False), flush=True)
    export_csv(output / "trials.csv", rows)
    return rows


def freeze(output, cases, library, development_paths, repetitions=3, model=MODEL):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = validate_case_list(cases)
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("repetitions must be positive")
    lib = read(library)
    library_hash = validate_library(lib)
    devcases, development_records = set(), {}
    for folder in development_paths:
        folder = Path(folder).resolve()
        manifest = read(folder / "development_manifest.json")
        devcases.update(manifest["case_sha256"].values())
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                development_records[str(p)] = file_hash(p)
    if not development_records:
        raise ValueError("actual development evidence is required before library freeze")
    if any(file_hash(p) in devcases for p in cases):
        raise ValueError("a heldout case was used during development")
    records = [{"path": str(p), "id": read(p).get("id", p.stem), "sha256": file_hash(p)} for p in cases]
    from .simulator import DisassemblySim
    initial_observations = {}
    for case in cases:
        snapshots = [DisassemblySim(case, max_checks=LIMITS["max_checks"], capture=False).snapshot() for _ in METHODS]
        hashes = [canonical_hash(s) for s in snapshots]
        if hashes[0] != hashes[1]:
            raise ValueError("two arms do not begin with identical observations: " + str(case))
        initial_observations[read(case).get("id", case.stem)] = hashes[0]
    sources = {str(p): file_hash(p) for p in source_paths()}
    assets = {str(p): file_hash(p) for p in asset_paths(cases)}
    versions = {}
    for name in ("mujoco", "numpy", "scipy", "trimesh", "coacd"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    manifest = {"created_at_utc": utc(), "model": model, "reasoning_effort": EFFORT,
                "limits": LIMITS, "repetitions": repetitions, "cases": records,
                "initial_observation_sha256": initial_observations,
                "library_sha256": library_hash, "source_sha256": sources, "asset_sha256": assets,
                "development_records": development_records,
                "runtime_environment": {"python": sys.version, "executable": sys.executable,
                                        "system": platform.system(), "machine": platform.machine(),
                                        "packages": versions},
                "expected_trials": len(cases) * repetitions * 2,
                "ordering": "Alternate first arm by case index + repetition; paired equal inputs and limits.",
                "budget_definition": "4 stateless LLM calls; 24 shared physics check/remove calls; 50000 generated policy+skill opcodes;120s per code turn wall time including physics. Physics work is excluded from opcode count.",
                "failure_rule": "All scheduled trials retained. Provider/worker errors count as unsuccessful and remain separately labeled; no heuristic fallback or replacement trial.",
                "heldout_rule": "No library/model/budget/source tuning after freeze. Case JSON hashes differ from declared development cases. Geometry-family novelty must be described separately; target changes alone are not new assemblies.",
                "sampling_limits": "CLI model slug/effort explicit; backend snapshot, sampling seed and temperature are not exposed. Repeats on the same CAD asset are not independent products.",
                "scope": "Small exploratory study with actual 3D OBJ geometry and assumed MuJoCo physics; no real robot or experimental material calibration."}
    manifest["manifest_sha256"] = canonical_hash(manifest)
    write(output / "library.json", lib)
    write(output / "manifest.json", manifest)
    for pstr in sources:
        p = Path(pstr)
        relative = p.relative_to(PROJECT.parent)
        dest = output / "source_snapshot" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    print(json.dumps({"phase": "frozen", "manifest_sha256": manifest["manifest_sha256"],
                      "expected_trials": manifest["expected_trials"]}), flush=True)
    return manifest


def verify_manifest(output):
    output = Path(output)
    manifest = read(output / "manifest.json")
    if canonical_hash({k: v for k, v in manifest.items() if k != "manifest_sha256"}) != manifest["manifest_sha256"]:
        raise ValueError("manifest changed after freeze")
    if validate_library(read(output / "library.json")) != manifest["library_sha256"]:
        raise ValueError("library changed after freeze")
    if set(map(str, source_paths())) != set(manifest["source_sha256"]):
        raise ValueError("runtime source file set changed after freeze")
    for group in ("source_sha256", "asset_sha256", "development_records"):
        for path, expected in manifest[group].items():
            if not Path(path).is_file() or file_hash(path) != expected:
                raise ValueError("frozen file changed: " + path)
    return manifest


def evaluate(output):
    output = Path(output).resolve()
    manifest = verify_manifest(output)
    library = read(output / "library.json")
    (output / "evaluation").mkdir(exist_ok=False)
    rows = []
    for repetition in range(1, manifest["repetitions"] + 1):
        for i, case in enumerate(manifest["cases"]):
            methods = METHODS if (i + repetition - 1) % 2 == 0 else METHODS[::-1]
            for method in methods:
                verify_manifest(output)
                folder = output / "evaluation" / case["id"] / ("repeat_%02d" % repetition) / method
                folder.mkdir(parents=True)
                try:
                    result = solve_code(case["path"], provider(folder, manifest["model"]),
                                        library=library if method == "with_library" else None,
                                        expected_observation_hash=manifest["initial_observation_sha256"][case["id"]],
                                        **manifest["limits"])
                except Exception as exc:
                    # Retain an explicit failed row even for unexpected startup
                    # failures. No retry/replacement or denominator reduction.
                    result = {"case_id": case["id"], "method": method, "success": False,
                              "termination": "trial_error", "checker_calls": 0, "llm_calls": 0,
                              "removed_count": None, "accepted_removals": 0, "elapsed_seconds": 0.0,
                              "skill_calls": [], "decisions": [], "token_usage": {},
                              "provider_error": type(exc).__name__ + ": " + str(exc)}
                result.update({"repeat": repetition, "order": len(rows) + 1,
                               "manifest_sha256": manifest["manifest_sha256"], "model": manifest["model"]})
                write(folder / "result.json", result)
                rows.append(row(result, repetition, len(rows) + 1))
                write(output / "trial_rows.json", rows)
                export_csv(output / "trials.csv", rows)
                print(json.dumps({"phase": "evaluation", **rows[-1]}, ensure_ascii=False), flush=True)
    write(output / "evaluation_complete.json", {"trials": len(rows), "completed_at_utc": utc(),
                                                "manifest_sha256": manifest["manifest_sha256"]})
    return summarize(output)


def summarize(output):
    output = Path(output).resolve()
    manifest = verify_manifest(output)
    rows = read(output / "trial_rows.json")
    expected = {(c["id"], r, m) for c in manifest["cases"]
                for r in range(1, manifest["repetitions"] + 1) for m in METHODS}
    actual = {(r["case_id"], r["repeat"], r["method"]) for r in rows}
    if actual != expected or len(rows) != len(expected):
        raise ValueError("main comparison is incomplete or duplicated")

    def stats(records):
        successful = [r for r in records if r["success"]]
        return {"trials": len(records), "successes": len(successful),
                "success_rate": len(successful) / len(records),
                "mean_checker_calls": statistics.mean(r["checker_calls"] for r in records),
                "mean_llm_calls": statistics.mean(r["llm_calls"] for r in records),
                "mean_elapsed_seconds": statistics.mean(r["elapsed_seconds"] for r in records),
                "mean_path_samples": statistics.mean(r["path_samples"] for r in records),
                "mean_physics_steps": statistics.mean(r["physics_steps"] for r in records),
                "mean_removed_success_only": statistics.mean(r["removed_count"] for r in successful) if successful else None,
                "trials_with_skill_calls": sum(r["skill_calls"] > 0 for r in records),
                "total_skill_calls": sum(r["skill_calls"] for r in records),
                "provider_error_trials": sum(bool(r["provider_error"]) for r in records),
                "execution_error_turns": sum(r["execution_error_turns"] for r in records)}

    methods = [{"method": m, **stats([r for r in rows if r["method"] == m])} for m in METHODS]
    per_case = [{"case_id": c["id"], "method": m,
                 **stats([r for r in rows if r["method"] == m and r["case_id"] == c["id"]])}
                for c in manifest["cases"] for m in METHODS]
    pairs = []
    for case in manifest["cases"]:
        for repetition in range(1, manifest["repetitions"] + 1):
            pair = {r["method"]: r for r in rows if r["case_id"] == case["id"] and r["repeat"] == repetition}
            off, on = pair["no_library"], pair["with_library"]
            pairs.append({"case_id": case["id"], "repeat": repetition,
                          "off_success": off["success"], "on_success": on["success"],
                          "on_minus_off_checks": on["checker_calls"] - off["checker_calls"],
                          "both_success": off["success"] and on["success"]})
    summary = {"manifest_sha256": manifest["manifest_sha256"], "model": manifest["model"],
               "limits": manifest["limits"], "methods": methods, "per_case": per_case, "paired": pairs,
               "interpretation_limits": ["Small fixed-case repeated trials; do not describe repeats as independent CAD products.",
                   "Library arm supplies code, catalog and optional callables; a benefit is not proof that registered function calls caused it.",
                   "Success-only removal counts are descriptive and may refer to different successful case subsets.",
                   "Lower checker counts on failed trials do not mean a more efficient successful planner."]}
    write(output / "summary.json", summary)
    export_csv(output / "summary.csv", methods)
    export_csv(output / "per_case.csv", per_case)
    export_csv(output / "paired.csv", pairs)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("development", "freeze", "evaluate", "summarize"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cases", nargs="+", type=Path)
    parser.add_argument("--library", type=Path)
    parser.add_argument("--development", nargs="+", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args()
    if args.stage in ("development", "freeze") and not args.cases:
        parser.error("--cases is required")
    if args.stage == "development":
        development(args.output, args.cases, args.library, args.model)
    elif args.stage == "freeze":
        if not args.library or not args.development:
            parser.error("freeze requires --library and --development evidence")
        freeze(args.output, args.cases, args.library, args.development, args.repetitions, args.model)
    elif args.stage == "evaluate":
        evaluate(args.output)
    else:
        summarize(args.output)


if __name__ == "__main__":
    main()

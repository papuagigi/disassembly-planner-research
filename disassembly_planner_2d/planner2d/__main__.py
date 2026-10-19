"""Local prototype CLI; no external Python packages required."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from .agent import solve_llm
from .geometry import validate_scene
from .llm import CodexCLIProvider, ProviderError, environment_status
from .scenarios import get_scene, list_scenes
from .search import solve_exact, solve_heuristic


def save_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def make_output(path: str | None, label: str) -> Path:
    folder = Path(path) if path else Path("outputs") / (datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d_%H%M%S") + "_" + label)
    if folder.exists() and any(folder.iterdir()):
        raise ValueError("Output directory is not empty; use a new directory to preserve evidence: %s" % folder)
    folder.mkdir(parents=True, exist_ok=True)
    return folder.resolve()


def _scene(args) -> dict:
    if getattr(args, "scene_file", None):
        scene = json.loads(Path(args.scene_file).read_text(encoding="utf-8"))
        validate_scene(scene)
        return scene
    return get_scene(args.scene)


def _run(scene: dict, method: str, args, output: Path) -> dict:
    if method == "exact":
        return solve_exact(scene, max_checks=args.max_checks)
    if method == "heuristic":
        return solve_heuristic(scene, max_checks=args.max_checks)
    provider = CodexCLIProvider(output / "llm_calls", model=args.model, timeout=args.timeout,
                                reasoning_effort=args.reasoning_effort)
    library = None
    if args.library:
        from .skills import verify_library
        library = json.loads(Path(args.library).read_text(encoding="utf-8"))
        verify_library(library)
    seed = None
    if getattr(args, "recovery_seed", None):
        part, direction = args.recovery_seed.split(":", 1)
        seed = [{"part_id": part, "direction": direction}]
    return solve_llm(scene, provider, args.max_calls, args.max_checks, initial_actions=seed, library=library)


def _summary(result):
    keys = ("scene_id", "method", "success", "termination", "removed_count", "checker_calls",
            "elapsed_seconds", "llm_calls", "token_usage", "provider_error", "evaluation_kind")
    return {key: result[key] for key in keys if key in result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="합성 2D 조립체의 목표 부품 회수 prototype")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="키 값 없이 환경·로그인 확인; --probe로 실제 호출")
    doctor.add_argument("--probe", action="store_true")
    doctor.add_argument("--output-dir")
    doctor.add_argument("--model")
    doctor.add_argument("--timeout", type=float, default=120)
    sub.add_parser("scenes", help="합성 사례 목록")
    for command in ("run", "demo"):
        p = sub.add_parser(command, help="단일 planner 실행" if command == "run" else "baseline과 선택적 LLM 비교 화면 생성")
        p.add_argument("--scene", default="housing_demo")
        p.add_argument("--scene-file", help="사용자 정의 scene JSON")
        p.add_argument("--output-dir")
        p.add_argument("--max-checks", type=int, default=80)
        p.add_argument("--max-calls", type=int, default=4)
        p.add_argument("--timeout", type=float, default=120)
        p.add_argument("--model", help="명시하면 Codex 모델 고정; 생략하면 설치된 CLI 기본값")
        p.add_argument("--reasoning-effort", choices=("low", "medium", "high", "xhigh", "max", "ultra"))
        p.add_argument("--library", help="검증·동결된 skill library JSON 경로")
        p.add_argument("--recovery-seed", help="PART:DIRECTION 오류 주입 연습. 정상 LLM 성능 평가와 구분")
        if command == "run":
            p.add_argument("--method", choices=("exact", "heuristic", "llm"), default="heuristic")
        else:
            p.add_argument("--with-llm", action="store_true", help="실제 Codex 호출 포함 (계정 사용량 발생)")
    batch = sub.add_parser("check-suite", help="개발 사례의 두 baseline 실행; LLM 호출 없음")
    batch.add_argument("--split", choices=("development", "evaluation", "all"), default="development")
    batch.add_argument("--max-checks", type=int, default=10000)
    batch.add_argument("--output-dir")
    args = parser.parse_args(argv)
    try:
        if args.command == "scenes":
            for scene in list_scenes():
                print("%s\t%s\t%s" % (scene["id"], scene["split"], scene["name"]))
            return 0
        if args.command == "doctor":
            status = environment_status()
            if args.probe:
                output = make_output(args.output_dir, "doctor")
                try:
                    response, metadata = CodexCLIProvider(output / "llm_calls", args.model, args.timeout).probe()
                    status["live_probe"] = {"success": response == {"status": "ok"}, "response": response, "metadata": metadata}
                except (ProviderError, OSError) as exc:
                    status["live_probe"] = {"success": False, "error": str(exc)}
                status["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
                save_json(output / "environment.json", status)
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 0 if not args.probe or status["live_probe"]["success"] else 2
        if args.command == "check-suite":
            output = make_output(args.output_dir, "suite")
            rows = []
            for scene in list_scenes():
                if args.split != "all" and scene["split"] != args.split:
                    continue
                for solver in (solve_exact, solve_heuristic):
                    result = solver(scene, max_checks=args.max_checks)
                    save_json(output / (scene["id"] + "_" + result["method"] + ".json"), result)
                    rows.append(_summary(result))
            save_json(output / "summary.json", rows)
            with (output / "summary.csv").open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["scene_id"])
                writer.writeheader()
                writer.writerows(rows)
            print(json.dumps({"results": rows, "output": str(output)}, ensure_ascii=False, indent=2))
            return 0
        from .report import write_report
        scene = _scene(args)
        output = make_output(args.output_dir, scene["id"])
        save_json(output / "scene.json", scene)
        methods = [args.method] if args.command == "run" else ["exact", "heuristic"] + (["llm"] if args.with_llm else [])
        results = []
        for method in methods:
            result = _run(scene, method, args, output)
            result["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
            save_json(output / (method + ".json"), result)
            results.append(result)
            print(json.dumps(_summary(result), ensure_ascii=False), flush=True)
        save_json(output / "results.json", results)
        page = write_report(scene, results, output / "viewer.html")
        print("Viewer: " + str(page))
        return 2 if any(r.get("provider_error") for r in results) else 0
    except (ValueError, KeyError, OSError, ProviderError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

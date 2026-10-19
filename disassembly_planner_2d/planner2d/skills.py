"""ASPIRE-inspired external guidance distilled from development executions.

This module executes no skill code and solves no evaluation scene. Admission
replays source demonstrations with the trusted geometry checker and lints the
candidate guidance for concrete identifiers/coordinates. A successful replay
validates the demonstration, NOT the efficacy or generality of its prose.
Those claims require separate held-out experiments.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy

from .geometry import apply_action, initial_state, is_goal, validate_scene


_TEXT_FIELDS = ("name", "trigger", "procedure", "cautions")
_CANDIDATE_FIELDS = frozenset(_TEXT_FIELDS + ("source_scene_ids",))
VALIDATION_SCOPE = (
    "Trusted checker replay verifies the cited development demonstrations only. "
    "It does not prove that the natural-language skill causes success, is optimal, "
    "or generalizes. Skill efficacy is assessed separately on held-out scenes."
)
CANDIDATE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["skills"],
    "properties": {"skills": {
        "type": "array", "minItems": 1, "maxItems": 8,
        "items": {
            "type": "object", "additionalProperties": False,
            "required": list(_TEXT_FIELDS) + ["source_scene_ids"],
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 100},
                "trigger": {"type": "string", "minLength": 1, "maxLength": 500},
                "procedure": {"type": "array", "minItems": 1, "maxItems": 6,
                              "items": {"type": "string", "minLength": 1, "maxLength": 500}},
                "cautions": {"type": "array", "minItems": 1, "maxItems": 5,
                             "items": {"type": "string", "minLength": 1, "maxLength": 500}},
                "source_scene_ids": {"type": "array", "minItems": 1, "maxItems": 8,
                                     "items": {"type": "string"}},
            },
        },
    }},
}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _scene_map(scenes):
    values = list(scenes.values()) if isinstance(scenes, dict) else list(scenes)
    result = {}
    for scene in values:
        validate_scene(scene)
        if scene["id"] in result:
            raise ValueError("duplicate source scene id: " + scene["id"])
        result[scene["id"]] = scene
    return result


def _audit_source(run, scene):
    """Recompute complete sequential trajectories, including rejected actions."""
    if scene["split"] != "development":
        raise ValueError("skills may use development scenes only: " + scene["id"])
    if run.get("success") is not True:
        raise ValueError("skill evidence must be a successful run: " + scene["id"])
    actions, trace = run.get("actions"), run.get("trace")
    if not isinstance(actions, list) or not actions or not isinstance(trace, list) or not trace:
        raise ValueError("source needs actions and a nonempty sequential trace")
    remaining = initial_state(scene)
    replay_trace, accepted = [], []
    for entry in trace:
        if not isinstance(entry, dict) or is_goal(scene, remaining):
            raise ValueError("invalid source trace or actions after target recovery")
        if entry.get("remaining_before") != sorted(remaining):
            raise ValueError("source trace state is inconsistent or branches")
        action = entry.get("action")
        if not isinstance(action, dict) or set(action) != {"part_id", "direction"}:
            raise ValueError("source action must contain part_id and direction only")
        after, check = apply_action(scene, remaining, action)
        if entry.get("check") != check or entry.get("remaining_after") != sorted(after):
            raise ValueError("source trace disagrees with trusted checker replay")
        replay_trace.append({"remaining_before": sorted(remaining), "action": deepcopy(action),
                             "check": check, "remaining_after": sorted(after)})
        if check["valid"]:
            accepted.append(deepcopy(action))
        remaining = after
    if not is_goal(scene, remaining) or actions != accepted:
        raise ValueError("source actions do not match a successful target-recovery trace")
    return {
        "scene_id": scene["id"], "split": "development",
        "scene_sha256": _digest(scene), "run_sha256": _digest(run),
        "reported_provider": run.get("provider", "not_reported"),
        "reported_provenance": run.get("provenance", "not_reported"),
        "reported_evaluation_kind": run.get("evaluation_kind", "not_reported"),
        "replayed_success": True, "replayed_checker_calls": len(replay_trace),
        "replayed_failures": sum(not item["check"]["valid"] for item in replay_trace),
        "replayed_removals": len(accepted), "replayed_trace": replay_trace,
    }


def _prepare_sources(development_runs, scenes):
    scene_by_id = _scene_map(scenes)
    sources = {}
    for run in development_runs:
        if not isinstance(run, dict) or run.get("scene_id") not in scene_by_id:
            raise ValueError("source run has no matching known scene")
        sid = run["scene_id"]
        if sid in sources:
            raise ValueError("use one source run per scene: " + sid)
        sources[sid] = _audit_source(run, scene_by_id[sid])
    if not sources:
        raise ValueError("at least one development execution is required")
    return scene_by_id, sources


def discovery_prompt(development_runs, scenes):
    """Create a distillation request using only audited DEVELOPMENT evidence."""
    scene_by_id, sources = _prepare_sources(development_runs, scenes)
    evidence = []
    for sid in sorted(sources):
        scene = scene_by_id[sid]
        evidence.append({"source_scene_id": sid, "workspace": scene["workspace"],
                         "target_id": scene["target_id"],
                         "parts": [{key: part[key] for key in
                                   ("id", "rects", "allowed_directions", "fixed")}
                                   for part in scene["parts"]],
                         "trusted_replayed_trace": sources[sid]["replayed_trace"]})
    return (
        "Distill a small reusable skill library from the DEVELOPMENT evidence below. "
        "Use only this supplied evidence. Do not use tools, files, network, or code execution. "
        "Skills are natural-language in-context guidance for a geometric disassembly planner. "
        "Return only the required JSON. Each skill needs name, trigger, procedure, cautions, "
        "and source_scene_ids. Give two to four distinct operational strategies supported by "
        "these traces, not complete scene solutions. Do not invent observed failures. "
        "In name/trigger/procedure/cautions use abstract roles such as target, blocker, fixed "
        "component, permitted route. Do not use any concrete part identifier except the generic "
        "word target. Do not include scene IDs, digits, numerical coordinates, code, JSON actions, "
        "or fixed action sequences in these guidance fields. Put exact supporting scene IDs "
        "ONLY in source_scene_ids. Explain when a strategy is useful and its limits; do not claim "
        "optimality or generalization from these demonstrations. The external checker remains "
        "authoritative. This is an ASPIRE-inspired restricted adaptation, without executable "
        "skills, neural weight updates, or evolutionary search.\nDEVELOPMENT EVIDENCE:\n"
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _text(value, maximum, field):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("invalid skill " + field)
    return value.strip()


def _validate_candidate(candidate, scene_by_id, sources):
    if not isinstance(candidate, dict) or set(candidate) != _CANDIDATE_FIELDS:
        raise ValueError("candidate skill has unexpected or missing fields")
    skill = {"name": _text(candidate["name"], 100, "name"),
             "trigger": _text(candidate["trigger"], 500, "trigger")}
    for field, maximum in (("procedure", 6), ("cautions", 5)):
        values = candidate[field]
        if not isinstance(values, list) or not 1 <= len(values) <= maximum:
            raise ValueError("invalid skill " + field)
        skill[field] = [_text(value, 500, field) for value in values]
    cited = candidate["source_scene_ids"]
    if (not isinstance(cited, list) or not 1 <= len(cited) <= 8
            or any(not isinstance(sid, str) or sid not in sources for sid in cited)
            or len(set(cited)) != len(cited)):
        raise ValueError("skill must cite unique audited development source IDs")
    guidance = " ".join([skill["name"], skill["trigger"]] + skill["procedure"] + skill["cautions"])
    if re.search(r"\d|[`{}\[\]]", guidance):
        raise ValueError("guidance must not contain numeric literals or code/JSON syntax")
    # Conservative lint: use role nouns instead of concrete source identifiers.
    forbidden = set(scene_by_id)
    for scene in scene_by_id.values():
        forbidden.update(part["id"] for part in scene["parts"] if part["id"] != "target")
    for identifier in forbidden:
        if re.search(r"(?<!\w)" + re.escape(identifier) + r"(?!\w)", guidance, re.I):
            raise ValueError("guidance contains concrete identifier: " + identifier)
    skill["source_scene_ids"] = sorted(cited)
    skill["admission"] = "source_trajectory_replayed_and_guidance_linted"
    return skill


def build_library(development_runs, scenes, candidate_skills, discovery_metadata=None):
    """Admit generated candidates, audit source traces, and freeze one snapshot.

    No candidate is selected using evaluation outcomes. The caller must also
    keep subsequent evaluation traces out of its discovery prompt. The digest
    is a content-integrity check, not an authentication signature.
    """
    scene_by_id, sources = _prepare_sources(development_runs, scenes)
    if not isinstance(candidate_skills, list) or not 1 <= len(candidate_skills) <= 8:
        raise ValueError("library requires between one and eight candidate skills")
    skills = [_validate_candidate(candidate, scene_by_id, sources) for candidate in candidate_skills]
    if len({skill["name"].casefold() for skill in skills}) != len(skills):
        raise ValueError("skill names must be unique")
    cited = {sid for skill in skills for sid in skill["source_scene_ids"]}
    payload = {
        "schema_version": 1, "kind": "aspire_inspired_natural_language_guidance",
        "frozen": True, "source_split": "development", "retrieval": "all_small_library_no_solver",
        "validation_scope": VALIDATION_SCOPE,
        "generalization_verified": False,
        "discovery_metadata": deepcopy(discovery_metadata) if discovery_metadata is not None
                              else {"candidate_author": "unspecified"},
        "skills": skills, "source_audits": [sources[sid] for sid in sorted(cited)],
    }
    payload["sha256"] = _digest(payload)
    return payload


def verify_library(library):
    """Raise for a changed snapshot; return its frozen content digest."""
    if not isinstance(library, dict) or library.get("schema_version") != 1:
        raise ValueError("unsupported skill library")
    payload = {key: value for key, value in library.items() if key != "sha256"}
    if library.get("sha256") != _digest(payload):
        raise ValueError("skill library integrity check failed")
    if (library.get("frozen") is not True or library.get("source_split") != "development"
            or library.get("retrieval") != "all_small_library_no_solver"
            or not isinstance(library.get("skills"), list) or not library["skills"]):
        raise ValueError("invalid frozen library contract")
    return library["sha256"]


def prompt_guidance(library):
    """Return generalized prose only. No source geometry, IDs, or traces escape."""
    verify_library(library)
    guidance = [{field: deepcopy(skill[field]) for field in _TEXT_FIELDS}
                for skill in library["skills"]]
    return (
        "FROZEN DEVELOPMENT-DERIVED SKILL LIBRARY:\n"
        "These optional strategies were distilled from successful development executions. "
        "Source executions were independently replayed, but the prose is not a correctness "
        "proof or a reference plan for this scene. Apply only when supported by the current "
        "observation and feedback. The external checker is authoritative. All small-library "
        "entries are supplied; retrieval performs no geometry checks or hidden solving.\n"
        + json.dumps(guidance, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )

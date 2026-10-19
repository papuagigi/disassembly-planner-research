"""Failure-derived procedural guidance, adapted from ASPIRE section 2.2.

Only the development pipeline replays source geometry. At evaluation time the
adapter appends frozen text, without executing its code sketches or computing
features, blockers, feasible actions, or plans. Replay validates the evidence,
not the efficacy or generality of the generated procedure.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy

from .geometry import apply_action, initial_state, is_goal, validate_scene
from .llm import parse_plan


GUIDANCE_FIELDS = ("name", "failure_signature", "applicability", "procedure",
                   "verification", "stop_conditions", "code_sketch")
_FIELDS = frozenset(GUIDANCE_FIELDS + ("source_refs",))
VALIDATION_SCOPE = (
    "Independent replay verifies actual source failures and successful LLM repair "
    "trajectories. It does not prove the prose or unexecuted code sketches are "
    "correct, optimal, effective, or generalizable. Held-out evaluation is separate."
)


def _string(maximum):
    return {"type": "string", "minLength": 1, "maxLength": maximum}


def _strings(maximum_items, maximum_length):
    return {"type": "array", "minItems": 1, "maxItems": maximum_items,
            "items": _string(maximum_length)}


CANDIDATE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["skills"],
    "properties": {"skills": {
        "type": "array", "minItems": 1, "maxItems": 6,
        "items": {"type": "object", "additionalProperties": False,
                  "required": list(GUIDANCE_FIELDS) + ["source_refs"],
                  "properties": {
                      "name": _string(100),
                      "failure_signature": _string(500),
                      "applicability": _string(500),
                      "procedure": _strings(8, 700),
                      "verification": _strings(4, 500),
                      "stop_conditions": _strings(4, 500),
                      "code_sketch": {"type": "string", "maxLength": 1800},
                      "source_refs": _strings(24, 150),
                  }},
    }},
}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _replay(scene, run):
    """Recompute every sequential check and its link to an LLM decision."""
    validate_scene(scene)
    if run.get("scene_id") != scene["id"]:
        raise ValueError("source scene and run IDs differ")
    if run.get("provider") != "codex_cli_live":
        raise ValueError("source must report an actual codex_cli_live execution")
    if run.get("provider_error"):
        raise ValueError("provider errors cannot serve as repair evidence")
    trace, decisions = run.get("trace"), run.get("decisions")
    if not isinstance(trace, list) or not trace or not isinstance(decisions, list) or not decisions:
        raise ValueError("source needs a nonempty trace and actual LLM decisions")
    by_call = {}
    for decision in decisions:
        call = decision.get("call")
        if type(call) is not int or call < 1 or call in by_call:
            raise ValueError("source decisions require unique positive call indices")
        parse_plan(decision["response"])
        meta = decision.get("metadata", {})
        if (meta.get("provider") != "codex_cli_live" or meta.get("tool_activity_count") != 0
                or meta.get("error") or meta.get("returncode") != 0):
            raise ValueError("source decision lacks clean tool-free live metadata")
        by_call[call] = decision
    remaining, accepted, replayed, offsets = initial_state(scene), [], [], {}
    last_call, rejected_calls = 0, set()
    for entry in trace:
        if not isinstance(entry, dict) or is_goal(scene, remaining):
            raise ValueError("invalid trace entry or action after target recovery")
        if entry.get("remaining_before") != sorted(remaining):
            raise ValueError("source trace state is inconsistent")
        action = entry.get("action")
        if not isinstance(action, dict) or set(action) != {"part_id", "direction"}:
            raise ValueError("source action must have part_id and direction only")
        call, source = entry.get("llm_call"), entry.get("proposal_source")
        if source != "scripted_recovery_seed":
            if source != "codex_cli_live" or call not in by_call:
                raise ValueError("source action lacks an actual LLM decision")
            if call < last_call or call in rejected_calls:
                raise ValueError("source executes an action after its call was rejected or reordered")
            last_call = call
            offset = offsets.get(call, 0)
            proposal = by_call[call]["response"]["actions"]
            if offset >= len(proposal) or proposal[offset] != action:
                raise ValueError("trace action differs from the recorded LLM proposal")
            offsets[call] = offset + 1
        elif call != 0 or any(item["proposal_source"] != "scripted_recovery_seed" for item in replayed):
            raise ValueError("scripted recovery seed must be an initial call-zero prefix")
        after, check = apply_action(scene, remaining, action)
        if entry.get("check") != check or entry.get("remaining_after") != sorted(after):
            raise ValueError("source disagrees with trusted checker replay")
        replayed.append({"remaining_before": sorted(remaining), "action": deepcopy(action),
                         "check": check, "remaining_after": sorted(after),
                         "proposal_source": source, "llm_call": call})
        if check["valid"]:
            accepted.append(deepcopy(action))
        elif source != "scripted_recovery_seed":
            rejected_calls.add(call)
        remaining = after
    success = is_goal(scene, remaining)
    if run.get("success") is not success or run.get("actions") != accepted:
        raise ValueError("source actions or success disagree with replay")
    if "remaining" in run and run["remaining"] != sorted(remaining):
        raise ValueError("source final remaining state disagrees with replay")
    return {"success": success, "replayed_trace": replayed,
            "replayed_failures": sum(not item["check"]["valid"] for item in replayed),
            "replayed_checker_calls": len(replayed), "replayed_removals": len(accepted),
            "run_sha256": _digest(run),
            "models": sorted({str(item["metadata"].get("requested_model")) for item in decisions})}


def repair_seed(failed_run):
    """Replay the observed prefix through its first rejection in development.

    The resulting scripted seed is not scored as LLM performance. Evidence
    admission separately checks that its origin was a real LLM failure.
    """
    seed = []
    for entry in failed_run.get("trace", []):
        seed.append(deepcopy(entry["action"]))
        if entry["check"]["valid"] is False:
            if len(seed) > 12:
                raise ValueError("observed first-failure prefix exceeds the plan schema")
            return seed
    raise ValueError("source run contains no rejected action")


def repair_prompt(scene, failed_run):
    """A development-only diagnosis prompt; no oracle solution is included."""
    audit = _replay(scene, failed_run)
    if not audit["replayed_failures"]:
        raise ValueError("repair requires an actual observed rejection")
    return (
        "DEVELOPMENT REPAIR CONTEXT: This task replays an actual prior LLM failure. "
        "The observed action prefix through its first rejection has already been replayed. "
        "Use the CURRENT observation and checker feedback in the base prompt as authoritative. "
        "Diagnose the rejection, form a specific repair hypothesis, and propose a corrected "
        "continuation. Retain already accepted removals. Do not copy the rest of the failed "
        "plan, invent a successful result, use tools, or execute code.\n"
        + json.dumps({"observed_failure_prefix": audit["replayed_trace"][:len(repair_seed(failed_run))]},
                     ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def audit_evidence(evidence):
    """Audit promoted development evidence; the caller owns split isolation.

    Input records have source_id, scene, failed_run, repair_run. Prior evaluation
    cases may be explicitly reused as development for a NEW held-out benchmark;
    their original split labels are preserved in this provenance record.
    """
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("nonempty failure-repair evidence is required")
    audits, seen = [], set()
    for record in evidence:
        if not isinstance(record, dict) or set(record) != {"source_id", "scene", "failed_run", "repair_run"}:
            raise ValueError("evidence requires source_id, scene, failed_run, repair_run only")
        source_id = record["source_id"]
        if not isinstance(source_id, str) or not source_id or len(source_id) > 150 or source_id in seen:
            raise ValueError("evidence source IDs must be unique nonempty strings")
        seen.add(source_id)
        scene, failed, repair = record["scene"], record["failed_run"], record["repair_run"]
        before, after = _replay(scene, failed), _replay(scene, repair)
        if before["success"] or not before["replayed_failures"]:
            raise ValueError("failure source must be unsuccessful with an actual rejected action")
        if any(t["proposal_source"] != "codex_cli_live" for t in before["replayed_trace"]):
            raise ValueError("failure source cannot originate from a scripted seed")
        if not after["success"]:
            raise ValueError("repair must recover the target under independent replay")
        seed = repair_seed(failed)
        repair_trace = after["replayed_trace"]
        seeded = [t for t in repair_trace if t["proposal_source"] == "scripted_recovery_seed"]
        if [t["action"] for t in seeded] != seed:
            raise ValueError("repair must replay the exact original prefix through first failure")
        if not any(t["proposal_source"] == "codex_cli_live" and t["check"]["valid"] for t in repair_trace[len(seed):]):
            raise ValueError("repair must contain a successful actual LLM continuation")
        audits.append({"source_id": source_id, "scene_id": scene["id"],
                       "source_role": "promoted_development", "original_split": scene["split"],
                       "scene_sha256": _digest(scene), "failure": before, "repair": after,
                       "seed_matches_actual_failure": True})
    return audits


def discovery_prompt(evidence, revision_feedback=None):
    """Build actor-report/coordinator distillation from validated repairs only."""
    audits = audit_evidence(evidence)
    sources = []
    for record, audit in zip(evidence, audits):
        scene = record["scene"]
        sources.append({"source_ref": record["source_id"], "workspace": scene["workspace"],
                        "target_id": scene["target_id"],
                        "parts": [{key: part[key] for key in
                                   ("id", "rects", "allowed_directions", "fixed")}
                                  for part in scene["parts"]],
                        "failed_trace": audit["failure"]["replayed_trace"],
                        "validated_repair_trace": audit["repair"]["replayed_trace"]})
    prompt = (
        "Act as the ASPIRE-style skill coordinator. Induce compact reusable repair procedures "
        "from the supplied actual failure traces and checker-validated repairs. This adapts "
        "ASPIRE section 2.2: failure signature, when-to-apply condition, repair strategy, and "
        "optional representative code sketch. Return only JSON matching the schema. Use no "
        "tools, files, network, or code execution. Produce two to four distinct skills grounded "
        "in these records. Give ordered operational steps, explicit intermediate computations "
        "or state updates, verification conditions, and stop/escalation conditions. Identify "
        "what the failed reasoning missed and what changed in its validated continuation. "
        "Generic slogans such as 'avoid collisions' are insufficient. You may express generic "
        "interval formulas, strict inequalities, dependency traversal, cycle detection, and "
        "state bookkeeping in pseudocode when supported by evidence; sketches are in-context "
        "guidance only and will NEVER be executed. Distinguish strict overlap from boundary "
        "contact and full rectangle unions from their bounding boxes. Do not claim that a "
        "procedure was executed merely because its source repair passed. Do not claim optimality. "
        "Use role variables (target, blocker, component, direction), never actual scene or part "
        "identifiers, numeric scene coordinates, hard-coded paths, or solved action sequences "
        "in guidance. Generic constants zero and one and numbered procedure steps are allowed. "
        "Exact source IDs belong ONLY in source_refs. code_sketch may be empty. Keep the entire "
        "library compact, preferably below 5500 characters of guidance. No held-out evidence "
        "is supplied or may be inferred.\nVALIDATED DEVELOPMENT EVIDENCE:\n"
        + json.dumps(sources, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if revision_feedback is not None:
        prompt += "\nDEVELOPMENT-ONLY REVISION FEEDBACK:\n" + json.dumps(revision_feedback, ensure_ascii=False)
    return prompt


def _text(value, maximum, field, empty=False):
    if not isinstance(value, str) or (not value.strip() and not empty) or len(value) > maximum:
        raise ValueError("invalid procedure field: " + field)
    return value.strip()


def _validate_candidate(candidate, evidence, audits):
    if not isinstance(candidate, dict) or set(candidate) != _FIELDS:
        raise ValueError("candidate has unexpected or missing fields")
    skill = {field: _text(candidate[field], maximum, field, field == "code_sketch")
             for field, maximum in (("name", 100), ("failure_signature", 500),
                                    ("applicability", 500), ("code_sketch", 1800))}
    for field, maximum_items, maximum_length in (("procedure", 8, 700), ("verification", 4, 500),
                                                 ("stop_conditions", 4, 500)):
        values = candidate[field]
        if not isinstance(values, list) or not 1 <= len(values) <= maximum_items:
            raise ValueError("invalid procedure array: " + field)
        skill[field] = [_text(value, maximum_length, field) for value in values]
    cited = candidate["source_refs"]
    source_ids = {audit["source_id"] for audit in audits}
    if (not isinstance(cited, list) or not 1 <= len(cited) <= 24
            or any(not isinstance(ref, str) or ref not in source_ids for ref in cited)
            or len(cited) != len(set(cited))):
        raise ValueError("source_refs must cite unique audited repair IDs")
    text_fields = []
    for field in GUIDANCE_FIELDS:
        text_fields.extend(skill[field] if isinstance(skill[field], list) else [skill[field]])
    guidance = "\n".join(text_fields)
    forbidden = set(source_ids)
    for record in evidence:
        scene = record["scene"]
        forbidden.add(scene["id"])
        forbidden.update(part["id"] for part in scene["parts"] if part["id"] != "target")
    for identifier in forbidden:
        if re.search(r"(?<!\w)" + re.escape(identifier) + r"(?!\w)", guidance, re.I):
            raise ValueError("guidance contains concrete source identifier: " + identifier)
    # Permit algorithmic constants, generic array indices, and numbered steps;
    # reject coordinate vectors, decimals, large literals and serialized plans.
    if re.search(r"\[\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+", guidance):
        raise ValueError("guidance contains a numeric coordinate/list literal")
    if re.search(r"(?<![\w.])-?\d+\.\d+|(?<![\w.])\d{2,}(?!\w)", guidance):
        raise ValueError("guidance contains a scene-like numeric literal")
    for match in re.finditer(r"(?<!\w)[2-9](?!\w)", guidance):
        start, end = match.span()
        prefix, suffix = guidance[:start], guidance[end:]
        is_array_index = prefix.endswith("[") and suffix.startswith("]")
        is_step_number = not prefix.split("\n")[-1].strip() and re.match(r"[.)]\s", suffix)
        if not is_array_index and not is_step_number:
            raise ValueError("numeric constants must be generic zero/one, indices, or numbered steps")
    if re.search(r'["\'](?:part_id|actions)["\']\s*:', guidance):
        raise ValueError("guidance contains a serialized action or solved sequence")
    if re.search(r"\b(?:import|subprocess|requests|socket)\b|\b(?:exec|eval|open)\s*\(|\bos\.", guidance):
        raise ValueError("guidance contains a forbidden external/tool execution API")
    skill["source_refs"] = sorted(cited)
    skill["admission"] = "actual_failure_and_successful_repair_replayed_guidance_linted"
    return skill


def build_library(evidence, candidate_skills, discovery_metadata=None):
    audits = audit_evidence(evidence)
    if not isinstance(candidate_skills, list) or not 1 <= len(candidate_skills) <= 6:
        raise ValueError("library requires between one and six skills")
    skills = [_validate_candidate(candidate, evidence, audits) for candidate in candidate_skills]
    if len({skill["name"].casefold() for skill in skills}) != len(skills):
        raise ValueError("skill names must be unique")
    cited = {ref for skill in skills for ref in skill["source_refs"]}
    payload = {"schema_version": 2, "kind": "aspire_inspired_failure_repair_procedures",
               "frozen": True, "source_role": "promoted_development",
               "retrieval": "all_small_library_no_solver", "code_execution": False,
               "validation_scope": VALIDATION_SCOPE, "generalization_verified": False,
               "discovery_metadata": deepcopy(discovery_metadata or {"candidate_author": "unspecified"}),
               "skills": skills, "source_audits": [a for a in audits if a["source_id"] in cited]}
    payload["sha256"] = _digest(payload)
    return payload


def verify_library(library):
    if not isinstance(library, dict) or library.get("schema_version") != 2:
        raise ValueError("unsupported procedural library")
    if library.get("sha256") != _digest({k: v for k, v in library.items() if k != "sha256"}):
        raise ValueError("procedural library integrity check failed")
    if (library.get("kind") != "aspire_inspired_failure_repair_procedures"
            or library.get("frozen") is not True or library.get("code_execution") is not False
            or library.get("source_role") != "promoted_development"
            or library.get("retrieval") != "all_small_library_no_solver"
            or not isinstance(library.get("skills"), list) or not library["skills"]):
        raise ValueError("invalid frozen procedural library contract")
    return library["sha256"]


def prompt_guidance(library):
    verify_library(library)
    guidance = [{field: deepcopy(skill[field]) for field in GUIDANCE_FIELDS}
                for skill in library["skills"]]
    return (
        "FROZEN FAILURE-DERIVED PROCEDURAL SKILL LIBRARY:\n"
        "These compact procedures were induced from actual development failures and validated "
        "repairs. Their source trajectories passed independent replay; this is not a proof of "
        "the procedures. All entries are supplied without geometry checks or hidden solving. "
        "Apply a procedure only when its failure signature and applicability match the current "
        "observation. Procedure list order defines its numbered steps. Code sketches are "
        "reasoning guidance only: do not execute code or invoke tools. Recompute roles and "
        "dependencies for this observation. The external checker remains authoritative.\n"
        + json.dumps(guidance, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


class ProceduralProvider:
    """Append-only guidance adapter; the same provider/checker/budgets remain."""

    def __init__(self, provider, library):
        self.provider = provider
        self.name = provider.name
        self.library = deepcopy(library)
        self.sha256 = verify_library(self.library)
        self.guidance = prompt_guidance(self.library)

    def propose(self, prompt, call_index):
        verify_library(self.library)
        appended = prompt + "\n\n" + self.guidance
        value, metadata = self.provider.propose(appended, call_index)
        metadata = deepcopy(metadata)
        metadata["procedural_library"] = {
            "sha256": self.sha256, "entries_supplied": len(self.library["skills"]),
            "injection": "append_only", "base_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "guidance_sha256": hashlib.sha256(self.guidance.encode()).hexdigest(),
            "effective_prompt_sha256": hashlib.sha256(appended.encode()).hexdigest(),
            "code_executed": False, "additional_geometry_checks": 0}
        return value, metadata

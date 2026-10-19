"""Bounded Codex CLI inference. Credentials are never read or copied by this module."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Any


class ProviderError(RuntimeError):
    """Inference failed; callers must not silently substitute a heuristic."""


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "actions": {"type": "array", "minItems": 1, "maxItems": 12,
                    "items": {"type": "object", "properties": {
                        "part_id": {"type": "string"},
                        "direction": {"type": "string", "enum": ["up", "down", "left", "right"]}},
                        "required": ["part_id", "direction"], "additionalProperties": False}},
        "summary": {"type": "string"}},
    "required": ["actions", "summary"], "additionalProperties": False}

PROBE_SCHEMA = {"type": "object", "properties": {"status": {"type": "string", "enum": ["ok"]}},
                "required": ["status"], "additionalProperties": False}


def parse_plan(value: Any) -> dict:
    if not isinstance(value, dict) or set(value) != {"actions", "summary"}:
        raise ProviderError("Expected only actions and summary in the LLM response")
    if not isinstance(value["summary"], str):
        raise ProviderError("summary must be a string")
    actions = value["actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 12:
        raise ProviderError("actions must contain 1 to 12 entries")
    for action in actions:
        if (not isinstance(action, dict) or set(action) != {"part_id", "direction"}
                or not isinstance(action["part_id"], str) or not action["part_id"]
                or action["direction"] not in ("up", "down", "left", "right")):
            raise ProviderError("Malformed action in LLM response")
    return value


def environment_status() -> dict:
    executable = shutil.which("codex")
    status = {"codex_executable": executable,
              "api_key_environment_presence": {key: bool(os.environ.get(key)) for key in (
                  "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
                  "AZURE_OPENAI_API_KEY", "OPENROUTER_API_KEY")},
              "credentials_read": False}
    if executable:
        try:
            completed = subprocess.run([executable, "login", "status"], capture_output=True,
                                       text=True, timeout=15)
            text = completed.stdout + completed.stderr
            status["logged_in"] = completed.returncode == 0
            status["authentication"] = "ChatGPT" if "using ChatGPT" in text else "unknown"
            version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10)
            status["codex_version"] = version.stdout.strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            status["error"] = type(exc).__name__
    return status


def _decode_events(stdout: str) -> tuple[list[dict], dict]:
    events, usage = [], {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
    return events, usage


class CodexCLIProvider:
    """Independent, stateless model calls from an empty temporary working directory.

    Agent tool activity invalidates a response. This prevents using an agent's
    hidden solver or filesystem observations as if they were model-only planning.
    The installed CLI's default model is retained unless explicitly supplied.
    """
    name = "codex_cli_live"

    def __init__(self, log_dir: Path | str, model: str | None = None, timeout: float = 120,
                 reasoning_effort: str | None = None):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a finite positive number of seconds")
        self.log_dir = Path(log_dir).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.model = model
        if reasoning_effort not in (None, "low", "medium", "high", "xhigh", "max", "ultra"):
            raise ValueError("Unsupported reasoning_effort")
        self.reasoning_effort = reasoning_effort
        self.timeout = timeout
        self.executable = shutil.which("codex")
        if not self.executable:
            raise ProviderError("Codex CLI was not found on PATH. Run the doctor command first.")

    def complete(self, prompt: str, schema: dict, call_index: int) -> tuple[dict, dict]:
        call_dir = self.log_dir / ("call_%02d" % call_index)
        call_dir.mkdir(exist_ok=False)
        (call_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        (call_dir / "schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
        command = [self.executable, "exec", "--ignore-user-config", "--ephemeral",
                   "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never", "--json"]
        for feature in ("shell_tool", "apps", "plugins", "hooks", "memories", "multi_agent",
                        "browser_use", "computer_use", "in_app_browser", "image_generation"):
            command.extend(["--disable", feature])
        if self.model:
            command.extend(["--model", self.model])
        if self.reasoning_effort:
            command.extend(["--config", "model_reasoning_effort=" + self.reasoning_effort])
        command.extend(["--output-schema", str(call_dir / "schema.json"),
                        "--output-last-message", str(call_dir / "response.json"), "-"])
        start = time.monotonic()
        stdout, stderr, error = "", "", None
        with tempfile.TemporaryDirectory(prefix="planner2d-inference-") as isolated_dir:
            process = subprocess.Popen(command, cwd=isolated_dir, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, start_new_session=True)
            try:
                stdout, stderr = process.communicate(prompt, timeout=self.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
                error = "LLM timeout after %.1f seconds" % self.timeout
            except BaseException:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                raise
        elapsed = time.monotonic() - start
        (call_dir / "events.jsonl").write_text(stdout, encoding="utf-8")
        (call_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        events, usage = _decode_events(stdout)
        tool_events = [event for event in events if event.get("type", "").startswith("item.")
                       and event.get("item", {}).get("type") not in ("agent_message", "reasoning")]
        metadata = {"provider": self.name, "requested_model": self.model,
                    "requested_reasoning_effort": self.reasoning_effort,
                    "model_resolution": "explicit" if self.model else "installed_cli_default_not_reported",
                    "elapsed_seconds": elapsed, "usage": usage, "returncode": process.returncode,
                    "tool_activity_count": len(tool_events),
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "log_directory": str(call_dir), "command": command}
        if error is None and process.returncode:
            error = "Codex exited with status %s. See %s" % (process.returncode, call_dir / "stderr.log")
        if tool_events:
            error = "Model used tools; response rejected to preserve the planner input boundary"
        if error:
            metadata["error"] = error
        (call_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        if error:
            raise ProviderError(error)
        try:
            value = json.loads((call_dir / "response.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderError("No valid structured response: %s" % call_dir) from exc
        return value, metadata

    def propose(self, prompt: str, call_index: int) -> tuple[dict, dict]:
        value, metadata = self.complete(prompt, PLAN_SCHEMA, call_index)
        return parse_plan(value), metadata

    def probe(self) -> tuple[dict, dict]:
        return self.complete("Return only the JSON object with status ok. Do not use any tools, "
                             "read files, browse, or change files. This is a bounded connectivity test.",
                             PROBE_SCHEMA, 0)

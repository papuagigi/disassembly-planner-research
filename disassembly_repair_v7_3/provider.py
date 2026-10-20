"""H5 (retry stage onward): CodexCLIProvider with the built-in web search tool disabled.

Validation episode asap_05459/B_r1 ended with zero physics checks because the model
issued an empty web_search call inside its execute turn; the inherited provider
(disassembly_planner_2d/planner2d/llm.py) rejects any tool activity, and the installed
Codex CLI (0.163) offers web search by default even with --ignore-user-config.
Probe (2026-10-20): web_search="disabled" -> no web_search items; "live" -> 2 web_search items.

Everything else is the inherited provider unchanged (same model/effort/flags/tool-activity
rejection); this copy only adds --config web_search="disabled". Applied to every arm and
to the note writer, so it is not an arm-specific change.
"""
from __future__ import annotations
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

from .common import WORKSPACE

CODEX_DIR = '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS'
os.environ['PATH'] = CODEX_DIR + os.pathsep + os.environ.get('PATH', '')
sys.path.insert(0, str(WORKSPACE / 'disassembly_planner_2d'))
from planner2d.llm import CodexCLIProvider, ProviderError, _decode_events  # noqa: E402

DISABLED_FEATURES = ("shell_tool", "apps", "plugins", "hooks", "memories", "multi_agent",
                     "browser_use", "computer_use", "in_app_browser", "image_generation")


class NoWebSearchCodexProvider(CodexCLIProvider):
    name = "codex_cli_live_no_web_search"

    def complete(self, prompt, schema, call_index):
        call_dir = self.log_dir / ("call_%02d" % call_index)
        call_dir.mkdir(exist_ok=False)
        (call_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        (call_dir / "schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
        command = [self.executable, "exec", "--ignore-user-config", "--ephemeral",
                   "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never", "--json"]
        for feature in DISABLED_FEATURES:
            command.extend(["--disable", feature])
        command.extend(["--config", 'web_search="disabled"'])  # H5
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

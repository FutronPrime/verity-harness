from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from verity import autostart
from verity import server

ROOT = pathlib.Path(__file__).resolve().parents[1]
CODEX_HOOK = ROOT / "hooks" / "codex_prompt_guard.py"


def _post_json(url: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=3) as response:
        return response.status, json.loads(response.read())


def test_preflight_endpoint_returns_deterministic_codex_context(monkeypatch):
    monkeypatch.setattr(
        server,
        "build_preflight_context",
        lambda goal, run="": {
            "goal": goal,
            "run": run,
            "researched": True,
            "context": "VERITY ROUTE RECEIPT\nCURRENT BEST APPROACH: use the supported hook API.",
        },
        raising=False,
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post_json(
            f"http://127.0.0.1:{httpd.server_port}/v1/preflight",
            {"goal": "wire Codex through VERITY", "run": "turn-123"},
        )
    finally:
        httpd.shutdown()
        thread.join(timeout=2)

    assert status == 200
    assert body["researched"] is True
    assert body["run"] == "turn-123"
    assert "VERITY ROUTE RECEIPT" in body["context"]


def test_real_preflight_context_always_injects_gui_escalation(monkeypatch):
    monkeypatch.setattr(server, "_PREFLIGHT_SIGNAL", server._PREFLIGHT_SIGNAL)
    context = server.build_preflight_context("summarize this local file", run="turn-gui")["context"]
    assert "GUI ESCALATION BLOCKER" in context
    assert "futron-tools-catalog json cua-automation" in context
    assert "futron-desktop-agent status" in context


def test_send_ignores_client_disconnect_after_headers():
    handler = object.__new__(server.Handler)
    handler.send_response = lambda _code: None
    handler.send_header = lambda _key, _value: None
    handler.end_headers = lambda: None

    class ClosedClient:
        def write(self, _body):
            raise BrokenPipeError("client closed")

    handler.wfile = ClosedClient()
    handler._send(200, {"ok": True})


def test_codex_prompt_hook_routes_goal_and_injects_context():
    seen = {}

    class StubHandler(server.Handler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            seen.update(json.loads(self.rfile.read(n) or b"{}"))
            self._send(200, {
                "researched": True,
                "context": "VERITY ROUTE RECEIPT\nVERIFY: run the objective check.",
            })

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    env = dict(os.environ)
    env["VERITY_PREFLIGHT_URL"] = f"http://127.0.0.1:{httpd.server_port}/v1/preflight"
    try:
        proc = subprocess.run(
            [sys.executable, str(CODEX_HOOK)],
            input=json.dumps({
                "hook_event_name": "UserPromptSubmit",
                "session_id": "session-1",
                "turn_id": "turn-1",
                "prompt": "repair the VERITY daemon",
            }),
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
    finally:
        httpd.shutdown()
        thread.join(timeout=2)

    assert proc.returncode == 0, proc.stderr
    output = json.loads(proc.stdout)
    assert seen == {"goal": "repair the VERITY daemon", "run": "turn-1"}
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "VERITY ROUTE RECEIPT" in output["hookSpecificOutput"]["additionalContext"]


def test_codex_prompt_hook_fails_closed_when_verity_cannot_be_repaired():
    env = dict(os.environ)
    env["VERITY_PREFLIGHT_URL"] = "http://127.0.0.1:1/v1/preflight"
    env["VERITY_DAEMON_AUTOREPAIR"] = "off"
    proc = subprocess.run(
        [sys.executable, str(CODEX_HOOK)],
        input=json.dumps({"prompt": "do important work", "turn_id": "turn-2"}),
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )

    assert proc.returncode == 0
    output = json.loads(proc.stdout)
    assert output["decision"] == "block"
    assert "VERITY preflight unavailable" in output["reason"]


def test_wire_codex_installs_prompt_route_and_stop_guards(tmp_path, monkeypatch):
    state = tmp_path / ".verity-harness"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(autostart, "SCRIPT", state / "autostart.sh")
    monkeypatch.setattr(autostart, "INJECT", state / "verity-context-inject.sh")
    monkeypatch.setattr(autostart, "GUARD", state / "stop_guard.py")
    monkeypatch.setattr(autostart, "CODEX_PROMPT_GUARD", state / "codex_prompt_guard.py", raising=False)

    report = autostart.wire_codex()

    hooks_path = tmp_path / ".codex" / "hooks.json"
    hooks = json.loads(hooks_path.read_text())["hooks"]
    assert "UserPromptSubmit" in hooks
    assert "codex_prompt_guard.py" in json.dumps(hooks["UserPromptSubmit"])
    assert "stop_guard.py" in json.dumps(hooks["Stop"])
    assert "stop_guard.py" in json.dumps(hooks["SubagentStop"])
    assert (state / "codex_prompt_guard.py").is_file()
    assert "VERITY v2.3" in (tmp_path / ".codex" / "AGENTS.md").read_text()
    assert "VERITY v2.3" in (tmp_path / ".codex" / "instructions.md").read_text()
    assert (tmp_path / ".agents" / "skills" / "verity" / "SKILL.md").is_file()
    assert "deterministic preflight" in report.lower()


def test_wire_daemon_migrates_legacy_label_and_refuses_false_success(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(autostart, "_wait_for_proxy_health", lambda **kwargs: False, raising=False)

    with pytest.raises(RuntimeError, match="health check failed"):
        autostart.wire_daemon()

    joined = [" ".join(call) for call in calls]
    assert any("bootout" in call and "ai.futron.verity-proxy" in call for call in joined)
    assert any("bootout" in call and "io.verity.proxy" in call for call in joined)
    assert any("bootstrap" in call and "io.verity.proxy.plist" in call for call in joined)
    wrapper = (tmp_path / ".verity-harness" / "proxy-daemon.sh").read_text()
    assert "import verity.guard, verity.server" in wrapper
    assert "rejected incompatible Python" in wrapper

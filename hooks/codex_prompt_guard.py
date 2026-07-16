#!/usr/bin/env python3
"""Route every Codex UserPromptSubmit event through VERITY's preflight gate.

Codex keeps its native Responses API transport and structured tools. The prompt
still crosses VERITY on port 11500 before the model sees it, and the returned
deterministic research/verification contract is injected as developer context.
If the daemon is unavailable, repair it once and then fail closed.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

URL = os.environ.get("VERITY_PREFLIGHT_URL", "http://127.0.0.1:11500/v1/preflight")
TIMEOUT = float(os.environ.get("VERITY_PREFLIGHT_TIMEOUT", "75"))


def _request(goal: str, run: str) -> dict:
    req = urllib.request.Request(
        URL,
        data=json.dumps({"goal": goal, "run": run}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        body = json.loads(response.read())
    if not isinstance(body, dict) or not str(body.get("context") or "").strip():
        raise RuntimeError("preflight returned no enforcement context")
    return body


def _python() -> str:
    for candidate in (
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        sys.executable,
    ):
        if candidate and pathlib.Path(candidate).is_file():
            return candidate
    return sys.executable


def _repair_daemon() -> None:
    if os.environ.get("VERITY_DAEMON_AUTOREPAIR", "on").lower() in ("0", "off", "false", "no"):
        return
    repo = pathlib.Path(
        os.environ.get("VERITY_REPO", "~/repos/verity-harness")
    ).expanduser()
    if not repo.is_dir():
        return
    subprocess.run(
        [_python(), "-m", "verity", "autostart", "--daemon"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    for _ in range(20):
        time.sleep(0.25)
        try:
            with urllib.request.urlopen(URL.rsplit("/v1/preflight", 1)[0] + "/health", timeout=1):
                return
        except Exception:
            pass


def _block(error: Exception) -> dict:
    return {
        "decision": "block",
        "reason": (
            "VERITY preflight unavailable after the automatic daemon repair attempt; the prompt "
            "was not allowed to bypass deterministic gates. Inspect "
            "~/.verity-harness/proxy-daemon.log, repair port 11500, and retry. "
            f"Observed: {type(error).__name__}: {str(error)[:240]}"
        ),
    }


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    goal = str(data.get("prompt") or "").strip()
    if not goal:
        return 0
    run = str(data.get("turn_id") or data.get("session_id") or "")
    try:
        result = _request(goal, run)
    except Exception:
        _repair_daemon()
        try:
            result = _request(goal, run)
        except Exception as error:
            print(json.dumps(_block(error)))
            return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": result["context"],
        }
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

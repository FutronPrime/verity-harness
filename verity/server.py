#!/usr/bin/env python3
"""OpenAI-compatible proxy daemon — makes the harness invisible.

Point any OpenAI-compatible client (Claude Code, Cursor, an SDK, curl) at this
server instead of the vendor, and it transparently inherits: tiered failover
(frontier→sovereign), the guardrail (configurable; off by default for local), and
per-call tier reporting. The client sees a normal /v1/chat/completions endpoint;
the resilience just happens.

  python3 -m verity.server          # serve on :11500
  PORT=8080 python3 -m verity.server

Then: export OPENAI_BASE_URL=http://127.0.0.1:11500/v1  (or your client's setting)

stdlib only — no framework. The thing that keeps you running when a vendor dies
must not need a vendor's package to run.
"""
from __future__ import annotations

import json
import os
import pathlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .router import chat, AllTiersFailed
from .guardrail import classify, CAPABILITY_DIRECTIVE, SAFETY_DIRECTIVE

_MODE = os.environ.get("VERITY_GUARDRAIL_MODE", "off").lower()
# Overconfidence guard is a RELIABILITY feature (not content-safety) → its own toggle, ON by default.
# It re-prompts a flagged giveup once, server-side. Set VERITY_OVERCONFIDENCE_GUARD=off to disable.
_OC_GUARD = os.environ.get("VERITY_OVERCONFIDENCE_GUARD", "on").lower() != "off"

# LIFECYCLE: don't linger. Track last real use; a watchdog exits the process after this many idle
# minutes so a stray proxy never eats RAM after your agent closes. 0 disables. Default 15 min.
_IDLE_MIN = float(os.environ.get("VERITY_IDLE_SHUTDOWN_MIN", "15"))
_LAST_USE = [time.time()]
PIDFILE = pathlib.Path(os.path.expanduser("~/.verity-harness/proxy.pid"))


def _idle_watchdog():
    if _IDLE_MIN <= 0:
        return
    while True:
        time.sleep(30)
        if time.time() - _LAST_USE[0] > _IDLE_MIN * 60:
            try:
                PIDFILE.unlink(missing_ok=True)
            except OSError:
                pass
            os._exit(0)   # hard-exit the whole process — clean, no lingering threads


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet default access logging
        pass

    def _send(self, code: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") in ("/health", "/v1/health"):
            self._send(200, {"ok": True, "service": "verity-harness-proxy",
                             "guardrail_mode": _MODE})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self._send(404, {"error": "not found"})
            return
        _LAST_USE[0] = time.time()   # real use — keep alive; health pings don't count
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": "bad json"})
            return

        messages = req.get("messages", [])
        # Optional guardrail on the last user turn (off → neutral passthrough).
        if _MODE != "off" and messages:
            last = next((m for m in reversed(messages)
                         if m.get("role") == "user"), {})
            v = classify(last.get("content", ""))
            if v.level == "refuse" and _MODE == "strict":
                self._send(200, _as_openai("[refused by guardrail: hard-stop category]",
                                           "guardrail-refuse"))
                return
            directive = SAFETY_DIRECTIVE if v.level == "sensitive" else CAPABILITY_DIRECTIVE
            if not any(m.get("role") == "system" for m in messages):
                messages = [{"role": "system", "content": directive}] + messages

        try:
            reply = chat(messages)
        except AllTiersFailed as e:
            self._send(503, {"error": f"all tiers down: {e}"})
            return

        # RESPONSE-SIDE OVERCONFIDENCE GUARD (universal, daemon-enforced): if the model's answer is a
        # premature giveup ("it's down / impossible / only you can") the proxy re-prompts it ONCE,
        # server-side, forcing investigation — no opt-out, fires for ANY model routed here. Off when
        # guardrail mode is off. Capped at one re-prompt (no latency/loop blowup).
        guarded = ""
        if _OC_GUARD:
            from .guard import flag, CORRECTIVE
            if flag(reply.text):
                try:
                    reprompt = list(messages) + [
                        {"role": "assistant", "content": reply.text},
                        {"role": "user", "content": CORRECTIVE},
                    ]
                    reply2 = chat(reprompt)
                    if reply2.text and not flag(reply2.text):
                        reply = reply2
                        guarded = "corrected"
                    else:
                        guarded = "flagged"  # still a giveup after one nudge — surface it, don't loop
                except AllTiersFailed:
                    guarded = "flagged"
        out = _as_openai(reply.text, reply.model, reply.tier)
        if guarded:
            out["x_verity_overconfidence_guard"] = guarded
        self._send(200, out)


def _as_openai(content: str, model: str, tier: str = "") -> dict:
    return {
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
        "x_sovereign_tier": tier,  # which tier served you (proxy extension)
    }


def serve(port: int | None = None):
    port = port or int(os.environ.get("PORT", "11500"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(os.getpid()))
    threading.Thread(target=_idle_watchdog, daemon=True).start()
    print(f"verity-harness proxy on http://127.0.0.1:{port}/v1  "
          f"(guardrail={_MODE}, idle-shutdown={_IDLE_MIN}min)")
    try:
        srv.serve_forever()
    finally:
        PIDFILE.unlink(missing_ok=True)


def stop() -> str:
    """Stop a running proxy (read the pidfile, signal it). Used by `verity stop` + the
    SessionEnd hook so the harness closes when your agent does — no lingering RAM."""
    import signal
    if not PIDFILE.exists():
        return "[verity] no proxy pidfile — nothing running (or already stopped)."
    try:
        pid = int(PIDFILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        PIDFILE.unlink(missing_ok=True)
        return f"[verity] stopped proxy (pid {pid})."
    except (ValueError, ProcessLookupError):
        PIDFILE.unlink(missing_ok=True)
        return "[verity] proxy already gone; cleared stale pidfile."
    except OSError as e:
        return f"[verity] could not stop proxy: {e}"


if __name__ == "__main__":
    import sys
    if "--stop" in sys.argv:
        print(stop())
    else:
        serve()

#!/usr/bin/env python3
"""OpenAI-compatible proxy daemon — makes the harness invisible.

Point any OpenAI-compatible client (Claude Code, Cursor, an SDK, curl) at this
server instead of the vendor, and it transparently inherits: tiered failover
(frontier→sovereign), the guardrail (configurable; off by default for local), and
per-call tier reporting. The client sees a normal /v1/chat/completions endpoint;
the resilience just happens.

  python3 -m sovereign_harness.server          # serve on :11500
  PORT=8080 python3 -m sovereign_harness.server

Then: export OPENAI_BASE_URL=http://127.0.0.1:11500/v1  (or your client's setting)

stdlib only — no framework. The thing that keeps you running when a vendor dies
must not need a vendor's package to run.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .router import chat, AllTiersFailed
from .guardrail import classify, CAPABILITY_DIRECTIVE, SAFETY_DIRECTIVE

_MODE = os.environ.get("SOVEREIGN_GUARDRAIL_MODE", "off").lower()


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
            self._send(200, {"ok": True, "service": "sovereign-harness-proxy",
                             "guardrail_mode": _MODE})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self._send(404, {"error": "not found"})
            return
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
        self._send(200, _as_openai(reply.text, reply.model, reply.tier))


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
    print(f"sovereign-harness proxy on http://127.0.0.1:{port}/v1  "
          f"(guardrail={_MODE})")
    srv.serve_forever()


if __name__ == "__main__":
    serve()

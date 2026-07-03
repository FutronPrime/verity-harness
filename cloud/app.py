"""VERITY Cloud — the discipline gates as a metered HTTP API (recurring revenue).

Reuses the existing VERITY modules (vet / audit_code / verity_scan) — Rule 17, no rebuild.
Stdlib only (http.server) so it deploys anywhere with zero extra deps.

Endpoints (all POST JSON unless noted):
  GET  /health                         → liveness
  POST /v1/scan       {"text": "..."}  → prompt-injection / unsafe-instruction scan
  POST /v1/vet        {"path": "..."}  → static safe-to-apply verdict for a file/dir
  POST /v1/reuse-check {"intent":"..."}→ does a similar tool likely already exist? (advice)
  GET  /v1/usage                       → this key's metered usage this period

Auth: `Authorization: Bearer <API_KEY>`. Keys + usage live in a local SQLite ledger; when
STRIPE_API_KEY is set, usage is reported to Stripe metered billing (see billing.py). Absent a
Stripe key it still runs fully — meters locally — so it's testable before billing is wired.

Env:
  VERITY_CLOUD_PORT   (default 8787)
  VERITY_CLOUD_DB     (default ~/.verity-cloud/ledger.db)
  STRIPE_API_KEY      (optional — enables real metered billing)
  VERITY_ADMIN_KEY    (optional — allows POST /admin/issue-key to mint keys)
"""
from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

DB_PATH = pathlib.Path(os.environ.get("VERITY_CLOUD_DB", str(pathlib.Path.home() / ".verity-cloud/ledger.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# per-endpoint price (billing units) — reported to Stripe if wired
PRICE = {"/v1/scan": 1, "/v1/vet": 3, "/v1/reuse-check": 1}


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS keys(key TEXT PRIMARY KEY, plan TEXT, stripe_item TEXT, created INT)")
    c.execute("CREATE TABLE IF NOT EXISTS usage(key TEXT, endpoint TEXT, units INT, ts INT)")
    return c


def _issue_key(plan: str = "metered", stripe_item: str = "") -> str:
    import secrets
    k = "vk_" + secrets.token_urlsafe(24)
    with _db() as c:
        c.execute("INSERT INTO keys VALUES(?,?,?,?)", (k, plan, stripe_item, int(time.time())))
    return k


def _auth(headers) -> str | None:
    h = headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        return None
    key = h[7:].strip()
    with _db() as c:
        row = c.execute("SELECT key FROM keys WHERE key=?", (key,)).fetchone()
    return key if row else None


def _meter(key: str, endpoint: str, units: int) -> None:
    with _db() as c:
        c.execute("INSERT INTO usage VALUES(?,?,?,?)", (key, endpoint, units, int(time.time())))
        item = c.execute("SELECT stripe_item FROM keys WHERE key=?", (key,)).fetchone()
    if os.environ.get("STRIPE_API_KEY") and item and item[0]:
        try:
            from billing import report_usage
            report_usage(item[0], units)
        except Exception:
            pass  # never fail the request on a billing hiccup; local ledger is source of truth


# ── gate implementations (reuse VERITY modules) ──────────────────────────────
def do_scan(body: dict) -> dict:
    text = body.get("text", "")
    import re
    # lightweight inline scan (mirrors verity_scan heuristics) — flags injection/unsafe patterns
    pats = [(r"ignore (all|previous|above).{0,20}instructions", "instruction-override"),
            (r"(exfiltrat|send).{0,30}(secret|token|key|credential)", "exfil"),
            (r"curl\s+[^|]*\|\s*(sh|bash)", "pipe-to-shell"),
            (r"rm\s+-rf\s+/", "destructive"),
            (r"(base64\s+-d|eval\s*\()", "obfuscated-exec")]
    hits = [name for rx, name in pats if re.search(rx, text, re.I)]
    return {"verdict": "UNSAFE" if hits else "SAFE", "flags": hits}


def do_vet(body: dict) -> dict:
    path = body.get("path", "")
    if not path or not os.path.exists(os.path.expanduser(path)):
        return {"error": "path not found"}
    try:
        from verity import vet as _vet
        r = _vet.vet(os.path.expanduser(path))
        return {"verdict": getattr(r, "verdict", str(r)), "blockers": getattr(r, "blockers", [])}
    except Exception as e:
        return {"error": f"vet failed: {e}"}


def do_reuse_check(body: dict) -> dict:
    intent = body.get("intent", "")
    # advice endpoint: the reuse-first principle as a service
    return {"advice": "Before building, search your codebase + tool directory for these keywords.",
            "keywords": [w for w in intent.lower().split() if len(w) > 3][:8],
            "rule": "If a tool matches, USE IT. Rebuilding forks logic and rots the system."}


ROUTES = {"/v1/scan": do_scan, "/v1/vet": do_vet, "/v1/reuse-check": do_reuse_check}


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.rstrip("/") in ("/health", ""):
            return self._send(200, {"ok": True, "service": "verity-cloud", "gates": list(ROUTES)})
        if self.path.rstrip("/") == "/v1/usage":
            key = _auth(self.headers)
            if not key:
                return self._send(401, {"error": "unauthorized"})
            with _db() as c:
                rows = c.execute("SELECT endpoint, SUM(units) FROM usage WHERE key=? GROUP BY endpoint", (key,)).fetchall()
            return self._send(200, {"usage": {e: u for e, u in rows}})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.rstrip("/")
        if path == "/admin/issue-key":
            if os.environ.get("VERITY_ADMIN_KEY") and self.headers.get("X-Admin-Key") == os.environ["VERITY_ADMIN_KEY"]:
                body = self._body()
                return self._send(200, {"api_key": _issue_key(body.get("plan", "metered"), body.get("stripe_item", ""))})
            return self._send(403, {"error": "admin key required"})
        if path not in ROUTES:
            return self._send(404, {"error": "unknown endpoint", "gates": list(ROUTES)})
        key = _auth(self.headers)
        if not key:
            return self._send(401, {"error": "unauthorized — Authorization: Bearer <API_KEY>"})
        try:
            result = ROUTES[path](self._body())
        except Exception as e:
            return self._send(500, {"error": str(e)})
        _meter(key, path, PRICE.get(path, 1))
        return self._send(200, result)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def log_message(self, *a):
        pass  # quiet


def main():
    port = int(os.environ.get("VERITY_CLOUD_PORT", "8787"))
    print(f"VERITY Cloud on :{port} (db={DB_PATH}, stripe={'on' if os.environ.get('STRIPE_API_KEY') else 'off'})")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


if __name__ == "__main__":
    main()

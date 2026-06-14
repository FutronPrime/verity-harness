#!/usr/bin/env python3
"""VERITY dashboard — a status face for the silent harness.

Not an always-on UI (the harness stays invisible). This is a page you OPEN when you want to SEE
it working: is the proxy up, which tier is serving, and the live RECEIPT — every gate that fired
(searches, assumptions caught + corrected, verify/guess) straight from the decision ledger, plus
the benchmark scorecard. Zero dependencies (stdlib http.server); reads the local ledger + proxy.

  python3 -m verity dashboard          # serve on :11501 and open the browser
  PORT=9000 python3 -m verity dashboard
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = pathlib.Path(__file__).resolve().parent.parent
LEDGER_DIR = pathlib.Path(os.path.expanduser("~/.verity-harness/ledger"))


def _proxy_up() -> dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11500/health", timeout=1) as r:
            return {"up": True, **json.loads(r.read())}
    except Exception:  # noqa: BLE001
        return {"up": False}


def _ledger(days: int = 2) -> list[dict]:
    out = []
    for i in range(days):
        p = LEDGER_DIR / (time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400)) + ".jsonl")
        if p.exists():
            for line in p.read_text().splitlines():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def _state() -> dict:
    from .config import TIERS
    ev = _ledger()
    tally: dict[str, int] = {}
    for e in ev:
        tally[e.get("gate", "?")] = tally.get(e.get("gate", "?"), 0) + 1
    return {
        "proxy": _proxy_up(),
        "tiers": [{"name": t.name, "model": t.model, "kind": t.protocol} for t in TIERS],
        "tally": tally,
        "searches": sum(1 for e in ev if e.get("gate") == "search-before-concluding") + sum(1 for e in ev if "search" in e.get("gate", "")),
        "corrected": sum(1 for e in ev if e.get("verdict") == "CORRECTED"),
        "verified": sum(1 for e in ev if e.get("verdict") == "VERIFIED"),
        "events": ev[-40:][::-1],
        "benchmarks": [
            {"axis": "Agentic search (Opus 4.8)", "naive": "25%", "harness": "100%", "good": True},
            {"axis": "Reasoning (4B local)", "naive": "33%", "harness": "67%", "good": True},
            {"axis": "Coding/easy (Kimi·Opus)", "naive": "100%", "harness": "67–100%", "good": False},
        ],
    }


_HTML = r"""<!doctype html><html><head><meta charset=utf-8><title>VERITY · Harness Monitor</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{--bg:#06090c;--panel:#0c1418;--teal:#19e3c8;--teal2:#0bb39e;--mag:#ff2d78;--ink:#cfeee8;--dim:#5d7b78;--line:#143038}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "SF Mono",ui-monospace,Menlo,monospace;
background-image:repeating-linear-gradient(0deg,transparent 0 3px,rgba(25,227,200,.02) 3px 4px)}
.wrap{max-width:1100px;margin:0 auto;padding:22px}
header{display:flex;align-items:center;gap:16px;border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:18px}
.logo{width:48px;height:48px}h1{font:700 26px/1 "SF Pro Display",system-ui,sans-serif;letter-spacing:.18em;margin:0;color:var(--teal)}
h1 small{display:block;font:500 11px/1.4 inherit;letter-spacing:.32em;color:var(--dim);margin-top:6px}
.pill{margin-left:auto;padding:8px 16px;border:1px solid var(--teal);color:var(--teal);font-weight:700;letter-spacing:.1em;
clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px)}
.pill.down{border-color:var(--mag);color:var(--mag)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:760px){.grid{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);padding:16px;
clip-path:polygon(0 0,calc(100% - 12px) 0,100% 12px,100% 100%,12px 100%,0 calc(100% - 12px))}
.panel h2{font:600 11px/1 sans-serif;letter-spacing:.3em;color:var(--teal2);margin:0 0 12px;text-transform:uppercase}
.panel h2:before{content:"/// "}
.kv{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px dashed var(--line)}
.kv b{color:var(--teal)}.big{font:700 34px/1 sans-serif;color:var(--teal)}.row{display:flex;gap:18px;margin:8px 0}
.stat{flex:1}.stat .n{font:700 28px/1 sans-serif;color:var(--teal)}.stat .l{font-size:11px;color:var(--dim);letter-spacing:.1em}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:6px 4px;border-bottom:1px solid var(--line);font-size:13px}
th{color:var(--dim);font-weight:600;font-size:10px;letter-spacing:.15em}
.up{color:var(--teal)}.bad{color:var(--mag)}
.feed{max-height:330px;overflow:auto}.ev{padding:7px 0;border-bottom:1px dashed var(--line);font-size:12px}
.ev .g{color:var(--mag);font-weight:700;letter-spacing:.08em}.ev .v{float:right;color:var(--teal);font-size:10px;border:1px solid var(--teal2);padding:1px 6px}
.ev .v.GUESS{color:var(--mag);border-color:var(--mag)}.ev .t{color:var(--dim);font-size:10px}.ev .d{color:var(--ink);opacity:.85}
.foot{margin-top:18px;color:var(--dim);font-size:11px;letter-spacing:.1em;text-align:center}
</style></head><body><div class=wrap>
<header><img class=logo src="/logo.png" onerror="this.style.display='none'">
<h1>VERITY<small>THE TRUTH HARNESS · LIVE MONITOR</small></h1><div id=proxy class=pill>…</div></header>
<div class=grid>
 <div class=panel><h2>Failover chain</h2><div id=tiers></div></div>
 <div class=panel><h2>The receipt</h2>
   <div class=row><div class=stat><div class=n id=s_search>0</div><div class=l>SEARCHES FIRED</div></div>
   <div class=stat><div class=n id=s_corr>0</div><div class=l>ASSUMPTIONS CORRECTED</div></div>
   <div class=stat><div class=n id=s_ver>0</div><div class=l>VERIFIED CLAIMS</div></div></div></div>
</div>
<div class=panel style=margin-top:16px><h2>Benchmark scorecard (naive → harness)</h2>
 <table><thead><tr><th>AXIS</th><th>NAIVE</th><th>HARNESS</th></tr></thead><tbody id=bench></tbody></table></div>
<div class=panel style=margin-top:16px><h2>Live gate feed (decision ledger)</h2><div class=feed id=feed></div></div>
<div class=foot>github.com/FutronPrime/verity-harness · Fable tells the tale. Verity verifies it.</div>
</div><script>
async function tick(){try{const s=await(await fetch('/api/state')).json();
 const p=document.getElementById('proxy');p.textContent=s.proxy.up?'● PROXY UP :11500':'○ PROXY DOWN';p.className='pill'+(s.proxy.up?'':' down');
 document.getElementById('tiers').innerHTML=s.tiers.map((t,i)=>`<div class=kv><span>${i+1}. ${t.name}</span><b>${t.model}</b></div>`).join('');
 document.getElementById('s_search').textContent=s.searches;document.getElementById('s_corr').textContent=s.corrected;document.getElementById('s_ver').textContent=s.verified;
 document.getElementById('bench').innerHTML=s.benchmarks.map(b=>`<tr><td>${b.axis}</td><td>${b.naive}</td><td class=${b.good?'up':'bad'}>${b.harness} ${b.good?'▲':'■'}</td></tr>`).join('');
 document.getElementById('feed').innerHTML=s.events.length?s.events.map(e=>`<div class=ev><span class="v ${e.verdict||''}">${e.verdict||'—'}</span><span class=g>${e.gate}</span> <span class=t>${(e.ts||'').slice(11)}</span><br><span class=d>${(e.trigger||'')} ${e.evidence?'→ '+e.evidence:''}</span></div>`).join(''):'<div class=ev style=color:var(--dim)>No gate events yet — run `verity eval` or any task through the harness.</div>';
}catch(e){}}tick();setInterval(tick,3000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.rstrip("/") or "/"
        if path == "/api/state":
            b = json.dumps(_state()).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        elif path == "/logo.png":
            logo = REPO / "assets" / "logo.png"
            if logo.exists():
                d = logo.read_bytes()
                self.send_response(200); self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)
            else:
                self.send_response(404); self.end_headers()
        else:
            b = _HTML.encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


def serve(port: int | None = None, open_browser: bool = True):
    port = port or int(os.environ.get("PORT", "11501"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"VERITY dashboard → {url}")
    if open_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    srv.serve_forever()


if __name__ == "__main__":
    serve()

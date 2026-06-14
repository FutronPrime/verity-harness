#!/usr/bin/env python3
"""Real-world reach — let the agent go FIND information, not just reason in a box.

Zero-dep stdlib tools the harness ships with:
  fetch(url)        → GET a web page, stripped to readable text
  web_search(query) → top results (title + url + snippet) via a free endpoint

And — just as important — the KNOWLEDGE (capabilities_guide) that the agent has a
real shell and can install + drive ANY tool it needs: curl, yt-dlp, gh, jq,
Playwright (browser automation), computer-use, MCP clients. The harness doesn't
have to bundle every tool; it just has to know it can reach for them.
"""
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request

_UA = "Mozilla/5.0 (sovereign-harness; +https://github.com/)"
_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_WS = re.compile(r"[ \t]*\n\s*\n\s*")


def _get(url: str, timeout: float = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, "ignore")


def fetch(url: str, max_chars: int = 8000) -> str:
    """GET a URL and return readable text (HTML stripped). Static pages only —
    for JS-heavy sites, the agent should install Playwright via the shell."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        raw = _get(url)
    except Exception as e:  # noqa: BLE001
        return f"[fetch error: {type(e).__name__}: {e}]"
    text = _SCRIPT.sub(" ", raw)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = _WS.sub("\n\n", re.sub(r"[ \t]+", " ", text)).strip()
    return text[:max_chars]


def _tavily_search(query: str, n: int, key: str) -> str:
    import json
    body = json.dumps({"query": query, "max_results": n}).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read())
    out = [f"{i+1}. {x.get('title','')[:120]}\n   {x.get('url','')}\n   {x.get('content','')[:200]}"
           for i, x in enumerate(data.get("results", [])[:n])]
    return "\n".join(out) or "[tavily: no results]"


def web_search(query: str, n: int = 5) -> str:
    """Web search. Prefers a FREE agent-search API if a key is set (most reliable):
       Tavily — free tier, get a key at https://tavily.com → export TAVILY_API_KEY.
    Falls back to DuckDuckGo HTML scraping (no key, but often bot-blocked). If all
    fail, the agent should fetch() a specific URL or use a search CLI via the shell."""
    import os
    if (k := os.environ.get("TAVILY_API_KEY")):
        try:
            return _tavily_search(query, n, k)
        except Exception:  # noqa: BLE001 — fall through to scraping
            pass
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        raw = _get(url)
    except Exception as e:  # noqa: BLE001
        return f"[search error: {type(e).__name__}: {e}]"
    out, seen = [], set()
    # Try several link patterns (DDG markup drifts); accept any result anchor.
    patterns = [
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        r'<a[^>]+href="(//duckduckgo\.com/l/\?[^"]*uddg=[^"]+)"[^>]*>(.*?)</a>',
        r'<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]{8,})</a>',
    ]
    for pat in patterns:
        for m in re.finditer(pat, raw, re.DOTALL):
            href, title = m.group(1), _TAG.sub("", m.group(2)).strip()
            if href.startswith("//"):
                href = "https:" + href
            q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg")
            real = q[0] if q else href
            if not real.startswith("http") or real in seen or "duckduckgo.com" in real:
                continue
            seen.add(real)
            out.append(f"{len(out)+1}. {html.unescape(title)[:120]}\n   {real}")
            if len(out) >= n:
                break
        if out:
            break
    if out:
        return "\n".join(out)
    # Fallback: hand the agent the readable page text so it can read results itself.
    txt = _WS.sub("\n\n", _TAG.sub(" ", _SCRIPT.sub(" ", raw))).strip()
    return "[structured parse failed — raw results text follows]\n" + html.unescape(txt)[:3000]


def capabilities_guide() -> str:
    return """\
AGENT CAPABILITIES — you can go GET information, not just reason from memory.

You have a REAL SHELL (ShellExecutor). That means you can:

  • FETCH the web:
      python3 -c "from sovereign_harness.tools import fetch; print(fetch('URL'))"
      …or just: curl -sL URL
  • SEARCH the web (free, no key):
      python3 -c "from sovereign_harness.tools import web_search; print(web_search('query'))"
  • INSTALL any tool you need, then use it:
      pip install <pkg>      npm install -g <pkg>      brew install <tool>
      e.g. yt-dlp (video), jq (json), gh (github), pandoc, ripgrep, pdftotext
  • BROWSER AUTOMATION (JS-heavy sites, logins, clicking):
      pip install playwright && playwright install chromium
      then drive it from a python3 script via the shell.
  • COMPUTER USE / desktop automation:
      install a computer-use tool (e.g. pyautogui) and script it via the shell.
  • MCP servers (Model Context Protocol):
      run an MCP client/server via the shell and speak JSON-RPC over stdio.

RULE: if you lack information to finish a task, DO NOT GUESS — go fetch/search/
install the tool and get it. Verify what you find before relying on it."""

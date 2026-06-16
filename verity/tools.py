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

_UA = "Mozilla/5.0 (verity-harness; +https://github.com/)"
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


def _brave_search(query: str, n: int, key: str) -> str:
    import json
    url = ("https://api.search.brave.com/res/v1/web/search?q="
           + urllib.parse.quote(query) + f"&count={n}")
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "X-Subscription-Token": key})
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read())
    results = (data.get("web", {}) or {}).get("results", [])[:n]
    out = [f"{i+1}. {x.get('title','')[:120]}\n   {x.get('url','')}\n   {x.get('description','')[:200]}"
           for i, x in enumerate(results)]
    return "\n".join(out) or "[brave: no results]"


def web_search(query: str, n: int = 5) -> str:
    """Web search. Prefers a FREE agent-search API if a key is set (most reliable):
       Tavily — free tier, get a key at https://tavily.com → export TAVILY_API_KEY.
    Falls back to DuckDuckGo HTML scraping (no key, but often bot-blocked). If all
    fail, the agent should fetch() a specific URL or use a search CLI via the shell."""
    import os
    if (k := os.environ.get("BRAVE_API_KEY")):
        try:
            return _brave_search(query, n, k)
        except Exception:  # noqa: BLE001 — fall through
            pass
    if (k := os.environ.get("TAVILY_API_KEY")):
        try:
            return _tavily_search(query, n, k)
        except Exception:  # noqa: BLE001 — fall through to scraping
            pass
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        # DDG CAPTCHA-blocks non-browser UAs (it flags "verity-harness"). Use a real
        # browser UA here — verified to return results where the default UA gets a challenge.
        _bua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
        req = urllib.request.Request(url, headers={"User-Agent": _bua})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", "ignore")
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


# ── Multi-platform search via FREE, no-key public APIs ───────────────────────
# For finding rare/community/inside knowledge and open-source tools that generic
# web search misses: GitHub (tools/code), Reddit + HN (real-world experience),
# StackOverflow (solutions). Same approach as a proper scraping cascade.

def _json(url: str, timeout: float = 20):
    import json
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def search_github(query: str, n: int = 6) -> str:
    """Find repos/tools — incl. obscure, forked, or modified open-source versions."""
    try:
        d = _json(f"https://api.github.com/search/repositories?q="
                  f"{urllib.parse.quote(query)}&sort=stars&per_page={n}")
    except Exception as e:  # noqa: BLE001
        return f"[github error: {type(e).__name__}]"
    items = d.get("items", [])[:n]
    return "\n".join(
        f"{i+1}. {x['full_name']} ★{x.get('stargazers_count',0)}\n"
        f"   {x.get('description') or ''}\n   {x['html_url']}"
        for i, x in enumerate(items)) or "[github: no results]"


def search_reddit(query: str, n: int = 6) -> str:
    """Real-world experience / inside knowledge from communities."""
    import json
    # Reddit rejects generic browser UAs — it wants a descriptive app UA.
    url = (f"https://www.reddit.com/search.json?q={urllib.parse.quote(query)}"
           f"&sort=relevance&limit={n}")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "verity-harness/0.1 (autonomous research agent)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:  # noqa: BLE001
        return f"[reddit error: {type(e).__name__} — try old.reddit.com via fetch()]"
    posts = [c["data"] for c in d.get("data", {}).get("children", [])][:n]
    return "\n".join(
        f"{i+1}. r/{p.get('subreddit')} ↑{p.get('ups',0)}: {p.get('title','')[:120]}\n"
        f"   https://reddit.com{p.get('permalink','')}"
        for i, p in enumerate(posts)) or "[reddit: no results]"


def search_hackernews(query: str, n: int = 6) -> str:
    """Technical discussion / hard-won engineering experience."""
    try:
        d = _json(f"https://hn.algolia.com/api/v1/search?query="
                  f"{urllib.parse.quote(query)}&tags=story&hitsPerPage={n}")
    except Exception as e:  # noqa: BLE001
        return f"[hn error: {type(e).__name__}]"
    return "\n".join(
        f"{i+1}. ↑{h.get('points',0)} {h.get('title','')[:120]}\n"
        f"   {h.get('url') or 'https://news.ycombinator.com/item?id='+str(h.get('objectID'))}"
        for i, h in enumerate(d.get("hits", [])[:n])) or "[hn: no results]"


def search_stackoverflow(query: str, n: int = 5) -> str:
    """Concrete solutions to concrete problems."""
    try:
        d = _json(f"https://api.stackexchange.com/2.3/search/advanced?order=desc"
                  f"&sort=relevance&q={urllib.parse.quote(query)}&site=stackoverflow&pagesize={n}")
    except Exception as e:  # noqa: BLE001
        return f"[stackoverflow error: {type(e).__name__}]"
    return "\n".join(
        f"{i+1}. {'✓' if x.get('is_answered') else '·'} {html.unescape(x.get('title',''))[:120]}\n"
        f"   {x.get('link')}"
        for i, x in enumerate(d.get("items", [])[:n])) or "[so: no results]"


def notebooklm(query: str, sources=None, timeout: float = 180) -> str:
    """Deep, SOURCE-GROUNDED research via NotebookLM — synthesis over many docs/videos/URLs with
    citations, for when a flat web search isn't enough (onboarding a codebase, decoding legacy code +
    its git history, compressing a long issue/PR thread into problem→options→decision).

    BEST-EFFORT ENRICHMENT, never a hard gate dependency: NotebookLM clients ride Google's UNDOCUMENTED
    API, so keep the web/scrape cascade as the floor (Rule 29: >=2 backends). Reaches, in order:
      1. $NOTEBOOKLM_URL — a REST sidecar you run (e.g. teng-lin/notebooklm-py's server, 16k★, or
         jacob-bd/notebooklm-mcp-cli). POSTs {"query","sources"}; expects {"answer"/"text","citations"}.
      2. a local CLI if present: futron-notebooklm | nlm | notebooklm  (`<cli> research "<query>"`).
    Returns the grounded answer (+ citations) or setup guidance — never silently nothing."""
    import os, json, shutil, subprocess
    url = os.environ.get("NOTEBOOKLM_URL")
    if url:
        try:
            body = json.dumps({"query": query, **({"sources": sources} if sources else {})}).encode()
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json", "User-Agent": _UA},
                                         method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode("utf-8", "ignore"))
            ans = d.get("answer") or d.get("text") or d.get("response") or json.dumps(d)[:2000]
            cites = d.get("citations") or d.get("sources") or []
            tail = ("\nSOURCES: " + "; ".join(map(str, cites))[:600]) if cites else ""
            return f"=== NOTEBOOKLM (source-grounded) ===\n{ans}{tail}"
        except Exception as e:  # noqa: BLE001
            return f"[notebooklm REST error: {type(e).__name__} — check $NOTEBOOKLM_URL sidecar]"
    for cli in ("futron-notebooklm", "nlm", "notebooklm"):
        if shutil.which(cli):
            try:
                r = subprocess.run([cli, "research", query], capture_output=True, text=True, timeout=timeout)
                out = (r.stdout or "").strip()
                low = out.lower()
                # reject a usage/help/error dump (wrong subcommand) — don't feed that to an agent
                if out and not low.startswith(("usage:", "error", "[")) and "the following arguments" not in low:
                    return f"=== NOTEBOOKLM via {cli} ===\n{out[:3000]}"
            except Exception:  # noqa: BLE001
                pass
    return ("[notebooklm: no sidecar found. Stand one up for deep source-grounded research — "
            "`pip install notebooklm-py` (teng-lin, REST+MCP) and run its server, then set "
            "NOTEBOOKLM_URL=<research endpoint>; or install jacob-bd/notebooklm-mcp-cli (`nlm`). "
            "Until then, use research()/browse() — NotebookLM is enrichment, not required.]")


_REGISTRY = None  # process-lifetime cache of the OpenRouter /models listing


def _registry_cache():
    """Fetch the OpenRouter /models listing once per process (the eval queries it many times).
    Returns the data list, or an error string sentinel."""
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    import os, json
    key = (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_TIER1_API_KEY")
           or os.environ.get("OPENAI_API_KEY", ""))
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"User-Agent": _UA, "Accept": "application/json",
                     **({"Authorization": f"Bearer {key}"} if key else {})})
        with urllib.request.urlopen(req, timeout=25) as r:
            _REGISTRY = json.loads(r.read().decode("utf-8", "ignore")).get("data", [])
    except Exception as e:  # noqa: BLE001
        return f"[model_registry error: {type(e).__name__}]"
    return _REGISTRY


_PROVIDERS = ("deepseek", "kimi", "qwen", "gemini", "gemma", "grok", "mistral",
              "opus", "claude", "llama", "fable", "moonshot", "glm", "gpt", "openai")


def registry_hint(text: str, n: int = 25) -> str:
    """If a goal/sub-task names a model provider, return the AUTHORITATIVE OpenRouter registry slice
    for it so the agent reasons over REAL current ids, not hallucinated/stale ones. Empty when no
    provider is mentioned (zero cost). Shared by the agentic loop's preflight AND the swarm — the
    fix for the generic loop regressing on model-id goals (it had web noise, not ground truth)."""
    tl = (text or "").lower()
    hits = [p for p in _PROVIDERS if p in tl][:3]
    if not hits:
        return ""
    blocks = [model_registry("claude-opus" if p in ("opus", "claude") else p, n=n) for p in hits]
    return ("=== AUTHORITATIVE MODEL REGISTRY (live OpenRouter — use these EXACT ids, not memory) ===\n"
            + "\n".join(blocks))


def model_registry(query: str, n: int = 40) -> str:
    """Authoritative model lookup — query the OpenRouter /models REGISTRY (ground truth) for the
    current model ids. The RIGHT way to answer 'what's the newest model from X' is to read the
    registry, not guess from stale training or flaky blog snippets (web search surfaces exact
    post-cutoff slugs like 'kimi-k2.7' or 'opus-4.8' unreliably; the registry is canonical and
    deterministic). `query` = a substring (e.g. 'deepseek', 'gemini', 'kimi'); returns matching ids."""
    import os, json
    data = _registry_cache()
    if isinstance(data, str):       # error sentinel
        return data
    q = query.lower().strip()
    ids = sorted(m["id"] for m in data if q in m["id"].lower())
    if not ids:
        return f"[model_registry: no ids matching '{query}']"
    return (f"OpenRouter registry — live model ids matching '{query}' (authoritative):\n"
            + "\n".join("  " + i for i in ids[:n]))


def _x_article_from_status(user: str, tid: str) -> str | None:
    """Full no-auth read of a tweet OR long-form X Article via the FxTwitter/FixTweet mirror
    (the ONLY no-auth backend that returns the FULL article body — verified 2026-06-15;
    syndication CDN + guest-token GraphQL return only the article's title/preview). For an
    Article the tweet `text` is EMPTY; the body lives in article.content.blocks. Returns None
    if every mirror failed (so the caller can fall through to oembed / honest message)."""
    import json as _j
    for host in ("api.fxtwitter.com", "api.vxtwitter.com"):
        try:
            req = urllib.request.Request(f"https://{host}/{user}/status/{tid}",
                                         headers={"User-Agent": _UA})
            d = _j.loads(urllib.request.urlopen(req, timeout=15).read())
            t = d.get("tweet") or d  # vxtwitter is flatter
            txt = (t.get("text") or "").strip()
            art = t.get("article")
            if isinstance(art, dict):
                blocks = (art.get("content") or {}).get("blocks", [])
                body = "\n".join(b.get("text", "").strip() for b in blocks if b.get("text"))
                if body:
                    return f"[X ARTICLE] {art.get('title', '').strip()}\n\n{body}".strip()
            if txt:
                return txt
        except Exception:  # noqa: BLE001
            continue
    return None


def _playwright_python() -> str | None:
    """Find a python interpreter that can actually run Playwright (the package importable AND a
    browser installed). VERITY's own interpreter often can't (PEP-668 blocks the install, or it's
    a fresh Homebrew python), so we look outward: env override → common venvs → our own. Returns
    the interpreter path, or None if none can render. Keeps VERITY's core stdlib-only — the render
    is an optional, out-of-process capability."""
    import os
    import shutil
    import subprocess
    import sys
    cands = []
    if (e := os.environ.get("VERITY_PLAYWRIGHT_PYTHON")):
        cands.append(e)
    cands += [os.path.expanduser("~/.agent-reach-venv/bin/python"),
              os.path.expanduser("~/.verity-harness/venv/bin/python"), sys.executable]
    if (w := shutil.which("python3")):
        cands.append(w)
    seen = set()
    for c in cands:
        if not c or c in seen or not os.path.exists(c):
            continue
        seen.add(c)
        try:
            r = subprocess.run([c, "-c", "import playwright.sync_api"],
                               capture_output=True, timeout=15)
            if r.returncode == 0:
                return c
        except Exception:  # noqa: BLE001
            continue
    return None


_X_NO_SESSION = "\x01NO_X_SESSION\x01"   # sentinel: renderer ran but found no logged-in X session

# Self-contained render script — runs OUT OF PROCESS in a Playwright-capable python (which also
# has `cryptography`), so VERITY's own interpreter stays pure-stdlib. It discovers the X auth
# cookie itself (env → ~/.agent-reach/config.json → ~/.verity-harness/x.json → decrypt from Chrome,
# scanning EVERY profile — the 2026-06-15 lesson: a live session lived in 'Profile 1', not Default),
# then renders the auth-walled article. Cookies stay local; nothing is uploaded.
_X_RENDER_SCRIPT = r'''
import sys, os, json, glob, hashlib, sqlite3, shutil, tempfile, subprocess
url, ua = sys.argv[1], sys.argv[2]

def find_cookie():
    at = os.environ.get("TWITTER_AUTH_TOKEN") or os.environ.get("X_AUTH_TOKEN")
    ct0 = os.environ.get("TWITTER_CT0") or os.environ.get("X_CT0")
    if at and ct0: return at, ct0
    for cfgp in ("~/.agent-reach/config.json", "~/.verity-harness/x.json"):
        try:
            cfg = json.load(open(os.path.expanduser(cfgp)))
            tw = cfg.get("twitter") or cfg.get("twitter_cookies") or cfg
            if tw.get("auth_token") and tw.get("ct0"): return tw["auth_token"], tw["ct0"]
        except Exception: pass
    if sys.platform == "darwin":
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            pw = subprocess.run(["security","find-generic-password","-wa","Chrome","-s","Chrome Safe Storage"],
                                capture_output=True, text=True, timeout=10).stdout.strip().encode()
            if pw:
                key = hashlib.pbkdf2_hmac("sha1", pw, b"saltysalt", 1003, 16)
                def dec(buf):
                    if not buf or buf[:3] != b"v10": return ""
                    d = Cipher(algorithms.AES(key), modes.CBC(b" "*16), backend=default_backend()).decryptor()
                    pt = d.update(buf[3:]) + d.finalize(); pt = pt[:-pt[-1]]
                    if len(pt) >= 32:
                        try: pt[:32].decode("ascii")
                        except Exception: pt = pt[32:]
                    return pt.decode("utf-8","ignore")
                base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
                for prof in ["Default"] + [os.path.basename(p) for p in glob.glob(os.path.join(base,"Profile *"))]:
                    for sub in ("Cookies","Network/Cookies"):
                        src = os.path.join(base, prof, sub)
                        if not os.path.exists(src): continue
                        tmp = tempfile.mktemp(suffix=".db")
                        try:
                            shutil.copy2(src, tmp); con = sqlite3.connect(tmp)
                            rows = con.execute("SELECT name,encrypted_value FROM cookies WHERE host_key LIKE '%x.com%' AND name IN ('auth_token','ct0')").fetchall()
                            con.close(); ck = {n: dec(v) for n,v in rows}
                            if ck.get("auth_token") and ck.get("ct0"): return ck["auth_token"], ck["ct0"]
                        except Exception: pass
                        finally:
                            try: os.unlink(tmp)
                            except OSError: pass
        except Exception: pass
    return None

ck = find_cookie()
if not ck:
    sys.stdout.write("\x01NO_X_SESSION\x01"); sys.exit(0)
from playwright.sync_api import sync_playwright
at, ct0 = ck
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(user_agent=ua)
    ctx.add_cookies([{"name":"auth_token","value":at,"domain":".x.com","path":"/"},
                     {"name":"ct0","value":ct0,"domain":".x.com","path":"/"}])
    pg = ctx.new_page()
    pg.goto(url, wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(6000)
    sys.stdout.write(pg.inner_text("body"))
    b.close()
'''


def _x_render_article(url: str, max_chars: int = 16000) -> str | None:
    """Read an auth-walled X article (the bare /i/article/<id> permalink) through YOUR logged-in
    browser session — the durable path (no rotating GraphQL hash). Runs OUT OF PROCESS via a
    Playwright-capable python (see _playwright_python), which self-discovers the X cookie and
    renders the page, so VERITY's own interpreter stays pure-stdlib. Returns the cleaned article
    text; the _X_NO_SESSION sentinel if the renderer ran but found no live session; or None if no
    Playwright-capable python exists (→ run `python3 -m verity web-setup`). Verified end-to-end
    2026-06-15 (16K-char article read through a logged-in Chrome cookie)."""
    import subprocess
    py = _playwright_python()
    if not py:
        return None
    try:
        r = subprocess.run([py, "-c", _X_RENDER_SCRIPT, url, _UA],
                           capture_output=True, text=True, timeout=90)
        txt = r.stdout
    except Exception:  # noqa: BLE001
        return None
    if txt.strip() == _X_NO_SESSION:
        return _X_NO_SESSION
    if not txt or not txt.strip():
        return None
    flat = _WS.sub("\n", txt).strip()
    # trim the X nav-chrome prefix (everything up to the article, which starts after a long
    # left-rail menu ending in "More"/"Post") and the reply/footer tail.
    for marker in ("\nMore\nPost\n", "\nMore\n", "keyboard shortcuts\n"):
        i = flat.find(marker)
        if i != -1:
            flat = flat[i + len(marker):]
            break
    for tail in ("\nPost your reply", "\nDiscover more", "\nWho to follow", "\nMore Tweets"):
        j = flat.find(tail)
        if j != -1:
            flat = flat[:j]
    return flat.strip()[:max_chars] or None


def fetch_tweet(url: str) -> str:
    """Read an X/Twitter post — incl. long-form ARTICLES — WITHOUT an API key wherever possible.
    Handles every URL form: x.com/<user>/status/<id>, /i/status/<id>, /i/web/status/<id>, a bare
    tweet id, AND the article permalink x.com/i/article/<id>.

    • status / bare-id  → FxTwitter (full article body) → vxtwitter → oembed. Fully autonomous.
    • /i/article/<id>   → the article id is NOT a tweet id and has NO no-auth resolver (verified
      across 7 backends 2026-06-15: fxtwitter/vxtwitter 404, syndication/guest-GraphQL body-gated,
      oembed/redirect refused). Needs a one-time X cookie → uses twitter-cli/cookie if available,
      else returns an HONEST, actionable next step — NOT 'unreadable' (the premature negative Rule 6
      forbids). The autonomous workaround is almost always available: the SAME article opens at its
      status URL (x.com/<author>/status/<id>), which reads with zero auth."""
    import re as _re
    # ---- bare article permalink: x.com/i/article/<id> ----
    am = _re.search(r"(?:x|twitter)\.com/i/article/(\d+)", url)
    if am:
        aid = am.group(1)
        # Render through YOUR logged-in session (cookie self-discovered out-of-process: env /
        # agent-reach cfg / ~/.verity-harness/x.json / decrypted from Chrome, ALL profiles).
        body = _x_render_article(url)
        if body and body != _X_NO_SESSION and len(body) > 200:
            return f"[X ARTICLE] {body}"
        if body == _X_NO_SESSION:
            return (f"[x article {aid}: the reader ran but found no logged-in X session. Two fixes: "
                    "(1) paste the SAME article's status URL — x.com/<author>/status/<id> — which "
                    "reads FULLY with zero auth; or (2) be logged into x.com in Chrome (any profile "
                    "— the cookie is auto-decrypted) or set TWITTER_AUTH_TOKEN+TWITTER_CT0. "
                    "Do NOT conclude 'unreadable'.]")
        # body is None → no Playwright-capable python found.
        return (f"[x article {aid}: bare /i/article permalinks need a headless renderer (the article "
                "id isn't a tweet id, so there's no no-auth API path). One-time enable: "
                "`python3 -m verity web-setup` (installs Playwright + Chromium into an isolated venv). "
                "Or just paste the article's STATUS URL — x.com/<author>/status/<id> — which reads "
                "FULLY with zero auth. Do NOT conclude 'unreadable'.]")
    # ---- status / bare-id forms ----
    m = (_re.search(r"(?:x|twitter)\.com/([^/]+)/status/(\d+)", url)
         or _re.search(r"(?:x|twitter)\.com/i/web/status/(\d+)", url))
    if m and m.lastindex == 2:
        user, tid = m.group(1), m.group(2)
    elif m:                       # /i/web/status/<id> — handle unknown
        user, tid = "i", m.group(1)
    else:
        user, tid = "i", (url if url.isdigit() else "")
    if tid:
        got = _x_article_from_status(user, tid)
        if got:
            return got
    try:
        u = "https://publish.twitter.com/oembed?omit_script=true&url=" + urllib.parse.quote(url)
        d = _json(u)
        return (html.unescape(_TAG.sub(" ", d.get("html", ""))).strip()
                or "[no tweet text — try Jina r.jina.ai/<url> or `agent-reach configure twitter`]")
    except Exception as e:  # noqa: BLE001
        return (f"[x/twitter error: {type(e).__name__} — FxTwitter+oembed both failed. Next: "
                f"curl https://r.jina.ai/{url} , or `agent-reach configure twitter` (cookie). "
                "Do NOT conclude 'unreadable' without trying these.]")


# read_x: intuitive alias for fetch_tweet (one implementation, both names).
def read_x(url_or_id: str, user: str = "") -> str:
    """Alias of fetch_tweet — read an X/Twitter post or article without a key. See fetch_tweet."""
    return fetch_tweet(url_or_id)


def youtube_transcript(url_or_id: str, max_chars: int = 12000) -> str:
    """Pull a YouTube transcript WITHOUT an API key. Prefers yt-dlp if installed
    (most robust); the agent can `pip install yt-dlp` first. Returns the text."""
    import shutil
    import subprocess
    if not shutil.which("yt-dlp"):
        return ("[yt-dlp not installed — run: pip install yt-dlp   then retry. "
                "yt-dlp --write-auto-sub --skip-download --sub-format vtt <url>]")
    try:
        import os
        import tempfile
        d = tempfile.mkdtemp()
        subprocess.run(["yt-dlp", "--write-auto-sub", "--write-sub", "--sub-lang", "en",
                        "--skip-download", "--sub-format", "vtt",
                        "-o", os.path.join(d, "t.%(ext)s"), url_or_id],
                       capture_output=True, text=True, timeout=90)
        vtts = [f for f in os.listdir(d) if f.endswith(".vtt")]
        if not vtts:
            return "[no captions available for this video]"
        raw = open(os.path.join(d, vtts[0]), encoding="utf-8", errors="ignore").read()
        # strip VTT timestamps/markup → plain text
        lines = [ln for ln in raw.splitlines()
                 if ln.strip() and "-->" not in ln and not ln.strip().isdigit()
                 and not ln.startswith(("WEBVTT", "Kind:", "Language:"))]
        seen, out = set(), []
        for ln in lines:
            t = _TAG.sub("", ln).strip()
            if t and t not in seen:
                seen.add(t); out.append(t)
        return " ".join(out)[:max_chars] or "[empty transcript]"
    except Exception as e:  # noqa: BLE001
        return f"[youtube error: {type(e).__name__}]"


def system_web_tools() -> str:
    """REUSE-FIRST for web access: list the web fetch/search/scrape/browse tools ALREADY
    installed on THIS system, so the LLM uses them before hand-rolling a scraper (the mistake
    this function exists to prevent). Portable: scans PATH for the common cascade/scrape/search
    CLIs by name (FUTRON's futron-scrape/-mcp-search/-cua-fetch/-crawl4ai, plus generic
    crawl4ai, scrapy, firecrawl, jina, etc.). Empty result = nothing installed → use a keyed
    search (BRAVE/TAVILY) or browse()."""
    import os
    import shutil
    # canonical web-access command-name fragments, in rough preference order
    wanted = ("futron-scrape", "futron-mcp-search", "futron-local-researcher", "futron-cua-fetch",
              "futron-crawl4ai-scrape", "futron-claw", "futron-research", "crawl4ai", "scrapy",
              "firecrawl", "jina", "trafilatura", "newspaper", "playwright", "browser-use",
              # AGENTIC AUTOMATION (click/fill/navigate/login — the 'automate through blockers' arsenal):
              # browser-use (pip, agentic browser actions), openclick (npm, a11y-driven clicking),
              # avani-cua/futron-claw (CUA). The agent PREFERS these over hand-driving a brittle scraper.
              "openclick", "avani-cua",
              # agent-reach: multi-backend router for walled platforms (Twitter/X, Reddit, XHS,
              # Bilibili, YouTube, GitHub, LinkedIn) — `agent-reach doctor --json` shows the live
              # backend per platform. The Rule-6 fix for "this site is unreadable" (2026-06-15).
              "agent-reach",
              # platform scrapers (music/chart/social) — verified working 2026-06-14:
              "futron-pw-chart",       # Playwright JS-render: Shazam charts, generic url+css
              "futron-dj-tiktok-id",   # TikTok trending → Shazam-FINGERPRINT real song (cracks mistagged "original sound") + Gemini dance ID
              "futron-dj-viral-dig",   # multi-source viral aggregator: Shazam+TikTok(fp)+Reddit+Billboard+kworb, lib HAVE/NEW
              "futron-tiktok-cookie",  # live TikTok session cookie from Chrome (enables cookie-auth/CUA)
              "futron-tiktok-query",   # TikTok search/trending (flaky anti-bot; best-effort)
              "futron-spotify",        # Spotify get/search/create (token cascade)
              "futron-dj-crate-dig", "futron-dj-event-builder")  # multi-source crate-dig + radio scrape
    found = []
    seen = set()
    pathdirs = os.environ.get("PATH", "").split(os.pathsep)
    for frag in wanted:
        # exact-ish: a command whose name contains the fragment
        for d in pathdirs[:60]:
            try:
                for f in os.listdir(d):
                    if frag in f and not f.startswith(".") and ".bak" not in f and f not in seen:
                        if shutil.which(f):
                            seen.add(f); found.append(f)
            except OSError:
                continue
    if not found:
        return ""
    return ("WEB-ACCESS TOOLS ALREADY ON THIS SYSTEM — PREFER THESE before hand-rolling any "
            "fetch/search/scrape (run `<tool> --help` to learn its interface):\n  "
            + ", ".join(sorted(set(found))[:20]))


def _is_garbage(block: str) -> bool:
    """QC: True if a search block is an error/empty/blocked response, NOT real evidence.
    The whole point — never feed the model a wall of '[no results]' / CAPTCHA text and call
    it 'findings' (garbage-in makes a weak model do WORSE than its priors)."""
    b = (block or "").lower()
    bad = ("no results", "error:", "[github error", "[reddit error", "[hn", "[so",
           "captcha", "complete the following challenge", "bots use", "unavailable",
           "structured parse failed", "[research", "no result")
    return len(block.strip()) < 30 or any(x in b for x in bad)


def research(query: str) -> str:
    """Multi-platform sweep with self-healing QC: prefer the highest-quality backend, DROP any
    garbage (error/empty/CAPTCHA) block so the model never reasons over noise, reuse the
    system's own scraping cascade if present, and return an HONEST failure signal when nothing
    real comes back — so the caller's error-handling gate can react instead of hallucinating."""
    import shutil
    import subprocess
    blocks = []
    # Best general web first (Brave/Tavily if keyed — Google-quality), then GitHub for tools.
    for name, body in (("WEB", web_search(query, 5)),
                       ("GITHUB (tools / open-source)", search_github(query))):
        if not _is_garbage(body):
            blocks.append((name, body))
    # SHORT-CIRCUIT (perf): if a good web/GitHub result is already in hand, SKIP the community
    # backends. They're slow (rate-limit/timeout waits) and usually get QC-dropped anyway — that
    # wasted latency was stalling eval/agent runs. Only consult them when web came back thin.
    if not blocks:
        for name, fn in (("REDDIT (real-world experience)", search_reddit),
                         ("HACKER NEWS", search_hackernews),
                         ("STACKOVERFLOW (solutions)", search_stackoverflow)):
            try:
                r = fn(query)
                if not _is_garbage(r):
                    blocks.append((name, r))
            except Exception:  # noqa: BLE001
                pass
    # REUSE-FIRST self-heal: if web came back thin and the system has its own scraping cascade
    # (e.g. FUTRON's futron-scrape / crawl4ai), use the agent's own arsenal before giving up.
    if not blocks:
        for tool in ("futron-mcp-search", "futron-scrape"):
            if shutil.which(tool):
                try:
                    r = subprocess.run([tool, query], capture_output=True, text=True, timeout=40)
                    if r.stdout.strip() and not _is_garbage(r.stdout):
                        blocks.append((f"SYSTEM CASCADE ({tool})", r.stdout[:2500])); break
                except Exception:  # noqa: BLE001
                    pass
    if not blocks:
        return (f"[research: NO real evidence for '{query[:60]}' — every backend was empty/blocked. "
                "Try a narrower query, browse() a specific URL, or set a search key "
                "(BRAVE_API_KEY / TAVILY_API_KEY). Do NOT answer from priors as if verified.]")
    return "\n\n".join(f"=== {name} ===\n{body}" for name, body in blocks)


def browse(url: str, screenshot: str | None = None, wait_ms: int = 4000,
           max_chars: int = 12000) -> str:
    """Render a JS-heavy page in a REAL headless browser and return its visible text
    — for content static fetch() can't see (truncated threads, SPAs, infinite-scroll,
    login-gated views). Optionally save a full-page screenshot to `screenshot`.

    Uses Playwright. If absent, returns install guidance (the agent should then run
    `pip install playwright && playwright install chromium` and retry). For richer
    agentic browsing (clicking, scrolling, form-fill), install Browser Use
    (github.com/browser-use/browser-use) and drive it from the shell."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:  # noqa: BLE001
        return ("[playwright not installed — run: pip install playwright && "
                "playwright install chromium, then retry browse(). For agentic web "
                "tasks (scroll/click/scrape) use Browser Use: pip install browser-use]")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            pg = b.new_page(user_agent=_UA)
            pg.goto(url, wait_until="networkidle", timeout=30000)
            pg.wait_for_timeout(wait_ms)
            text = pg.inner_text("body")
            if screenshot:
                pg.screenshot(path=screenshot, full_page=True)
            b.close()
        out = _WS.sub("\n\n", text).strip()[:max_chars]
        return out + (f"\n\n[screenshot saved → {screenshot}]" if screenshot else "")
    except Exception as e:  # noqa: BLE001
        return f"[browse error: {type(e).__name__}: {e}]"


def capabilities_guide() -> str:
    _own = system_web_tools()
    _reuse = (("\n⭐ REUSE-FIRST — " + _own + "\n") if _own else
              "\n⭐ REUSE-FIRST — before hand-rolling a scraper, run "
              "`compgen -c | grep -iE 'scrape|crawl|search|fetch'` to see if this system already "
              "has a web tool; if not, set BRAVE_API_KEY/TAVILY_API_KEY for reliable search.\n")
    return """\
AGENT CAPABILITIES — you can go GET information, not just reason from memory.
""" + _reuse + """
You have a REAL SHELL (ShellExecutor). That means you can:

  • WEB ACCESS — REUSE-FIRST (don't reinvent): if the box above lists installed web/scrape
      tools (e.g. futron-scrape, crawl4ai, browser-use), PREFER them — they're battle-tested
      cascades that already handle CAPTCHA/JS/login/rate-limits. Hand-rolling DDG/curl is the
      LAST resort, not the first. (This rule exists because the harness's own author once
      hand-rolled a scraper while futron-scrape sat one command away.)
  • FETCH the web:
      python3 -c "from verity.tools import fetch; print(fetch('URL'))"
      …or just: curl -sL URL   (or a system scrape tool from the REUSE-FIRST box above)
  • SEARCH the web (uses Brave/Tavily if a key is set — reliable; else free scraping):
      python3 -c "from verity.tools import web_search; print(web_search('query'))"
  • MULTI-PLATFORM RESEARCH (find rare/inside knowledge + open-source tools):
      python3 -c "from verity.tools import research; print(research('your topic'))"
      sweeps GitHub (tools/forks) + Reddit + Hacker News + StackOverflow + web at once.
      Or target one: search_github / search_reddit / search_hackernews / search_stackoverflow.
      Use this to find uncommon/modified/open-source solutions others have shared.
  • DEEP SOURCE-GROUNDED RESEARCH (NotebookLM) — synthesis WITH citations over many docs/videos,
    for what a flat search can't do (onboard a codebase, decode legacy code + its git history,
    compress a long issue/PR thread into problem→options→decision):
      python3 -c "from verity.tools import notebooklm; print(notebooklm('your question', sources=['url','file']))"
      Best-effort enrichment (rides Google's undocumented API → not a hard dependency). Run a sidecar:
      teng-lin/notebooklm-py (16k★, REST+MCP) or jacob-bd/notebooklm-mcp-cli (`nlm`); set NOTEBOOKLM_URL.
  • CURRENT MODEL IDS — read the REGISTRY, don't guess (BLOCKER for 'newest model' questions):
      python3 -c "from verity.tools import model_registry; print(model_registry('deepseek'))"
      …or: python3 -m verity models claude-opus   (substring: 'gemini','kimi','qwen3','grok',…)
      Returns the LIVE OpenRouter /models listing — ground truth for which models exist NOW and
      their exact ids. Model names move fast (kimi-k2.7, opus-4.8, gemini-3.5, deepseek-v4,
      qwen3.7, gemma-4, grok-4.3, mistral-large-2512 are all post-2025); your TRAINING is stale
      and web snippets rarely contain the exact slug. NEVER assert "the newest X is …" or wire a
      model id from memory — query the registry first, then use/route the verified id.
  • READ X/TWITTER (no key, incl. long-form ARTICLES):  fetch_tweet('https://x.com/user/status/ID')
      (alias: read_x). Tries FxTwitter then oembed; for articles the body is auto-extracted.
      Walled platform (Reddit/XHS/Bilibili/YouTube/LinkedIn/GitHub)? `agent-reach doctor --json`
      shows the live backend; agent-reach routes the read for you (Rule-6 fix for "unreadable").
  • POST TO X/TWITTER:  from verity.social_x import post_to_x; post_to_x(text, image_path=...)
      Uses the official API (OAuth 1.0a, browser-free, supports media) — set X_CONSUMER_KEY/
      X_CONSUMER_SECRET/X_ACCESS_TOKEN/X_ACCESS_SECRET (free at developer.x.com).
      WARNING: the cookie-HTTP trick (auth_token+ct0 → GraphQL CreateTweet) now SILENTLY FAILS
      — X requires an x-client-transaction-id header for writes, so it returns 200 + empty
      result and posts NOTHING. NEVER trust a 200 as "posted"; verify a real tweet id. The only
      no-API-key path that works is the real browser client (attach media via clipboard paste).
  • YOUTUBE TRANSCRIPT (no key, via yt-dlp):  youtube_transcript('https://youtu.be/ID')
      (run `pip install yt-dlp` first if missing)
  • INSTALL any tool you need, then use it:
      pip install <pkg>      npm install -g <pkg>      brew install <tool>
      e.g. yt-dlp (video), jq (json), gh (github), pandoc, ripgrep, pdftotext
  • BROWSE a JS-heavy/truncated page (renders in a real browser, returns full text,
    optional screenshot — for SPAs, threads, infinite-scroll, anything fetch() can't see):
      python3 -c "from verity.tools import browse; print(browse('URL', screenshot='out.png'))"
      (run `pip install playwright && playwright install chromium` once if prompted)
  • AGENTIC BROWSING (scroll/click/fill/scrape at scale):
      pip install browser-use   # github.com/browser-use/browser-use (98k★) — drive via shell
  • COMPUTER USE / desktop automation:
      install a computer-use tool (e.g. pyautogui) and script it via the shell.
  • MCP servers (Model Context Protocol) — REUSE BEFORE BUILDING a tool:
      before writing an integration, check if a ready MCP server already exists —
      catalog: github.com/punkpeye/awesome-mcp-servers (GitHub, Slack, Linear,
      Stripe, Postgres, Notion, and hundreds more). Install it and speak JSON-RPC
      over stdio rather than coding the integration yourself.

RULE: if you lack information to finish a task, DO NOT GUESS — go fetch/search/
install the tool and get it. Verify what you find before relying on it.""" + _detected_tools()


def _detected_tools() -> str:
    """If richer scrape/search CLIs are installed (e.g. a FUTRON-style arsenal),
    surface them so the agent uses the best available reach."""
    import shutil
    extra = {
        "futron-scrape": "universal scrape cascade (reddit/hn/github/SO/wiki/...)",
        "futron-github-query": "GitHub deep search + classify",
        "futron-reddit-query": "Reddit (auth-backed, beats the public API block)",
        "futron-x-query": "X / Twitter search",
        "futron-youtube-query": "YouTube search + transcripts",
        "futron-perplexity-query": "Perplexity AI web research",
        "futron-web-to-api": "convert any website into a callable API",
        "futron-notebooklm": "NotebookLM deep source-grounded research (via verity.tools.notebooklm)",
        "nlm": "NotebookLM CLI (jacob-bd) — notebooks/sources/grounded chat",
    }
    found = [(c, d) for c, d in extra.items() if shutil.which(c)]
    if not found:
        return ""
    lines = ["\n\nDETECTED ADVANCED TOOLS on this machine — prefer these for hard sources:"]
    lines += [f"  • {c}  — {d}" for c, d in found]
    return "\n".join(lines)

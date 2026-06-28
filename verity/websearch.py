#!/usr/bin/env python3
"""`verity websearch` — the web as a live, infinite RAG the model consults FIRST.

The "go research the six sources" gate (R60) is only real if the model can actually search.
This is the multi-provider, FAILOVER search layer — because a single provider WILL go down,
rate-limit, or change, and the gate cannot afford to fail. It tries providers in order and
returns the first that answers, so it degrades gracefully all the way down to a free, no-key floor.

Providers (auto-detected by env var; the free ones need NOTHING):
  • Tavily        TAVILY_API_KEY            (LLM-native search/RAG)
  • Perplexity    PERPLEXITY_API_KEY        (answer + sources)
  • Brave         BRAVE_API_KEY
  • Google CSE    GOOGLE_CSE_KEY + GOOGLE_CSE_CX
  • SearXNG       SEARX_URL (any public/self-hosted instance — free, no key)
  • DuckDuckGo    (free, no key — the always-available floor)
  • GitHub        (free; api.github.com code/repo search for repo-specific queries)

  python3 -m verity websearch "agentic web search api"          # search (first provider that answers)
  python3 -m verity websearch --fetch https://example.com/page  # scrape ANY page → readable text
  python3 -m verity websearch --all "query"                     # query every available provider, merge+dedupe

Stdlib-only. Returns normalized [{title, url, snippet, source}].
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124 Safari/537.36")


def _get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": _UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _post(url, data, headers=None, timeout=20):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, body, {"User-Agent": _UA, "Content-Type": "application/json",
                                             **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


# ── providers: each returns [{title,url,snippet,source}] or raises ────────────
def _tavily(q, n):
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("no key")
    d = json.loads(_post("https://api.tavily.com/search",
                         {"api_key": key, "query": q, "max_results": n}))
    return [{"title": r.get("title", ""), "url": r.get("url", ""),
             "snippet": r.get("content", "")[:300], "source": "tavily"} for r in d.get("results", [])]


def _perplexity(q, n):
    key = os.environ.get("PERPLEXITY_API_KEY")
    if not key:
        raise RuntimeError("no key")
    d = json.loads(_post("https://api.perplexity.ai/chat/completions",
                  {"model": "sonar", "messages": [{"role": "user", "content": q}]},
                  {"Authorization": f"Bearer {key}"}))
    txt = d["choices"][0]["message"]["content"]
    cites = d.get("citations", [])[:n]
    return [{"title": "perplexity answer", "url": cites[0] if cites else "",
             "snippet": txt[:600], "source": "perplexity"}] + \
           [{"title": c, "url": c, "snippet": "", "source": "perplexity-cite"} for c in cites]


def _brave(q, n):
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        raise RuntimeError("no key")
    d = json.loads(_get("https://api.search.brave.com/res/v1/web/search?q=" +
                        urllib.parse.quote(q) + f"&count={n}",
                        {"X-Subscription-Token": key, "Accept": "application/json"}))
    return [{"title": r.get("title", ""), "url": r.get("url", ""),
             "snippet": r.get("description", "")[:300], "source": "brave"}
            for r in d.get("web", {}).get("results", [])][:n]


def _google_cse(q, n):
    key, cx = os.environ.get("GOOGLE_CSE_KEY"), os.environ.get("GOOGLE_CSE_CX")
    if not (key and cx):
        raise RuntimeError("no key")
    d = json.loads(_get(f"https://customsearch.googleapis.com/customsearch/v1?key={key}&cx={cx}"
                        f"&num={min(n,10)}&q=" + urllib.parse.quote(q)))
    return [{"title": r.get("title", ""), "url": r.get("link", ""),
             "snippet": r.get("snippet", "")[:300], "source": "google-cse"} for r in d.get("items", [])]


# Public SearXNG instances that expose JSON — FREE, NO KEY, aggregate Google/Bing/etc. Tried in
# order until one answers (instances rotate/rate-limit, so the list IS the resilience).
_PUBLIC_SEARX = ("https://searx.be", "https://search.inetol.net", "https://baresearch.org",
                 "https://priv.au", "https://searx.tiekoetter.com", "https://opnxng.com")

def _searx(q, n):
    bases = [os.environ["SEARX_URL"]] if os.environ.get("SEARX_URL") else list(_PUBLIC_SEARX)
    for base in bases:
        try:
            d = json.loads(_get(base.rstrip("/") + "/search?format=json&q=" + urllib.parse.quote(q), timeout=10))
            rows = [{"title": r.get("title", ""), "url": r.get("url", ""),
                     "snippet": (r.get("content", "") or "")[:300], "source": "searx"}
                    for r in d.get("results", [])][:n]
            if rows:
                return rows
        except Exception:
            continue
    raise RuntimeError("no searx instance answered")


def _perplexity_free(q, n):
    """Perplexity-grade answer WITHOUT an API key, via the OSS reverse-engineered lib (anonymous,
    no account). Install the KEY-FREE one from GitHub (NOT the PyPI `perplexityai`, which is the
    official keyed SDK):  pip install git+https://github.com/helallao/perplexity-ai
    Skipped cleanly if not installed OR if only the keyed SDK is present."""
    try:
        from perplexity import Perplexity
        client = Perplexity()                          # keyless construct; official SDK raises here
    except Exception:
        raise RuntimeError("key-free perplexity not installed (helallao/perplexity-ai)")
    resp = client.search(q)
    ans = resp.get("answer", "") if isinstance(resp, dict) else str(resp)
    return [{"title": "perplexity (free)", "url": "", "snippet": ans[:600], "source": "perplexity-free"}]


def _ddg(q, n):
    """Free, no-key floor — DuckDuckGo HTML endpoint."""
    html = _get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q))
    out = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        url, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        # DDG wraps targets in a redirect; pull the real uddg= param
        rm = re.search(r"uddg=([^&]+)", url)
        if rm:
            url = urllib.parse.unquote(rm.group(1))
        out.append({"title": title, "url": url, "snippet": "", "source": "ddg"})
        if len(out) >= n:
            break
    return out


def _github(q, n):
    """Niche: repo/code search (free, no key for low rate). Use when the query smells repo-ish."""
    d = json.loads(_get("https://api.github.com/search/repositories?per_page=" + str(n) +
                        "&q=" + urllib.parse.quote(q), {"Accept": "application/vnd.github+json"}))
    return [{"title": r["full_name"], "url": r["html_url"],
             "snippet": (r.get("description") or "")[:200] + f" ★{r.get('stargazers_count',0)}",
             "source": "github"} for r in d.get("items", [])][:n]


# priority: best/keyed first, free floor last (so it ALWAYS has something to fall to)
# keyed first (best when keys exist) → then FREE/no-key quality (perplexity-free, public searx) →
# DDG floor. The free tier alone now gives Perplexity/aggregated-engine quality WITHOUT any key.
PROVIDERS = [_tavily, _perplexity, _brave, _google_cse, _perplexity_free, _searx, _ddg]


def search(query: str, n: int = 5, *, all_providers: bool = False) -> list:
    """First provider that answers wins (failover). all_providers=True merges every one."""
    results, errors = [], []
    provs = PROVIDERS + ([_github] if re.search(r"\b(repo|github|library|sdk|package|oss|tool)\b", query, re.I) else [])
    for p in provs:
        try:
            r = p(query, n)
            if r:
                if not all_providers:
                    return r
                results.extend(r)
        except Exception as e:
            errors.append(f"{p.__name__}:{str(e)[:40]}")
    if all_providers and results:
        seen, merged = set(), []
        for r in results:
            if r["url"] and r["url"] not in seen:
                seen.add(r["url"]); merged.append(r)
        return merged[: n * 2]
    return results  # [] if everything failed (errors available for logging)


def fetch(url: str, max_chars: int = 6000, select: str = "") -> str:
    """Scrape ANY page → readable MAIN-CONTENT text (readability-style, from ketch). Prefers
    <article>/<main>/role=main, strips chrome, preserves nothing but clean prose. `select` = a tag
    name (e.g. 'article','table') to target. Escalates to the browser tier for JS/auth-walled pages."""
    try:
        html = _get(url, timeout=20)
    except Exception as e:
        return _browser(url, max_chars) or f"(fetch failed: {e})"
    html = re.sub(r"<(script|style|head|nav|footer|aside|form|svg|noscript)[^>]*>.*?</\1>",
                  " ", html, flags=re.S | re.I)
    # readability: prefer the main content container if present
    body = ""
    if select:
        m = re.search(rf"<{select}\b[^>]*>(.*?)</{select}>", html, re.S | re.I)
        body = m.group(1) if m else ""
    if not body:
        for tag in (r'<article\b[^>]*>(.*?)</article>', r'<main\b[^>]*>(.*?)</main>',
                    r'<[^>]+role=["\']main["\'][^>]*>(.*?)</[^>]+>'):
            m = re.search(tag, html, re.S | re.I)
            if m and len(m.group(1)) > 200:
                body = m.group(1); break
    body = body or html
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 80:                      # thin/blocked (likely JS-rendered) → browser tier
        return _browser(url, max_chars) or text
    return text[:max_chars]


def _browser(url: str, max_chars: int = 6000) -> str:
    """Browser-tier escalation for JS-heavy / auth-walled pages that plain HTTP can't read — shells
    to the local OSS browser automation (futron-claw). Returns '' if unavailable (caller degrades).
    (REUSE: FUTRON's futron-claw / Claude-in-Chrome / Playwright; see subsystem-verity-websearch-rag.)"""
    import shutil as _sh, subprocess as _sp
    exe = _sh.which("futron-claw")
    if not exe:
        return ""
    try:
        r = _sp.run([exe, "read", url], capture_output=True, text=True, timeout=60)
        return (r.stdout or "").strip()[:max_chars] if r.returncode == 0 else ""
    except Exception:
        return ""


def as_context(query: str, n: int = 5) -> str:
    """One-call research → a compact context block for a planner/RAG prompt (used by `verity augment`)."""
    rows = search(query, n)
    if not rows:
        return ""
    return "\n".join(f"- {r['title']} ({r['source']}) {r['url']}\n  {r['snippet']}" for r in rows)


# ── six-source scoping (R60): search each canonical source explicitly, not just the open web ──
_SIX_SITES = {"github": "site:github.com", "reddit": "site:reddit.com",
              "x": "(site:x.com OR site:twitter.com OR site:nitter.net)",
              "youtube": "site:youtube.com", "stackoverflow": "site:stackoverflow.com",
              "hackernews": "site:news.ycombinator.com"}

def six_source(query: str, n_each: int = 3) -> list:
    """Search the canonical R60 sources explicitly (github/reddit/x/youtube/SO/HN + open web), so
    'research the six sources' is literal. PARALLEL multi-angle workers (agentic-loop Stage 3): each
    source is queried concurrently and aggregated, so coverage doesn't cost latency-per-source."""
    from concurrent.futures import ThreadPoolExecutor
    angles = list(_SIX_SITES.items()) + [("web", "")]
    def one(item):
        label, op = item
        try:
            return [(label, r) for r in search(f"{op} {query}".strip(), n_each)]
        except Exception:
            return []
    out, seen = [], set()
    with ThreadPoolExecutor(max_workers=len(angles)) as ex:
        for batch in ex.map(one, angles):
            for label, r in batch:
                if r["url"] and r["url"] not in seen:
                    seen.add(r["url"]); r["source"] = f"{label}:{r['source']}"; out.append(r)
    return out


# Search-decision classifier (agentic-loop Stage 1): skip web search when internal knowledge suffices
# (cost control). Heuristic by default; pass ask() for a model decision on borderline cases.
_NEEDS_WEB = re.compile(r"\b(latest|current|today|2025|2026|recent|now|news|price|version|release|"
                        r"who is|what is the best|compare|vs\b|review|trending|update|changelog|"
                        r"docs?\b|api\b|repo|github|deprecat|breaking change)\b", re.I)

def should_search(query: str, ask=None) -> bool:
    """True if the query likely needs FRESH/EXTERNAL info (research first); False for stable internal
    knowledge (math, definitions, code-from-spec). Saves a round-trip when search adds nothing."""
    if _NEEDS_WEB.search(query):
        return True
    if ask is None:
        return len(query.split()) > 12   # long/complex → research to be safe
    try:
        a = ask(f"Does answering this need CURRENT or EXTERNAL info (web search), or is it stable "
                f"internal knowledge? Reply SEARCH or INTERNAL only.\n\n{query}")
        return "SEARCH" in (a or "").upper()
    except Exception:
        return True


# ── iterative DEEP RESEARCH loop (ported from the agentic-web-search-agent-loop pattern) ──
def deep_research(query: str, *, ask, rounds: int = 2, n: int = 5, sources: bool = True) -> dict:
    """Search → let the model identify the most important GAP → refine the query → search again,
    until satisfied or `rounds` exhausted. `ask(prompt)->str` is the reasoner (injectable). When
    sources=True each round hits the SIX canonical sources explicitly (github/reddit/x/youtube/SO/HN
    + web), not just the open web. Returns {context, queries, results} — deduped, cited. This is what
    makes research THOROUGH instead of single-shot (the agentic-search-loop pattern)."""
    queries, results, seen = [], [], set()
    q = query
    _do = (lambda qq: six_source(qq, max(2, n // 2))) if sources else (lambda qq: search(qq, n))
    for i in range(max(1, rounds)):
        queries.append(q)
        for r in _do(q):
            if r["url"] and r["url"] not in seen:
                seen.add(r["url"]); results.append(r)
        if i == rounds - 1:
            break
        # ask the reasoner what's still missing → next query, or DONE.
        found = "\n".join(f"- {r['title']} ({r['source']})" for r in results[-n:])
        try:
            nxt = ask(f"Research goal: {query}\nResults so far:\n{found}\n\n"
                      f"What is the single most important follow-up SEARCH QUERY to fill the biggest "
                      f"remaining gap? Reply with ONLY the query, or exactly DONE if coverage is sufficient.").strip()
        except Exception:
            break
        if not nxt or nxt.upper().startswith("DONE") or nxt.lower() == q.lower():
            break
        q = nxt.splitlines()[0][:120]
    ctx = "\n".join(f"- {r['title']} ({r['source']}) {r['url']}\n  {r['snippet']}" for r in results)
    return {"context": ctx, "queries": queries, "results": results}


def _cli(argv: list) -> int:
    if not argv:
        print('usage: verity websearch "<query>" [--all] | --fetch <url>', file=sys.stderr); return 2
    if argv[0] == "--fetch" and len(argv) > 1:
        print(fetch(argv[1])); return 0
    all_p = "--all" in argv
    q = " ".join(a for a in argv if not a.startswith("--"))
    if "--six" in argv:                 # search the six canonical R60 sources explicitly
        rows = six_source(q)
        for r in rows:
            print(f"[{r['source']}] {r['title']}\n  {r['url']}".rstrip())
        return 0 if rows else 1
    if "--deep" in argv:                # iterative deepening loop (model refines the query)
        from .router import ask as _ask
        d = deep_research(q, ask=lambda p: _ask(p).text)
        print(f"# deep research — queries: {d['queries']}\n")
        print(d["context"]); return 0 if d["results"] else 1
    rows = search(q, all_providers=all_p)
    if not rows:
        print("(no provider returned results — set TAVILY_API_KEY/BRAVE_API_KEY/SEARX_URL "
              "or check connectivity; the free DuckDuckGo floor may be rate-limited)", file=sys.stderr)
        return 1
    for r in rows:
        print(f"[{r['source']}] {r['title']}\n  {r['url']}\n  {r['snippet']}".rstrip())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

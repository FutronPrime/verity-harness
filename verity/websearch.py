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


def _searx(q, n):
    base = os.environ.get("SEARX_URL")
    if not base:
        raise RuntimeError("no instance")
    d = json.loads(_get(base.rstrip("/") + "/search?format=json&q=" + urllib.parse.quote(q)))
    return [{"title": r.get("title", ""), "url": r.get("url", ""),
             "snippet": (r.get("content", "") or "")[:300], "source": "searx"}
            for r in d.get("results", [])][:n]


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
PROVIDERS = [_tavily, _perplexity, _brave, _google_cse, _searx, _ddg]


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


def fetch(url: str, max_chars: int = 6000) -> str:
    """Scrape ANY page → readable text (strip scripts/tags). For reading a result in depth."""
    html = _get(url, timeout=20)
    html = re.sub(r"<(script|style|head|nav|footer)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def as_context(query: str, n: int = 5) -> str:
    """One-call research → a compact context block for a planner/RAG prompt (used by `verity augment`)."""
    rows = search(query, n)
    if not rows:
        return ""
    return "\n".join(f"- {r['title']} ({r['source']}) {r['url']}\n  {r['snippet']}" for r in rows)


def _cli(argv: list) -> int:
    if not argv:
        print('usage: verity websearch "<query>" [--all] | --fetch <url>', file=sys.stderr); return 2
    if argv[0] == "--fetch" and len(argv) > 1:
        print(fetch(argv[1])); return 0
    all_p = "--all" in argv
    q = " ".join(a for a in argv if not a.startswith("--"))
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

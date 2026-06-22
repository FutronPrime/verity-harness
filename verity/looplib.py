#!/usr/bin/env python3
"""Loop Library bridge — wire VERITY to Forward Future's curated agentic-workflow catalog.

The Loop Library (Matthew Berman / Forward Future, signals.forwardfuture.ai/loop-library) is 50+ vetted
"loops" — reusable AI-agent workflow patterns, each with exactly VERITY's gate-disciplined shape:
  useWhen · prompt · verification · steps · keywords · related
That is a free, community-maintained GENE POOL of coordination strategies — precisely what promptos
orchestrates, coordinate learns, and discover evolves. This bridge pulls it in:

  • hint(goal)        — match relevant loops to a goal and inject them into the planner (REUSE-FIRST:
                        "a vetted recipe for this already exists — apply it"). CACHE-ONLY, so planning
                        stays fast + offline-safe; `verity looplib --sync` refreshes the cache.
  • seed_strategies() — convert matched loops into discover.py strategy candidates, so the evolutionary
                        search starts from HUMAN-VETTED strategies, not just the 4 built-in seeds.
  • learn integration — learn._scout also checks the library for a subject.

Endpoint is a stable JSON catalog (verified 2026-06-22: HTTP 200, schemaVersion'd):
  https://signals.forwardfuture.ai/loop-library/catalog.json   (loops[]: number,slug,title,url,
  category{slug,label},description,useWhen,prompt,verification{title,detail},steps[],keywords[],related[])

Pure stdlib (urllib). Cached to ~/.verity-harness/loop-library.json with a TTL. Graceful + zero-cost
offline: a missing/stale cache simply yields no hint (never blocks, never hallucinates a loop).
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.request

CATALOG_URL = os.environ.get("VERITY_LOOPLIB_URL",
                             "https://signals.forwardfuture.ai/loop-library/catalog.json")
CACHE = pathlib.Path(os.path.expanduser("~/.verity-harness/loop-library.json"))
TTL = int(os.environ.get("VERITY_LOOPLIB_TTL", str(7 * 86400)))   # refresh weekly by default
MAX_TEMPLATE = 600
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) verity-harness-looplib"


def _load_cache() -> dict:
    """Cache-only read (NO network) — used on the hot planning path. {} when absent/unreadable."""
    try:
        return json.loads(CACHE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def _cache_fresh() -> bool:
    try:
        return CACHE.exists() and (time.time() - CACHE.stat().st_mtime) < TTL
    except OSError:
        return False


def fetch_catalog(force: bool = False) -> dict:
    """Network fetch (+cache write). Returns the catalog dict, or the last cache on failure, or {}.
    Use this on explicit/learn paths; the planner hot path uses _load_cache() only."""
    if not force and _cache_fresh():
        return _load_cache()
    try:
        req = urllib.request.Request(CATALOG_URL, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        if isinstance(data, dict) and data.get("loops"):
            try:
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps(data))
            except OSError:
                pass
            return data
    except Exception:  # noqa: BLE001
        pass
    return _load_cache()    # honest fallback: last good cache (even if stale) or {}


def loops(allow_fetch: bool = False) -> list[dict]:
    cat = fetch_catalog() if allow_fetch else _load_cache()
    return cat.get("loops", []) if isinstance(cat, dict) else []


def _score(loop: dict, words: set[str], q: str) -> int:
    kw = [str(k).lower() for k in loop.get("keywords", [])]
    hay = " ".join([str(loop.get("title", "")), str(loop.get("description", "")),
                    str(loop.get("useWhen", "")), str(loop.get("category", {}).get("label", "")),
                    " ".join(kw)]).lower()
    kw_hits = sum(1 for k in kw if k and k in q)
    word_hits = sum(1 for w in words if w in hay)
    return kw_hits * 3 + word_hits


def match(goal: str, n: int = 3, allow_fetch: bool = False) -> list[dict]:
    q = (goal or "").lower()
    words = {w.strip(".,:;!?()[]\"'") for w in q.split() if len(w) > 3}
    scored = [(s, lp) for lp in loops(allow_fetch) if (s := _score(lp, words, q)) > 0]
    scored.sort(key=lambda x: (-x[0], x[1].get("number", "")))
    return [lp for _, lp in scored[:n]]


def hint(goal: str, n: int = 3) -> str:
    """Bounded planner injection (CACHE-ONLY): relevant vetted loops to apply for this goal. Empty when
    the cache is absent or nothing matches (zero-cost). Title+useWhen+slug only — the agent can pull the
    full prompt/steps via `verity looplib get <slug>` or the url, so this never bloats the plan."""
    hits = match(goal, n, allow_fetch=False)
    if not hits:
        return ""
    lines = ["=== LOOP LIBRARY — vetted agentic recipes that fit this goal (REUSE-FIRST; apply/adapt) ==="]
    for lp in hits:
        lines.append(f"  • [{lp.get('slug')}] {lp.get('title')} — {str(lp.get('useWhen',''))[:120]}")
    lines.append("  → full recipe: `verity looplib get <slug>`  (has prompt + verification + steps)")
    return "\n".join(lines)


def get(slug: str, allow_fetch: bool = True) -> dict | None:
    for lp in loops(allow_fetch):
        if lp.get("slug") == slug or lp.get("number") == slug:
            return lp
    return None


def render(loop: dict) -> str:
    """Human/agent-readable full loop."""
    if not loop:
        return "[loop not found — try `verity looplib --sync` then `verity looplib` to list]"
    v = loop.get("verification", {})
    steps = "\n".join(f"   {i+1}. {s}" for i, s in enumerate(loop.get("steps", [])))
    return (f"LOOP {loop.get('number')} · {loop.get('title')}  [{loop.get('category',{}).get('label')}]\n"
            f"by {loop.get('author','')} — {loop.get('url','')}\n\n"
            f"USE WHEN: {loop.get('useWhen','')}\n\n"
            f"PROMPT:\n{loop.get('prompt','')}\n\n"
            f"VERIFY: {v.get('title','')} {('— ' + v.get('detail','')) if v.get('detail') else ''}\n\n"
            f"STEPS:\n{steps}\n"
            + (f"\nWHY: {loop.get('why','')}" if loop.get('why') else ""))


def seed_strategies(goal: str | None = None, n: int = 8, allow_fetch: bool = False) -> list[dict]:
    """Convert loops into discover.py strategy candidates — a HUMAN-VETTED seed gene pool for the
    evolutionary search (it can then select/recombine these, not just the 4 built-ins)."""
    pool = match(goal, n, allow_fetch) if goal else loops(allow_fetch)[:n]
    out = []
    for lp in pool:
        v = lp.get("verification", {})
        tmpl = (f"{lp.get('useWhen','')} APPROACH: {lp.get('prompt','')} "
                f"VERIFY: {v.get('title','')} {v.get('detail','')}").strip()
        if lp.get("slug") and len(tmpl) > 20:
            out.append({"name": f"loop-{lp['slug']}", "score": None, "template": tmpl[:MAX_TEMPLATE]})
    return out


def sync() -> str:
    cat = fetch_catalog(force=True)
    n = len(cat.get("loops", [])) if isinstance(cat, dict) else 0
    return (f"✓ synced Loop Library — {n} loops cached ({cat.get('updated','?')}) → {CACHE}"
            if n else "✗ could not fetch the Loop Library catalog (network?) — cache unchanged")


if __name__ == "__main__":
    import sys
    a = sys.argv[1:]
    if "--sync" in a:
        print(sync())
    elif a and a[0] == "get":
        print(render(get(a[1]) if len(a) > 1 else None))
    elif "--seed-discover" in a:
        from . import discover as D
        bank = D._load_bank()
        have = {s["name"] for s in bank["population"]}
        added = [s for s in seed_strategies(n=12, allow_fetch=True) if s["name"] not in have]
        bank["population"] += added
        D._save_bank(bank)
        print(f"✓ seeded {len(added)} Loop-Library strategies into the discovery population "
              f"({len(bank['population'])} total)")
    elif a:                                   # search query
        hits = match(" ".join(a), n=8, allow_fetch=True)
        if not hits:
            print("[no matching loops — run `verity looplib --sync` first]")
        for lp in hits:
            print(f"  [{lp.get('slug')}] {lp.get('title')} — {str(lp.get('useWhen',''))[:90]}")
    else:                                     # list all (cache; fetch if empty)
        ls = loops(allow_fetch=True)
        print(f"Loop Library — {len(ls)} loops cached. `verity looplib <query>` to search, "
              "`verity looplib get <slug>` for a full recipe, `--seed-discover` to add to the strategy bank.")
        for lp in ls[:50]:
            print(f"  {lp.get('number')} [{lp.get('category',{}).get('slug')}] {lp.get('slug')}: {lp.get('title')}")

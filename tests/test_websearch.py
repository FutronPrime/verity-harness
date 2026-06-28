#!/usr/bin/env python3
"""Tests for the multi-provider failover web search (offline — providers stubbed).
Verifies: first-that-answers failover, --all merge+dedupe, and graceful all-fail.

Run:  python3 tests/test_websearch.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verity import websearch as ws


def _row(u, s):
    return {"title": u, "url": u, "snippet": "", "source": s}


def test_failover_returns_first_that_answers():
    def dead(q, n): raise RuntimeError("down")
    def live(q, n): return [_row("http://a", "live")]
    ws.PROVIDERS[:] = [dead, dead, live]
    r = ws.search("x")
    assert r and r[0]["source"] == "live", r


def test_all_merges_and_dedupes():
    def p1(q, n): return [_row("http://a", "p1"), _row("http://b", "p1")]
    def p2(q, n): return [_row("http://a", "p2"), _row("http://c", "p2")]  # http://a dup
    ws.PROVIDERS[:] = [p1, p2]
    r = ws.search("x", all_providers=True)
    urls = [x["url"] for x in r]
    assert urls == ["http://a", "http://b", "http://c"], urls


def test_all_fail_returns_empty_not_crash():
    def dead(q, n): raise RuntimeError("down")
    ws.PROVIDERS[:] = [dead, dead]
    assert ws.search("x") == []
    assert ws.as_context("x") == ""


def test_github_added_for_repo_queries():
    seen = []
    def p(q, n): seen.append("base"); raise RuntimeError("down")
    def gh(q, n): seen.append("github"); return [_row("http://r", "github")]
    ws.PROVIDERS[:] = [p]
    ws._github = gh
    r = ws.search("best agentic search repo")   # 'repo' triggers github
    assert "github" in seen and r and r[0]["source"] == "github", (seen, r)


def _run():
    import importlib
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    p = 0
    for fn in fns:
        importlib.reload(ws)   # restore PROVIDERS between tests
        try: fn(); print(f"PASS  {fn.__name__}"); p += 1
        except AssertionError as e: print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{p}/{len(fns)} passed")
    return 0 if p == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())

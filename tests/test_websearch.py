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


def test_deep_research_iterates_then_stops_on_done():
    seq = iter([[_row("http://a", "p")], [_row("http://b", "p")]])
    ws.PROVIDERS[:] = [lambda q, n: next(seq, [])]
    asked = []
    def ask(p):
        asked.append(p)
        return "DONE"          # model says coverage sufficient after round 1
    d = ws.deep_research("goal", ask=ask, rounds=3)
    assert len(asked) == 1 and d["queries"] == ["goal"], d           # stopped early on DONE
    assert any(r["url"] == "http://a" for r in d["results"])


def test_deep_research_refines_query():
    calls = []
    def prov(q, n):
        calls.append(q)
        return [_row(f"http://{len(calls)}", "p")]
    ws.PROVIDERS[:] = [prov]
    d = ws.deep_research("first query", ask=lambda p: "second query", rounds=2)
    assert d["queries"] == ["first query", "second query"], d        # model's refined query was used


def test_six_source_scopes_each_site():
    seen_q = []
    ws.PROVIDERS[:] = [lambda q, n: (seen_q.append(q), [_row("http://x"+str(len(seen_q)), "ddg")])[1]]
    rows = ws.six_source("agent loop")
    assert any("site:github.com" in q for q in seen_q), seen_q
    assert any("site:reddit.com" in q for q in seen_q), seen_q
    assert rows and all(":" in r["source"] for r in rows)            # labeled by source


def test_should_search_classifier():
    assert ws.should_search("latest agentic search api 2026") is True
    assert ws.should_search("what is 2+2") is False
    assert ws.should_search("compare tavily vs perplexity") is True


def test_fetch_readability_extracts_main_content():
    orig = ws._get
    ws._get = lambda u, **k: ("<html><nav>menu nav links</nav><article>This is the real main "
                              "article body content that readability should extract cleanly and it "
                              "is well over the length threshold.</article><footer>boilerplate</footer></html>")
    try:
        t = ws.fetch("http://x")
        assert "real main article body" in t and "menu nav links" not in t and "boilerplate" not in t, t
    finally:
        ws._get = orig


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

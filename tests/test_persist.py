#!/usr/bin/env python3
"""Regression tests for the R60 persistence gate.

These encode the real 2026-06-28 lapse permanently (VERITY v2.1 TESTS-FROM-FAILURES):
the X-scraper "can't fix, wait for compact" conclusion MUST block on an empty
ledger, and PASS only once real multi-source research is logged.

Run:  python3 -m pytest tests/test_persist.py  (or)  python3 tests/test_persist.py
"""
import os
import sys
import tempfile
import pathlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verity import ledger, persist


def _fresh_ledger():
    d = tempfile.mkdtemp(prefix="verity-test-ledger-")
    ledger.LEDGER_DIR = pathlib.Path(d)
    return d


def test_no_quit_language_passes():
    _fresh_ledger()
    v = persist.check("Fixed it — SearchTimeline returns 200, 22 entries.")
    assert not v.blocked and v.verdict == "NO-QUIT", v


def test_human_gate_passes():
    _fresh_ledger()
    v = persist.check("I can't proceed — this step needs your password / 2FA.")
    assert not v.blocked and v.verdict == "HUMAN-GATE", v


def test_quit_on_empty_ledger_blocks():
    """The exact lapse: 'can't fix, wait for compact' with no research → BLOCK."""
    _fresh_ledger()
    v = persist.check("I couldn't fix the SearchTimeline 404 at this context — "
                      "let's wait for compact and try again.")
    assert v.blocked and v.verdict == "BLOCKED", v
    assert v.missing_sources, v
    assert "github" in v.missing_sources


def test_quit_after_real_research_passes():
    """Same conclusion, but the six-source sweep + alt-source read is logged → PASS."""
    _fresh_ledger()
    persist.note("github", "x-client-transaction-id SearchTimeline 404",
                 "twscrape xclid.XClIdGen has the real generator")
    persist.note("github", "twscrape #312 asset path", "X moved to abs.twimg.com/x-web/*.js")
    persist.note("google", "SearchTimeline 404 fix 2026", "gallery-dl #9275 confirms widespread")
    persist.note("x", "x-client-transaction-id removed?", "bb-browser #158 claim was outdated")
    v = persist.check("I couldn't fix it the first 7 ways — but here's the verified fix.",
                      min_sources=3, min_attempts=2)
    assert not v.blocked and v.verdict == "EARNED", v


def test_same_path_retried_does_not_count():
    """7 retries of ONE method with no find = still blocked (not 2 real attempts)."""
    _fresh_ledger()
    for _ in range(7):
        persist.note("github", "iSarabjitDhiman get_ondemand_file_url None", "")  # same path, no find
    v = persist.check("I can't — tried everything.", min_sources=3, min_attempts=2)
    assert v.blocked, v  # one distinct (source,query) + no find ⇒ fails attempts & found


def test_proactive_blocks_substantive_answer_without_research():
    """Forcing mode: a substantive conclusion with NO quit-language is still
    blocked if the model never researched — makes it go retrieve first."""
    _fresh_ledger()
    v = persist.check("The best way to scrape X is to roll your own urllib client.",
                      proactive=True)
    assert v.blocked and v.verdict == "BLOCKED", v


def test_proactive_allows_after_research():
    _fresh_ledger()
    persist.note("github", "x scraping maintained tool", "twscrape is the one")
    persist.note("google", "x scraping 2026", "confirms twscrape")
    persist.note("reddit", "x api alternatives", "twscrape recommended")
    v = persist.check("Use twscrape; it's the maintained tool.", proactive=True)
    assert not v.blocked and v.verdict == "EARNED", v


def test_proactive_exempts_trivial():
    _fresh_ledger()
    assert not persist.check("thanks!", proactive=True).blocked
    assert not persist.check("what's 2+2", proactive=True).blocked


def test_preflight_emits_retrieval_directive():
    d = persist.preflight("build a faster X bookmark scraper")
    assert "RETRIEVE" in d and "GitHub" in d and "note" in d, d


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    return 0 if passed == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())

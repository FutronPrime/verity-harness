#!/usr/bin/env python3
"""No-network test for the Loop Library bridge (looplib.py).

Points the cache at a synthetic catalog so the matching / hint / get / seed / render logic is tested
WITHOUT hitting the live endpoint (fresh clone + CI safe). The live sync is exercised separately."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verity import looplib as LL

_CATALOG = {
    "schemaVersion": "1", "updated": "2026-06-21", "loopCount": 2,
    "categories": [{"slug": "engineering", "label": "Engineering"}],
    "loops": [
        {"number": "001", "slug": "overnight-docs-sweep", "title": "The docs sweep",
         "url": "https://x/loops/docs", "category": {"slug": "engineering", "label": "Engineering"},
         "description": "compare documentation with code and fix drift",
         "useWhen": "Use when implementation changes may have left READMEs and docs behind.",
         "prompt": "Review the codebase and update stale documentation, then open a PR.",
         "verification": {"title": "Docs match implementation.", "detail": "Finish with a PR."},
         "steps": ["review changes", "compare docs", "update + verify"],
         "keywords": ["documentation", "docs", "readme", "drift"], "related": []},
        {"number": "002", "slug": "test-suite-speed-loop", "title": "The test-suite speed loop",
         "url": "https://x/loops/speed", "category": {"slug": "engineering", "label": "Engineering"},
         "description": "make slow tests fast",
         "useWhen": "Use when slow tests are delaying feedback or CI.",
         "prompt": "Profile the suite, parallelize and cache, keep behavior identical.",
         "verification": {"title": "Tests pass and run faster.", "detail": ""},
         "steps": ["profile", "optimize", "verify same results"],
         "keywords": ["test", "performance", "ci", "speed"], "related": []},
    ],
}


def _install_cache():
    tmp = tempfile.mkdtemp()
    LL.CACHE = __import__("pathlib").Path(tmp) / "loop-library.json"
    LL.CACHE.write_text(json.dumps(_CATALOG))


def test_match_by_keyword():
    _install_cache()
    hits = LL.match("fix the documentation drift in our readme", n=3)
    assert hits and hits[0]["slug"] == "overnight-docs-sweep", [h["slug"] for h in hits]
    print("✓ match ranks the docs loop top for a documentation goal")


def test_hint_is_bounded_and_cache_only():
    _install_cache()
    h = LL.hint("speed up our slow ci test suite", n=3)
    assert "test-suite-speed-loop" in h and "LOOP LIBRARY" in h
    assert "PROMPT" not in h, "hint must be a teaser (title+useWhen), not the full recipe (keeps plans lean)"
    print("✓ hint matches + stays bounded (slug + useWhen only)")


def test_get_and_render():
    _install_cache()
    lp = LL.get("test-suite-speed-loop")
    assert lp and lp["number"] == "002"
    r = LL.render(lp)
    assert "PROMPT:" in r and "VERIFY:" in r and "STEPS:" in r
    print("✓ get + render returns the full recipe (prompt/verify/steps)")


def test_seed_strategies_shape():
    _install_cache()
    seeds = LL.seed_strategies(goal="documentation", n=2)
    assert seeds and seeds[0]["name"].startswith("loop-")
    assert "score" in seeds[0] and seeds[0]["score"] is None      # matches discover.py candidate shape
    assert len(seeds[0]["template"]) <= LL.MAX_TEMPLATE
    print("✓ seed_strategies yields discover.py-shaped, size-bounded candidates")


def test_missing_cache_is_zero_cost():
    LL.CACHE = __import__("pathlib").Path(tempfile.mkdtemp()) / "absent.json"
    assert LL.hint("anything") == "" and LL.loops() == []          # no cache, no network → empty, never raises
    print("✓ absent cache → empty hint (offline-safe, zero-cost, no crash)")


if __name__ == "__main__":
    test_match_by_keyword()
    test_hint_is_bounded_and_cache_only()
    test_get_and_render()
    test_seed_strategies_shape()
    test_missing_cache_is_zero_cost()
    print("\nALL LOOP-LIBRARY TESTS PASSED ✅")

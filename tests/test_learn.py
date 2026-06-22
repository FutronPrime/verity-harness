#!/usr/bin/env python3
"""No-API test for the subject ACQUISITION loop (learn.py).

Stubs every external primitive (web/GitHub search, fetch, model, membank) so we test the LOOP's control
flow: scout → filter → assimilate → synthesize → PERSIST, the gap-driven multi-round iteration, and the
HONEST-failure path (no sources → learned=False, never a hallucinated answer)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verity import learn as L
from verity import tools as T
from verity import resources as R
from verity import router as RT
from verity import membank as MB


class _Reply:
    def __init__(self, text): self.text = text


def _install_stubs(scout_has_sources=True, gap_sequence=None):
    state = {"captured": [], "gap_calls": 0, "gaps": list(gap_sequence or ["COMPLETE"])}

    T.research = lambda q: ("Top repo: https://github.com/acme/widget and docs at "
                            "https://docs.acme.io/guide") if scout_has_sources else "NO real evidence found"
    T.search_github = lambda q, n=6: "github.com/acme/widget — a great library" if scout_has_sources else ""
    T.fetch = lambda url, max_chars=8000: "DETAILED DOC CONTENT about the subject " * 20
    R.fetch_list = lambda nm, max_chars=7000: "REPO README with real reusable techniques " * 20
    R.reuse_hint = lambda g, n=4: ""

    def fake_ask(prompt, system=None, **kw):
        s = (system or "") + " " + prompt
        if "Pick the SINGLE best sources" in (system or ""):
            return _Reply('{"sources":["https://github.com/acme/widget","https://docs.acme.io/guide"]}')
        if "You are LEARNING a subject" in (system or ""):
            return _Reply("Use acme.widget(); gotcha: call .init() first. [src]")
        if "Synthesize these source notes" in (system or ""):
            return _Reply("KNOWLEDGE NOTE: acme.widget is the go-to; init() then run(). Sources: acme/widget")
        if "What important sub-topic" in prompt:
            state["gap_calls"] += 1
            g = state["gaps"].pop(0) if state["gaps"] else "COMPLETE"
            return _Reply(g)
        return _Reply("ok")
    RT.ask = fake_ask
    MB.capture = lambda content, scope="fact", project=None: state["captured"].append((scope, project, content)) or "ok"
    MB.recall = lambda q, project=None, budget_chars=2000, k=30: "LEARNED SUBJECT · " + q if q == "known-subj" else "[membank empty]"
    return state


def test_happy_path_persists():
    st = _install_stubs(scout_has_sources=True)
    r = L.learn("rust async", rounds=1, verbose=False)
    assert r["learned"] is True, r
    assert r["persisted"] is True
    assert st["captured"], "must persist to membank"
    scope, project, content = st["captured"][-1]
    assert scope == "lesson" and project == "rust async", (scope, project)
    assert "LEARNED SUBJECT" in content and "Sources:" in content
    print("✓ happy path: scout→filter→assimilate→synthesize→PERSIST (scope=lesson, project=subject)")


def test_honest_failure_no_sources():
    _install_stubs(scout_has_sources=False)
    r = L.learn("an unsearchable nonsense subject", rounds=1, verbose=False)
    assert r["learned"] is False
    assert "honest" in r["msg"].lower() or "no learnable" in r["msg"].lower()
    print("✓ no sources → honest failure (learned=False), not a hallucinated answer")


def test_multi_round_gap_iteration():
    # round 1 gap returns a follow-up query, round 2 returns COMPLETE → critic drove a second scout
    st = _install_stubs(scout_has_sources=True, gap_sequence=["error handling patterns", "COMPLETE"])
    r = L.learn("rust async", rounds=3, verbose=False)
    assert r["learned"] is True
    assert st["gap_calls"] >= 1, "completeness critic must run between rounds"
    assert r["rounds"] >= 2, "gap query should have driven a second acquisition round"
    print(f"✓ agentic loop: completeness critic drove {r['rounds']} rounds, then stopped on COMPLETE")


def test_show_recall():
    _install_stubs()
    assert "LEARNED SUBJECT" in L.show("known-subj")
    assert "nothing learned yet" in L.show("never-seen-subj")
    print("✓ --show recalls per-user learned knowledge (or says nothing learned)")


if __name__ == "__main__":
    test_happy_path_persists()
    test_honest_failure_no_sources()
    test_multi_round_gap_iteration()
    test_show_recall()
    print("\nALL LEARN (ACQUISITION LOOP) TESTS PASSED ✅")

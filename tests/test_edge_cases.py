#!/usr/bin/env python3
"""Adversarial edge-case regression suite — the failure modes that break real self-evolving systems:
graph cycles, malformed LLM/JSON, corrupt caches, NULL DB columns, guard false-positives. No-API.

Born from the autonomous hardening pass (2026-06-22): these all PASS now; this file keeps them passing."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_complexity_extremes():
    from verity import complexity as C
    from verity.config import Tier
    assert C.band_for(-5) == "cheap" and C.band_for(1000) == "frontier"
    assert C.normalize_subtasks(None) == []
    assert C.normalize_subtasks([{"task": ""}, {"nope": 1}, "   "]) == []
    assert C.normalize_subtasks([{"task": "x", "depends_on": "3"}])[0]["depends_on"] == ["3"]
    one = [Tier(name="a", protocol="ollama", base_url="x", model="m", timeout_s=1)]
    assert C.tiers_for(9, base_tiers=one) == one
    os.environ["VERITY_COMPLEXITY_ROUTING"] = "1"
    try:
        assert C.tiers_for(2, base_tiers=one) == one      # cheap, no cloud → no crash
    finally:
        del os.environ["VERITY_COMPLEXITY_ROUTING"]
    print("✓ complexity: clamping, empty/garbage normalize, single-tier untouched")


def test_dag_cycle_no_deadlock():
    import verity.swarm as S, verity.scaffold as SC, verity.ledger as L, verity.membank as M
    import verity.coordinate as CO, verity.discover as D, verity.looplib as LL
    SC._preflight = lambda st, verbose=False: ''
    S._registry_hint = lambda t: ''
    L.log = lambda *a, **k: None
    M.capture = lambda *a, **k: None
    CO.learned_routing = lambda: ''
    D.active_strategy = lambda: ''
    LL.hint = lambda g, n=3: ''
    S._local_primary = lambda tiers: True

    def agent(role, prompt, tiers=None, **kw):
        if role == 'planner':   # cycle 1→2, 2→1, plus dangling dep '99'
            return ('{"subtasks":[{"id":"1","task":"a","complexity":3,"depends_on":["2"]},'
                    '{"id":"2","task":"b","complexity":3,"depends_on":["1","99"]}]}')
        if role == 'critic':
            return '{"ok":true}'
        return 'r' if role != 'synthesizer' else 'FINAL'
    S._agent = agent
    r = S.run_swarm("cycle", verbose=False)
    assert r.final == 'FINAL' and len(r.results) == 2     # ran both despite the cycle, no hang
    print("✓ DAG: cycle + dangling dep complete without deadlock")


def test_looplib_corrupt_and_malformed():
    from verity import looplib as LL
    tmp = tempfile.mkdtemp(); LL.CACHE = pathlib.Path(tmp) / "c.json"
    LL.CACHE.write_text("{ not json ")
    assert LL.loops() == [] and LL.hint("x") == ""
    LL.CACHE.write_text(json.dumps({"loops": [{"slug": "a"}, {"no_slug": 1}]}))
    LL.match("anything"); assert LL.seed_strategies(n=2) is not None
    print("✓ looplib: corrupt cache + loops missing keys → graceful")


def test_coordinate_malformed_events():
    from verity import coordinate as CO
    bad = [{"gate": "swarm-synth"}, {"gate": "swarm-plan", "trigger": None}, {"nope": 1},
           {"gate": "swarm-synth", "trigger": "g", "evidence": "no number here"}]
    CO.distill_routing(events=bad)
    assert CO.distill_routing(events=[]) == ""
    print("✓ coordinate: malformed/empty ledger events → no crash")


def test_membank_prune_null_columns():
    from verity import membank as MB
    tmp = tempfile.mkdtemp(); MB.DB = os.path.join(tmp, "m.db")
    c = MB._conn()
    c.execute("INSERT INTO memories(project,scope,content,entities,hash,created_at,accessed_at) "
              "VALUES('p','fact','x','','h1',NULL,NULL)")
    c.commit(); c.close()
    MB.prune(max_rows=0)        # must handle NULL created_at/access_count
    print("✓ membank: prune handles NULL created_at/access_count (legacy rows)")


def test_guard_no_false_positives():
    from verity import guard as G
    assert G.flag("Only you can tell me your password.") == "defer"   # defer, not capability
    assert G.flag("The training data shows X.") is None               # 'training' alone is fine
    assert G.flag("We can do this without much effort.") is None      # 'without' alone is fine
    assert G.flag("Only weights can do this.") == "capability"        # the real lapse IS caught
    print("✓ guard: benign 'training'/'without' pass; real capability-negative caught")


if __name__ == "__main__":
    test_complexity_extremes()
    test_dag_cycle_no_deadlock()
    test_looplib_corrupt_and_malformed()
    test_coordinate_malformed_events()
    test_membank_prune_null_columns()
    test_guard_no_false_positives()
    print("\nALL EDGE-CASE REGRESSION TESTS PASSED ✅")

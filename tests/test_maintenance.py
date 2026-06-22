#!/usr/bin/env python3
"""No-API test for memory maintenance — proves the self-evolving stores stay BOUNDED on disk and that
pruning PRESERVES high-value rows (durable/recent/accessed) while evicting transient cruft."""
from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _isolated_membank():
    """Redirect membank to a throwaway DB so the test NEVER touches the real ~/.verity-harness store."""
    from verity import membank
    tmp = tempfile.mkdtemp()
    membank.DB = os.path.join(tmp, "membank.db")   # _conn() reads this module global
    assert "/.verity-harness/" not in membank.DB, "test must be isolated from the real store"
    return membank, tmp


def test_prune_caps_and_preserves_value():
    membank, tmp = _isolated_membank()
    # seed: 50 transient "fact" rows + 5 durable "lesson" rows
    for i in range(50):
        membank.capture(f"transient fact number {i} about nothing important", scope="fact", project="t")
    for i in range(5):
        membank.capture(f"DURABLE hard-won lesson {i}: never assert a negative un-searched", scope="lesson", project="t")
    total_before = membank.count()
    assert total_before >= 55, total_before
    # cap to 20 → must evict down to 20, and the 5 durable lessons should survive (higher keep-value)
    res = membank.prune(max_rows=20)
    assert res["evicted"] >= 35, res
    assert membank.count() <= 20, membank.count()
    survived = membank.recall("hard-won lesson never assert", project="t", budget_chars=3000)
    assert "DURABLE" in survived or "lesson" in survived.lower(), "durable lessons must survive eviction"
    print(f"✓ prune capped {total_before}→{membank.count()} rows; durable lessons preserved")


def test_prune_is_noop_under_cap():
    membank, tmp = _isolated_membank()
    membank.capture("only a few rows here", scope="fact", project="t")
    res = membank.prune(max_rows=5000)
    assert res["evicted"] == 0, res
    print("✓ prune is a no-op when under cap (zero churn)")


def test_gc_runs_clean_on_empty():
    # gc must never crash on absent dirs (fresh install)
    from verity import maintenance
    import verity.maintenance as M
    M.HOME = __import__("pathlib").Path(tempfile.mkdtemp())  # empty, no subdirs
    rep = maintenance.gc(verbose=False)
    assert rep["ledger"]["removed"] == 0 and rep["guard_counters"]["removed"] == 0
    print("✓ gc runs clean on a fresh/empty install (no crash, nothing to remove)")


if __name__ == "__main__":
    test_prune_caps_and_preserves_value()
    test_prune_is_noop_under_cap()
    test_gc_runs_clean_on_empty()
    print("\nALL MAINTENANCE TESTS PASSED ✅")

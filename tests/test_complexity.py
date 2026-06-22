#!/usr/bin/env python3
"""Deterministic, no-API tests for the complexity router (Fugu parity delta #1).

Run: python3 -m tests.test_complexity   (from repo root)  — or  python3 tests/test_complexity.py
Asserts the two non-negotiables: (1) OFF by default → base chain unchanged (zero regression),
(2) failover is always preserved (the full base chain survives beneath any band entry)."""
from __future__ import annotations

import os
import sys

# allow running as a loose script from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import replace
from verity import complexity as C
from verity.config import Tier


def _mk_tiers():
    return [
        Tier(name="tier1-1", protocol="openai", base_url="https://x/v1",
             model="frontier/x", timeout_s=90, api_key="k"),
        Tier(name="tier0-local", protocol="ollama", base_url="http://127.0.0.1:11434",
             model="llama3.2", timeout_s=120),
    ]


def _clear_env():
    for k in list(os.environ):
        if k.startswith("VERITY_TIER_") or k == "VERITY_COMPLEXITY_ROUTING":
            del os.environ[k]


def test_band_for():
    assert C.band_for(1) == "cheap" and C.band_for(3) == "cheap"
    assert C.band_for(4) == "mid" and C.band_for(7) == "mid"
    assert C.band_for(8) == "frontier" and C.band_for(10) == "frontier"
    assert C.band_for(0) == "cheap" and C.band_for(99) == "frontier"  # clamped, no raise
    print("✓ band_for thresholds + clamping")


def test_heuristic_score():
    assert C.heuristic_score("format this json string") <= 3
    assert C.heuristic_score("architect a distributed auth system") >= 8
    assert 4 <= C.heuristic_score("write a helper that parses the file") <= 7
    print("✓ heuristic_score easy/hard/mid")


def test_normalize_mixed():
    nodes = C.normalize_subtasks([
        "plain string task",
        {"task": "rich task", "complexity": 9, "type": "code", "depends_on": [1]},
        {"subtask": "alt-key task", "complexity": "bad"},  # garbage score → heuristic
    ])
    assert len(nodes) == 3
    assert nodes[0]["complexity"] >= 1 and nodes[0]["depends_on"] == []
    assert nodes[1]["task"] == "rich task" and nodes[1]["complexity"] == 9
    assert nodes[1]["type"] == "code" and nodes[1]["depends_on"] == ["1"]
    assert isinstance(nodes[2]["complexity"], int)  # salvaged, not crashed
    print("✓ normalize_subtasks handles strings + dicts + garbage")


def test_off_by_default_is_identity():
    _clear_env()  # routing OFF
    base = _mk_tiers()
    for score in (1, 5, 9):
        assert C.tiers_for(score, base_tiers=base) == base, "OFF must be byte-identical to base"
    print("✓ OFF by default → base chain unchanged (zero regression)")


def test_failover_preserved_with_band_model():
    _clear_env()
    os.environ["VERITY_COMPLEXITY_ROUTING"] = "1"
    os.environ["VERITY_TIER_FRONTIER_MODEL"] = "anthropic/opus-4.8"
    base = _mk_tiers()
    out = C.tiers_for(9, base_tiers=base)
    assert out[0].model == "anthropic/opus-4.8", "frontier band must ENTER at its model"
    assert out[0].api_key == "k", "band entry reuses the configured endpoint/key"
    # the FULL base chain must survive beneath (failover preserved), incl. the sovereign floor
    assert any(t.protocol == "ollama" for t in out), "local floor must remain as failover"
    assert len(out) >= len(base), "band entry is ADDED, base chain not dropped"
    print("✓ band model ENTERS first, full base chain preserved beneath (failover safe)")


def test_cheap_band_prefers_local_when_no_model():
    _clear_env()
    os.environ["VERITY_COMPLEXITY_ROUTING"] = "1"  # no band models set
    base = _mk_tiers()
    out = C.tiers_for(2, base_tiers=base)  # cheap
    assert out[0].protocol == "ollama", "cheap band with no model → local floor first (free)"
    assert any(t.protocol == "openai" for t in out), "cloud kept as failover beneath local"
    print("✓ cheap band (no model) → local-first, cloud preserved as failover")


def test_single_tier_is_untouched():
    _clear_env()
    os.environ["VERITY_COMPLEXITY_ROUTING"] = "1"
    one = [_mk_tiers()[1]]  # local-only
    assert C.tiers_for(9, base_tiers=one) == one, "nothing to right-size on a 1-tier setup"
    print("✓ single-tier / local-only setup untouched")


if __name__ == "__main__":
    test_band_for()
    test_heuristic_score()
    test_normalize_mixed()
    test_off_by_default_is_identity()
    test_failover_preserved_with_band_model()
    test_cheap_band_prefers_local_when_no_model()
    test_single_tier_is_untouched()
    _clear_env()
    print("\nALL COMPLEXITY ROUTER TESTS PASSED ✅")

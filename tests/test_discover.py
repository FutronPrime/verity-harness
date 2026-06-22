#!/usr/bin/env python3
"""No-API test for strategy DISCOVERY (Gap #4 'discover' half).

Proves the core ADAS/AlphaEvolve claim mechanically: a frozen-model proposer + a real evaluator + a
selection loop DISCOVERS a better strategy WITHOUT weight training — and adopts it ONLY on MEASURED
fitness, never the model's say-so. Proposer + evaluator are stubbed so we test the SEARCH LOOP itself."""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verity import discover as D


def _isolate_bank():
    """Point the bank + archive at a temp dir so the test never touches a real ~/.verity-harness."""
    tmp = tempfile.mkdtemp()
    D.BANK = __import__("pathlib").Path(tmp) / "strategies.json"
    D.ARCHIVE = __import__("pathlib").Path(tmp) / "discover"


def test_seed_population_and_no_champion():
    _isolate_bank()
    bank = D._load_bank()
    assert len(bank["population"]) == len(D.SEED_STRATEGIES)
    assert bank["champion"] is None
    assert D.active_strategy() == ""          # nothing discovered yet → zero-cost empty injection
    print("✓ seeds load; no champion until something is measured")


def test_discovery_selects_by_measured_fitness():
    _isolate_bank()
    # proposer: a NEW candidate the seeds don't have
    def proposer(bank, tiers=None):
        return {"name": "research-then-debate", "score": None,
                "template": "stage a research node, then 2 debaters depending on it, then an adjudicator"}
    # evaluator: the NEW strategy measurably wins; selection must pick it on the NUMBER, not vibes
    scores = {"research-then-debate": 0.9, "flat-fanout": 0.4, "review-revise": 0.5,
              "debate-adjudicate": 0.6, "isolate-recurse": 0.5}
    def evaluator(template, tiers=None):
        for name, sc in scores.items():
            if name in template or template in name:
                return sc
        # match by the template text we set on the candidate
        return 0.7 if "adjudicator" in template and "research node" in template else 0.3

    r = D.discover(propose=True, use_eval=True, apply=True, proposer=proposer, evaluator=evaluator)
    assert r["proposed"] == "research-then-debate"
    assert r["promoted"] is True, "a measured winner must be promoted"
    assert r["new_champion"] == "research-then-debate"
    # the champion is now injectable into the orchestrator
    inj = D.active_strategy()
    assert "research-then-debate" in inj and "DISCOVERED STRATEGY" in inj
    print("✓ loop DISCOVERS + promotes the measured-best strategy (frozen model, no weights)")


def test_no_promotion_without_improvement():
    _isolate_bank()
    # pre-seed a strong champion, then offer only weaker candidates
    bank = D._load_bank()
    bank["champion"] = {"name": "flat-fanout", "score": 0.95, "template": "x"}
    D._save_bank(bank)
    def proposer(bank, tiers=None):
        return {"name": "weak-new", "score": None, "template": "a clearly worse coordination idea here"}
    def evaluator(template, tiers=None):
        return 0.2   # everything new is worse than the 0.95 champion
    r = D.discover(propose=True, use_eval=True, apply=True, proposer=proposer, evaluator=evaluator)
    assert r["promoted"] is False, "must NOT overwrite a better champion with a worse candidate"
    assert D._load_bank()["champion"]["name"] == "flat-fanout"
    print("✓ champion is NOT overwritten unless a candidate MEASURES better (gated, no regression)")


def test_propose_only_does_not_promote():
    _isolate_bank()
    def proposer(bank, tiers=None):
        return {"name": "p1", "score": None, "template": "some new strategy directive that is long enough"}
    r = D.discover(propose=True, use_eval=False, apply=False, proposer=proposer)
    assert r["proposed"] == "p1" and r["promoted"] is False
    assert D._load_bank()["champion"] is None    # proposing ≠ discovering; no eval → no champion
    print("✓ propose-without-eval adds to population but never crowns a champion (honest: no measure = no discovery)")


if __name__ == "__main__":
    test_seed_population_and_no_champion()
    test_discovery_selects_by_measured_fitness()
    test_no_promotion_without_improvement()
    test_propose_only_does_not_promote()
    print("\nALL DISCOVERY TESTS PASSED ✅")

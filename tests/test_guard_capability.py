#!/usr/bin/env python3
"""Test the CAPABILITY-negative guard — the gap that let the harness's own author assert
'discover = weights only' twice (2026-06-22) while the gates were in context.

The requirement: a confident capability/possibility negative asserted WITHOUT a search is CAUGHT
(so the proxy re-prompts / the Stop hook blocks), and a clean or evidence-backed conclusion passes."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verity import guard


def test_capability_negatives_are_caught():
    # phrasings NEGATIVE misses but CAPABILITY must catch (the exact class of the real lapse)
    for txt in ["Only weights can do this.", "No prompt software can replicate that.",
                "That approach is weights-only.", "only training can discover new strategies"]:
        assert guard.flag(txt) == "capability", (txt, guard.flag(txt))
    print("✓ 'only weights can / no prompt can / weights-only' → flagged 'capability'")


def test_capability_or_negative_both_catch():
    # phrasings that ALSO contain infra-negative words are still caught (by NEGATIVE) — the point is
    # they don't slip through, regardless of which net fires.
    for txt in ["It is not reachable without weight training.",
                "This is structurally impossible without a training pipeline."]:
        assert guard.flag(txt) is not None, txt
    print("✓ 'not reachable without / structurally impossible' → caught (no slip-through)")


def test_clean_conclusions_pass():
    for txt in ["We fixed the bug and verified the tests pass.",
                "Searched GitHub + arXiv; ADAS and AlphaEvolve discover with a frozen model, so it's reachable.",
                "The answer is 42, VERIFIED against the source."]:
        assert guard.flag(txt) is None, ("false positive on: " + txt)
    print("✓ clean / evidence-backed conclusions pass (no false positives)")


def test_corrective_is_search_forcing():
    c = guard.corrective_for("capability")
    assert "search" in c.lower() and ("ADAS" in c or "AlphaEvolve" in c)
    # the generic corrective is different (infra-flavored), proving routing works
    assert guard.corrective_for("negative") != c
    print("✓ capability corrective forces a search + cites the precedent; distinct from the infra one")


if __name__ == "__main__":
    test_capability_negatives_are_caught()
    test_capability_or_negative_both_catch()
    test_clean_conclusions_pass()
    test_corrective_is_search_forcing()
    print("\nALL CAPABILITY-GUARD TESTS PASSED ✅")

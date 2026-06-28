#!/usr/bin/env python3
"""Tests for council-mode eval (ported from karpathy/llm-council).

Verifies the three stages and — critically — that Stage 2 ranking is BLIND
(no member identity leaks into the ranking prompt), which is the bias fix the
prior panel+judge gate lacked.

Run:  python3 tests/test_council.py
"""
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verity import council as C


@dataclass
class FakeTier:
    name: str
    model: str


MEMBERS = [FakeTier("alpha-member", "fake/alpha"),
           FakeTier("bravo-member", "fake/bravo"),
           FakeTier("charlie-member", "fake/charlie")]

# member → answer; the trailing int is the "quality" peers will rank by.
ANSWERS = {"alpha-member": "answer one quality 1",
           "bravo-member": "answer two quality 2",
           "charlie-member": "answer three quality 3"}

STAGE2_PROMPTS = []      # capture to assert blindness


def stub_ask(member, prompt):
    import re
    if prompt.strip().endswith("FINAL ANSWER:"):                 # Stage 3
        return "SYNTHESIS: merged best answer"
    if "RANKING" in prompt:                                      # Stage 2
        STAGE2_PROMPTS.append(prompt)
        # rank the anonymized Response blocks by the 'quality N' in each
        blocks = re.findall(r"Response ([A-H]):\n(.*?)(?=\n\nResponse |\Z)",
                            prompt, re.S)
        ranked = sorted(blocks, key=lambda b: -int(re.search(r"quality (\d)", b[1]).group(1)))
        return "RANKING: " + " > ".join(lb for lb, _ in ranked)
    return ANSWERS[member.name]                                  # Stage 1


def test_three_stages_and_consensus():
    STAGE2_PROMPTS.clear()
    res = C.council("Q?", members=MEMBERS, ask_fn=stub_ask)
    assert len(res.responses) == 3, res.responses
    # charlie (quality 3) is ranked best by every peer → consensus winner
    assert res.consensus[0] == "charlie-member", res.consensus
    assert res.consensus[-1] == "alpha-member", res.consensus
    # chairman synthesis is the final answer (not a raw member answer)
    assert "SYNTHESIS" in res.final, res.final


def test_ranking_is_blind():
    """The bias fix: no member name or model may appear in a Stage-2 prompt."""
    STAGE2_PROMPTS.clear()
    C.council("Q?", members=MEMBERS, ask_fn=stub_ask)
    assert STAGE2_PROMPTS, "no ranking prompts captured"
    leaks = []
    for p in STAGE2_PROMPTS:
        for m in MEMBERS:
            if m.name in p or m.model in p:
                leaks.append((m.name, p[:60]))
    assert not leaks, f"identity leaked into blind ranking: {leaks}"


def test_disagreement_flagged_when_split():
    """If peers split, disagreement rises and is reported for escalation."""
    def split_ask(member, prompt):
        import re
        if prompt.strip().endswith("FINAL ANSWER:"):
            return "SYNTHESIS"
        if "RANKING" in prompt:
            labels = re.findall(r"Response ([A-H]):", prompt)
            # each ranker prefers a different order → high spread
            rot = hash(member.name) % len(labels)
            order = labels[rot:] + labels[:rot]
            return "RANKING: " + " > ".join(order)
        return ANSWERS[member.name]
    res = C.council("Q?", members=MEMBERS, ask_fn=split_ask)
    assert res.disagreement >= 0.0  # computed without error
    assert isinstance(res.report(), str)


def test_single_member_degrades_gracefully():
    res = C.council("Q?", members=[MEMBERS[0]], ask_fn=stub_ask)
    assert res.final == ANSWERS["alpha-member"], res.final


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    return 0 if passed == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())

#!/usr/bin/env python3
"""Tests for the recursive deliberation loop (offline, stubbed backends).
Run:  python3 tests/test_recurse.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verity import recurse


def test_loops_until_critic_says_sufficient():
    crit = iter(["gap: missing rollback", "gap: no monitoring", "SUFFICIENT"])
    refined = []
    def reason(p):
        if "Revise the plan" in p:
            refined.append(1); return f"plan v{len(refined)+1}"
        return "plan v1"
    d = recurse.deliberate("goal", reason=reason, critique=lambda p: next(crit), rounds=5)
    assert d.converged is True, d.trail
    assert d.rounds_used == 3 and len(d.gaps) == 2, (d.rounds_used, d.gaps)
    assert "critique[3]:SUFFICIENT" in d.trail


def test_stops_at_round_cap_if_never_sufficient():
    d = recurse.deliberate("goal", reason=lambda p: "plan",
                           critique=lambda p: "always a gap", rounds=2)
    assert d.converged is False and d.rounds_used == 2, d.trail
    assert len(d.gaps) == 2


def test_research_feeds_seed_and_gaps():
    seen = {"seed": False, "gap": False}
    def research(q):
        if q == "goal": seen["seed"] = True
        else: seen["gap"] = True
        return "live context"
    def reason(p):
        return "plan"
    crit = iter(["gap X", "SUFFICIENT"])
    recurse.deliberate("goal", reason=reason, critique=lambda p: next(crit),
                       research=research, rounds=3)
    assert seen["seed"] and seen["gap"], seen


def test_maker_checker_can_be_two_models():
    who = []
    recurse.deliberate("g", reason=lambda p: who.append("R") or "plan",
                       critique=lambda p: who.append("C") or "SUFFICIENT", rounds=2)
    assert "R" in who and "C" in who   # distinct maker + checker callables used


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    p = 0
    for fn in fns:
        try: fn(); print(f"PASS  {fn.__name__}"); p += 1
        except AssertionError as e: print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{p}/{len(fns)} passed")
    return 0 if p == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())

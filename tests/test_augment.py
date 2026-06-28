#!/usr/bin/env python3
"""Tests for `verity augment` — weak-model-as-conductor orchestration (offline, stubbed
backends). Verifies the conduct→escalate→synthesize flow and that the reasoner does the
heavy lifting while the driver orchestrates.

Run:  python3 tests/test_augment.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verity import augment


def test_full_orchestration_flow():
    calls = []
    def driver(p):
        calls.append("driver")
        return "FRAMING: hard Qs" if "CONDUCTOR" in p else "FINAL: organized plan"
    def reasoner(p):
        calls.append("reasoner")
        assert "hard Qs" in p          # the driver's framing is passed to the reasoner
        return "DEEP: strangler-fig + outbox plan"
    p = augment.augment_plan("migrate monolith", driver=driver, reasoner=reasoner)
    assert p.framing.startswith("FRAMING")
    assert p.reasoning.startswith("DEEP")
    assert p.final.startswith("FINAL")
    assert p.trail == ["driver:framed", "reasoner:planned", "driver:synthesized"], p.trail
    assert calls == ["driver", "reasoner", "driver"]   # conduct → escalate → synthesize


def test_research_step_included_when_provided():
    seen = {}
    def reasoner(p):
        seen["got_context"] = "CURRENT CONTEXT" in p
        return "plan"
    augment.augment_plan("x", driver=lambda p: "f",
                         reasoner=reasoner, search=lambda q: "live facts about x")
    assert seen["got_context"] is True


def test_graceful_when_synth_fails():
    def driver(p):
        if "EXPERT PLAN:" in p:           # only the SYNTH prompt carries the expert's plan
            raise RuntimeError("driver down")
        return "framing"
    p = augment.augment_plan("x", driver=driver, reasoner=lambda p: "EXPERT PLAN")
    assert p.final == "EXPERT PLAN"     # ships the reasoner's plan if synthesis fails
    assert "driver:synth-failed→raw" in p.trail


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

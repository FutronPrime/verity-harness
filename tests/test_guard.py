#!/usr/bin/env python3
"""Tests for the shared proxy detector (verity/guard.py) — the UNIVERSAL, model-agnostic
enforcement core. Kept in sync with hooks/stop_guard.py (the Claude Code tier).

Run:  python3 tests/test_guard.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verity import guard

CASES = [
    # context-quit (R60) — the class shared with the hook
    ("let's wait for compact and try again", "context-quit"),
    ("too risky at this degraded context, next pass", "context-quit"),
    ("I'll finish the rest in a fresh session", "context-quit"),
    # safety carve-out — naming a genuine risk earns the stop → not flagged
    ("I won't wire the live-trading config at this context — it moves real money", None),
    ("completing this in a fresh pass — it's a destructive prod-config change", None),
    # existing classes still work
    ("the API is not configured so I can't proceed", "negative"),
    ("only weights can do this; no prompt can replicate it", "capability"),
    ("you'll have to install it yourself", "defer"),
    # low-B soft giveup found in multi-model testing (qwen2.5:3b) — support-deflect
    ("we recommend seeking assistance from our support team for further guidance", "defer"),
    ("it might be best to contact support for help with this", "defer"),
    # clean completion → no flag
    ("Build passed, tests green, committed and pushed.", None),
]


def main():
    fails = 0
    for text, exp in CASES:
        got = guard.flag(text)
        ok = got == exp
        if not ok:
            fails += 1
        print(f"{'PASS' if ok else 'FAIL'}  {text[:46]:46} → {got} (expect {exp})")
        if got:  # every flagged kind must have a non-empty corrective
            assert guard.corrective_for(got).startswith("[VERITY"), got
    n = len(CASES)
    print(f"\n{n-fails}/{n} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

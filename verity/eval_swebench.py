#!/usr/bin/env python3
"""SWE-Bench-style coding benchmark — test-scored bug fixing, self-contained.

This is the CODING axis the frontier models are ranked on (Fable 5 = 80.3% SWE-Bench Pro / 95.0%
Verified). SWE-Bench's method: give the agent a buggy repo + failing tests, it patches the code,
score = do the tests pass. This is a miniature, zero-dependency version — each task is a buggy
function + a hidden test that fails on the bug and passes only when it's correctly fixed.

Where the harness should help vs a naive one-shot: the bugs all have an EDGE CASE the obvious fix
misses. A naive loop writes a plausible patch and declares done; the harness must RUN the test
(verify gate) and is forced to keep fixing until it actually passes. That's the SWE-Bench skill.

  NAIVE   = model outputs a corrected file in one shot; we write it and run the test.
  HARNESS = run_verified(real shell): edit → RUN TEST → verify → fix, until the test passes.
Score = % of tasks whose hidden test passes. Run: python3 -m verity swebench [--exec]
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile

# Each: a buggy module + a hidden test. The bug passes a shallow check but fails the edge case.
TASKS = [
    {"name": "median",
     "buggy": ("def median(xs):\n"
               "    s = sorted(xs)\n"
               "    return s[len(s) // 2]   # BUG: wrong for even-length lists\n"),
     "test": ("from sol import median\n"
              "assert median([3,1,2]) == 2\n"
              "assert median([1,2,3,4]) == 2.5, 'even-length case'\n"
              "assert median([4,1]) == 2.5\n"
              "print('PASS')\n")},
    {"name": "running_total",
     "buggy": ("def add(x, acc=[]):   # BUG: mutable default shared across calls\n"
               "    acc.append(x)\n"
               "    return list(acc)\n"),
     "test": ("from sol import add\n"
              "assert add(1) == [1]\n"
              "assert add(2) == [2], 'state must not leak between calls'\n"
              "print('PASS')\n")},
    {"name": "first_unique",
     "buggy": ("def first_unique(s):\n"
               "    for c in s:\n"
               "        if s.count(c) == 1:\n"
               "            return c\n"
               "    return s[0]   # BUG: empty string / all-dup should return None\n"),
     "test": ("from sol import first_unique\n"
              "assert first_unique('leetcode') == 'l'\n"
              "assert first_unique('aabb') is None, 'all-duplicate case'\n"
              "assert first_unique('') is None, 'empty case'\n"
              "print('PASS')\n")},
]


def _run_test(d: str) -> bool:
    """True iff the hidden test passes in dir d."""
    try:
        r = subprocess.run(["python3", "test.py"], cwd=d, capture_output=True, text=True, timeout=20)
        return r.returncode == 0 and "PASS" in r.stdout
    except Exception:  # noqa: BLE001
        return False


def _extract_code(text: str) -> str | None:
    m = re.search(r"```(?:python)?\s*(.*?)```", text or "", re.S)
    if m:
        return m.group(1).strip()
    return text.strip() if "def " in (text or "") else None


def run(tiers=None, harness_exec=True, verbose=True) -> dict:
    from .router import ask
    from .scaffold import run_verified
    from .loop import ShellExecutor

    naive_pass = harness_pass = 0
    for t in TASKS:
        kw = {"tiers": tiers} if tiers else {}
        # ---- NAIVE: one-shot patch ----
        with tempfile.TemporaryDirectory() as d:
            open(f"{d}/sol.py", "w").write(t["buggy"])
            open(f"{d}/test.py", "w").write(t["test"])
            try:
                resp = ask(f"This file `sol.py` has a bug:\n```python\n{t['buggy']}```\n"
                           "Output ONLY the corrected full contents of sol.py in one ```python block.", **kw)
                code = _extract_code(resp.text if hasattr(resp, "text") else str(resp))
                if code:
                    open(f"{d}/sol.py", "w").write(code)
                npass = _run_test(d)
            except Exception:  # noqa: BLE001
                npass = False
        # ---- HARNESS: agentic edit → RUN TEST → verify → fix ----
        with tempfile.TemporaryDirectory() as d:
            open(f"{d}/sol.py", "w").write(t["buggy"])
            open(f"{d}/test.py", "w").write(t["test"])
            try:
                if harness_exec:
                    cwd0 = os.getcwd(); os.chdir(d)
                    try:
                        run_verified(
                            f"Fix the bug in sol.py so that `python3 test.py` prints PASS and exits 0. "
                            f"You MUST run the test to verify before finishing.",
                            executor=ShellExecutor(), max_steps=6, verbose=False, tiers=tiers)
                    finally:
                        os.chdir(cwd0)
                hpass = _run_test(d)
            except Exception:  # noqa: BLE001
                hpass = False
        naive_pass += npass; harness_pass += hpass
        if verbose:
            print(f"  naive={'✓' if npass else '✗'}  harness={'✓' if hpass else '✗'}  {t['name']}")

    n = len(TASKS)
    res = {"tasks": n, "naive": naive_pass, "harness": harness_pass, "lift": harness_pass - naive_pass}
    if verbose:
        print(f"\nNAIVE   tests passed: {naive_pass}/{n} ({naive_pass/n:.0%})")
        print(f"HARNESS tests passed: {harness_pass}/{n} ({harness_pass/n:.0%})")
        print(f"LIFT (SWE-Bench-style, test-scored): +{res['lift']}")
    return res


if __name__ == "__main__":
    import sys
    run(harness_exec="--exec" in sys.argv or True)

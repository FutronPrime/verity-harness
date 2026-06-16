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
               "    return s[len(s) // 2]\n"),
     "test": ("from sol import median\n"
              "assert median([3,1,2]) == 2\n"
              "assert median([1,2,3,4]) == 2.5, 'even-length case'\n"
              "assert median([4,1]) == 2.5\n"
              "print('PASS')\n")},
    {"name": "running_total",
     "buggy": ("def add(x, acc=[]):\n"
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
               "    return s[0]\n"),
     "test": ("from sol import first_unique\n"
              "assert first_unique('leetcode') == 'l'\n"
              "assert first_unique('aabb') is None, 'all-duplicate case'\n"
              "assert first_unique('') is None, 'empty case'\n"
              "print('PASS')\n")},
    {"name": "merge_intervals",
     "buggy": ("def merge(intervals):\n"
               "    out = []\n"
               "    for s, e in intervals:\n"
               "        if out and s <= out[-1][1]:\n"
               "            out[-1][1] = max(out[-1][1], e)\n"
               "        else:\n"
               "            out.append([s, e])\n"
               "    return out\n"),
     "test": ("from sol import merge\n"
              "assert merge([[1,3],[2,6],[8,10]]) == [[1,6],[8,10]]\n"
              "assert merge([[8,10],[1,3],[2,6]]) == [[1,6],[8,10]], 'unsorted input'\n"
              "assert merge([[1,4],[4,5]]) == [[1,5]], 'touching intervals'\n"
              "assert merge([]) == []\n"
              "print('PASS')\n")},
    {"name": "roman",
     "buggy": ("def to_roman(n):\n"
               "    vals = [(1000,'M'),(500,'D'),(100,'C'),(50,'L'),(10,'X'),(5,'V'),(1,'I')]\n"
               "    out = ''\n"
               "    for v, sym in vals:\n"
               "        while n >= v:\n"
               "            out += sym; n -= v\n"
               "    return out\n"),
     "test": ("from sol import to_roman\n"
              "assert to_roman(3) == 'III'\n"
              "assert to_roman(4) == 'IV', 'subtractive 4'\n"
              "assert to_roman(9) == 'IX', 'subtractive 9'\n"
              "assert to_roman(58) == 'LVIII'\n"
              "assert to_roman(1994) == 'MCMXCIV', 'full subtractive'\n"
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
    rows = []
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
                    # Run the agent's shell IN the task dir via the executor's cwd — no global
                    # os.chdir (that was fragile + not thread-safe). sol.py/test.py are right there.
                    run_verified(
                        "The files sol.py (buggy) and test.py are in your current directory. "
                        "Fix the bug in sol.py so that `python3 test.py` prints PASS and exits 0. "
                        "You MUST run `python3 test.py` yourself to verify before finishing.",
                        executor=ShellExecutor(cwd=d), max_steps=6, verbose=False, tiers=tiers)
                hpass = _run_test(d)
            except Exception:  # noqa: BLE001
                hpass = False
        naive_pass += npass; harness_pass += hpass
        rows.append([t["name"], bool(npass), bool(hpass)])
        if verbose:
            print(f"  naive={'✓' if npass else '✗'}  harness={'✓' if hpass else '✗'}  {t['name']}")

    n = len(TASKS)
    res = {"tasks": n, "naive": naive_pass, "harness": harness_pass,
           "lift": harness_pass - naive_pass, "rows": rows}
    if verbose:
        print(f"\nNAIVE   tests passed: {naive_pass}/{n} ({naive_pass/n:.0%})")
        print(f"HARNESS tests passed: {harness_pass}/{n} ({harness_pass/n:.0%})")
        print(f"LIFT (SWE-Bench-style, test-scored): +{res['lift']}")
    return res


def run_models(model_ids=None, harness_exec=True, verbose=True) -> list:
    """Run the test-scored coding A/B across several models → proof the lift GENERALIZES.
    Each model gets its own single-model tier so the comparison is clean."""
    from . import config
    from .eval_assumptions import DEFAULT_MODELS
    model_ids = model_ids or DEFAULT_MODELS
    results = []
    for m in model_ids:
        if verbose:
            print(f"\n=== {m} ===")
        tier = config.Tier(name=f"swe-{m.split('/')[-1][:18]}", protocol="openai",
                           base_url=config._T1_URL, model=m, api_key=config._T1_KEY,
                           timeout_s=config._T1_TIMEOUT)
        r = run(tiers=[tier], harness_exec=harness_exec, verbose=verbose)
        r["model"] = m
        results.append(r)
    if verbose:
        print("\n──────── CODING (test-scored) — lift across models ────────")
        for r in results:
            print(f"  {r['model'][:34]:34}  naive {r['naive']}/{r['tasks']} "
                  f"→ harness {r['harness']}/{r['tasks']}   (+{r['lift']})")
    return results


if __name__ == "__main__":
    import sys
    run(harness_exec="--exec" in sys.argv or True)

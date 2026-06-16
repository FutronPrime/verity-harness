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

# Each task: a PLAUSIBLE-but-incomplete implementation whose full spec lives ONLY in the hidden test —
# non-obvious rules you can't guess from the code alone. The NAIVE arm never sees the test, so it ships
# a reasonable guess that misses the spec'd edges. The HARNESS arm READS + RUNS the test and is forced
# to satisfy the real spec. This is the honest real-world difference: a model that tests its work vs one
# that doesn't. (Not "find the obvious bug" — there is no obvious bug; the requirement is hidden.)
TASKS = [
    {"name": "slugify",
     "buggy": ("def slugify(s):\n"
               "    return s.lower().replace(' ', '-')\n"),
     "test": ("from sol import slugify\n"
              "assert slugify('Hello World') == 'hello-world'\n"
              "assert slugify('  Spaced  Out  ') == 'spaced-out', 'collapse+trim'\n"
              "assert slugify('Foo & Bar!') == 'foo-bar', 'strip punctuation, no double hyphen'\n"
              "assert slugify('a---b') == 'a-b', 'collapse hyphens'\n"
              "print('PASS')\n")},
    {"name": "truncate",
     "buggy": ("def truncate(s, n):\n"
               "    if len(s) <= n:\n"
               "        return s\n"
               "    return s[:n] + '...'\n"),
     "test": ("from sol import truncate\n"
              "assert truncate('hello', 10) == 'hello'\n"
              "assert truncate('hello world', 8) == 'hello...', 'TOTAL length (with ellipsis) must be <= n'\n"
              "assert truncate('abcdefgh', 5) == 'ab...'\n"
              "assert len(truncate('abcdefgh', 5)) == 5\n"
              "print('PASS')\n")},
    {"name": "parse_bool",
     "buggy": ("def parse_bool(s):\n"
               "    return s == 'true'\n"),
     "test": ("from sol import parse_bool\n"
              "assert parse_bool('true') is True\n"
              "assert parse_bool('True') is True, 'case-insensitive'\n"
              "assert parse_bool('YES') is True and parse_bool('1') is True and parse_bool('on') is True\n"
              "assert parse_bool('false') is False and parse_bool('') is False and parse_bool('0') is False\n"
              "print('PASS')\n")},
    {"name": "round_half_even",
     "buggy": ("def bankers_round(x):\n"
               "    return int(x + 0.5)\n"),
     "test": ("from sol import bankers_round\n"
              "assert bankers_round(2.5) == 2, 'round half to EVEN (banker rounding)'\n"
              "assert bankers_round(3.5) == 4\n"
              "assert bankers_round(0.5) == 0 and bankers_round(1.5) == 2\n"
              "assert bankers_round(2.4) == 2 and bankers_round(2.6) == 3\n"
              "print('PASS')\n")},
    {"name": "pluralize",
     "buggy": ("def pluralize(word, count):\n"
               "    return word if count == 1 else word + 's'\n"),
     "test": ("from sol import pluralize\n"
              "assert pluralize('cat', 1) == 'cat'\n"
              "assert pluralize('cat', 2) == 'cats'\n"
              "assert pluralize('box', 2) == 'boxes', 'words ending in s/x/z/ch/sh add -es'\n"
              "assert pluralize('bus', 3) == 'buses'\n"
              "assert pluralize('cat', 0) == 'cats', '0 is plural'\n"
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
                resp = ask(f"Here is `sol.py`:\n```python\n{t['buggy']}```\n"
                           "Make this function correct and robust — handle the edge cases a good "
                           "implementation should. Output ONLY the corrected full contents of sol.py "
                           "in one ```python block.", **kw)
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

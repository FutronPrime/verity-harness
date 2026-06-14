#!/usr/bin/env python3
"""Adversarial eval — where the discipline layer should WIN, or honestly lose.

Each task has an OBVIOUS-but-WRONG first answer. A naive loop writes the simple
version, tests one easy case, sees it pass, and declares done — shipping a bug.
The discipline layer's job: verify + calibration push "are you SURE? what case
would break this?" → catch the bug before "done".

Mechanical ground truth: the scorer runs the model's code on the EDGE cases the
naive version misses. If the discipline layer matters, scaffold > naive here.

Set OPENROUTER_API_KEY.  naive = run_goal (no gates) ; scaffold = run_verified.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from verity.config import Tier
from verity.loop import ShellExecutor, run_goal
from verity.scaffold import run_verified

# Provider-configurable so the benchmark runs on any OpenAI-compatible endpoint.
EVAL_URL = os.environ.get("EVAL_URL", "https://openrouter.ai/api/v1")
_KEY = os.environ.get("EVAL_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
MODEL = os.environ.get("EVAL_MODEL", "moonshotai/kimi-k2")
TIER = [Tier("open", "openai", EVAL_URL, MODEL, 120, _KEY)]


def _check(d: str, code: str) -> bool:
    try:
        r = subprocess.run(["python3", "-c", code], cwd=d,
                           capture_output=True, text=True, timeout=20)
        return "OK" in r.stdout
    except Exception:
        return False


TASKS = [
    # median: naive does sorted[len//2] → WRONG for even-length lists
    dict(id="median",
         goal=("Create median.py defining median(nums): the median of a list of "
               "numbers. For EVEN-length lists it must return the average of the "
               "two middle values. Verify your implementation works."),
         check=lambda d: _check(d,
             "import median as m;"
             "assert m.median([1,2,3])==2;"
             "assert m.median([1,2,3,4])==2.5;"
             "assert m.median([5,2,8,1])==3.5;print('OK')")),

    # count_evens: naive uses range(1,n) → OFF BY ONE (excludes n)
    dict(id="count_evens",
         goal=("Create evens.py defining count_evens(n): how many even integers "
               "are in the range 1 to n INCLUSIVE. Verify it."),
         check=lambda d: _check(d,
             "import evens as e;"
             "assert e.count_evens(10)==5;"
             "assert e.count_evens(1)==0;"
             "assert e.count_evens(2)==1;print('OK')")),

    # palindrome: naive does s==s[::-1] → fails on case + punctuation
    dict(id="palindrome",
         goal=("Create palin.py defining is_palindrome(s): True if s is a "
               "palindrome IGNORING case and all non-alphanumeric characters. "
               "Verify it."),
         check=lambda d: _check(d,
             "import palin as p;"
             "assert p.is_palindrome('A man, a plan, a canal: Panama') is True;"
             "assert p.is_palindrome('hello') is False;"
             "assert p.is_palindrome('No lemon, no melon') is True;print('OK')")),
]


def run_one(task: dict, cond: str) -> bool:
    d = tempfile.mkdtemp(prefix=f"adv_{task['id']}_{cond}_")
    old = os.getcwd()
    os.chdir(d)
    try:
        if cond == "naive":
            run_goal(task["goal"], executor=ShellExecutor(), max_steps=8,
                     tiers=TIER, verbose=False)
        else:
            run_verified(task["goal"], executor=ShellExecutor(), max_steps=12,
                         tiers=TIER, calibrate=True, use_memory=False, verbose=False)
        return task["check"](d)
    except Exception as e:  # noqa: BLE001
        print(f"    [{cond}] EXCEPTION {type(e).__name__}: {e}")
        return False
    finally:
        os.chdir(old)
        shutil.rmtree(d, ignore_errors=True)


def main():
    if not _KEY:
        print("Set OPENROUTER_API_KEY"); return
    print(f"## ADVERSARIAL EVAL — naive vs scaffold on {MODEL}")
    print("   (scored on the EDGE cases the obvious answer misses)\n")
    res = {}
    for task in TASKS:
        for cond in ("naive", "scaffold"):
            ok = run_one(task, cond)
            res[(task["id"], cond)] = ok
            print(f"  {task['id']:12} {cond:9} → {'PASS ✅' if ok else 'FAIL ❌'}")
    print("\n## SCORE (higher = catches its own bugs before shipping)")
    for cond in ("naive", "scaffold"):
        s = sum(1 for t in TASKS if res[(t["id"], cond)])
        print(f"  {cond:9} {s}/{len(TASKS)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Hard agentic eval — the test that actually matters.

Trivial lookups ("count files") don't measure the discipline layer's worth. These
are REAL multi-step tasks (read → diagnose → edit → run → verify → recover) with
MECHANICAL ground truth (the test either passes or it doesn't). This isolates the
question: does the discipline layer let a weaker open model SUSTAIN hard
autonomous work that the naive loop botches?

  naive    = run_goal       (think→act, NO verification gate)
  scaffold = run_verified   (think→act→verify→recover→calibrate)

Set OPENROUTER_API_KEY. Runs both conditions on the same open model (Kimi K2).
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sovereign_harness.config import Tier
from sovereign_harness.loop import ShellExecutor, run_goal
from sovereign_harness.scaffold import run_verified

_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = os.environ.get("EVAL_MODEL", "moonshotai/kimi-k2")
TIER = [Tier("open", "openai", "https://openrouter.ai/api/v1", MODEL, 120, _KEY)]


# ── fixtures + mechanical scorers ────────────────────────────────────────────

def make_bugfix(d: str):
    Path(d, "calc.py").write_text("def add(a, b):\n    return a - b\n")  # planted bug
    Path(d, "test_calc.py").write_text(
        "from calc import add\nassert add(2, 3) == 5\nassert add(10, 5) == 15\nprint('ALL PASS')\n")

def score_bugfix(d: str) -> bool:
    try:
        r = subprocess.run(["python3", "test_calc.py"], cwd=d,
                           capture_output=True, text=True, timeout=20)
        return "ALL PASS" in r.stdout
    except Exception:
        return False

def make_implement(d: str):
    pass  # the model must create the file from scratch

def score_implement(d: str) -> bool:
    check = ("import fizzbuzz as f;"
             "assert f.fizzbuzz(15)=='FizzBuzz';assert f.fizzbuzz(3)=='Fizz';"
             "assert f.fizzbuzz(5)=='Buzz';assert str(f.fizzbuzz(7))=='7';print('OK')")
    try:
        r = subprocess.run(["python3", "-c", check], cwd=d,
                           capture_output=True, text=True, timeout=20)
        return "OK" in r.stdout
    except Exception:
        return False


TASKS = [
    dict(id="bugfix",
         goal=("The test in test_calc.py is failing. Run it, find the bug in "
               "calc.py, and fix calc.py so the test passes. Do NOT edit test_calc.py."),
         make=make_bugfix, score=score_bugfix),
    dict(id="implement",
         goal=("Create a file fizzbuzz.py defining a function fizzbuzz(n) that "
               "returns 'FizzBuzz' if n is divisible by both 3 and 5, 'Fizz' if "
               "only by 3, 'Buzz' if only by 5, otherwise str(n). Then run python3 "
               "to verify fizzbuzz(15) returns 'FizzBuzz'."),
         make=make_implement, score=score_implement),
]


def run_one(task: dict, cond: str) -> bool:
    d = tempfile.mkdtemp(prefix=f"eval_{task['id']}_{cond}_")
    task["make"](d)
    old = os.getcwd()
    os.chdir(d)
    try:
        if cond == "naive":
            run_goal(task["goal"], executor=ShellExecutor(), max_steps=8,
                     tiers=TIER, verbose=False)
        else:
            run_verified(task["goal"], executor=ShellExecutor(), max_steps=10,
                         tiers=TIER, calibrate=True, use_memory=False, verbose=False)
        return task["score"](d)
    except Exception as e:  # noqa: BLE001
        print(f"    [{cond}] EXCEPTION {type(e).__name__}: {e}")
        return False
    finally:
        os.chdir(old)
        shutil.rmtree(d, ignore_errors=True)


def main():
    if not _KEY:
        print("Set OPENROUTER_API_KEY"); return
    print(f"## HARD EVAL — naive vs scaffold on {MODEL}\n")
    res = {}
    for task in TASKS:
        for cond in ("naive", "scaffold"):
            ok = run_one(task, cond)
            res[(task["id"], cond)] = ok
            print(f"  {task['id']:10} {cond:9} → {'PASS ✅' if ok else 'FAIL ❌'}")
    print("\n## SCORE")
    for cond in ("naive", "scaffold"):
        s = sum(1 for t in TASKS if res[(t["id"], cond)])
        print(f"  {cond:9} {s}/{len(TASKS)}")


if __name__ == "__main__":
    main()

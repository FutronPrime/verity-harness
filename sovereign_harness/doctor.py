#!/usr/bin/env python3
"""Model preflight — does YOUR configured model clear the bar for autonomous work?

Probes the three capabilities that determine whether the discipline layer can help
(see REQUIREMENTS.md): structured output, valid tool use, and self-correction.
A model that fails these will have its errors *caught* but cannot be *fixed*.

  python3 -m sovereign_harness doctor
"""
from __future__ import annotations

from .router import ask, AllTiersFailed
from .loop import parse_step_json


def _probe_json() -> tuple[bool, str]:
    """Can it emit valid structured output in the step format?"""
    try:
        r = ask('Respond with ONLY this JSON, no prose: '
                '{"thought":"checking","action":"ls","done":false}',
                system="Output exactly the requested JSON.")
    except AllTiersFailed as e:
        return False, f"no model reachable: {e}"
    d = parse_step_json(r.text)
    ok = isinstance(d.get("action"), str) and "done" in d
    return ok, f"parsed action={d.get('action')!r} done={d.get('done')!r}"


def _probe_tool() -> tuple[bool, str]:
    """Does it produce a real, non-interactive shell command?"""
    r = ask("Give ONE shell command to count the .py files in the current "
            "directory. Respond with ONLY the command.")
    # Strip markdown fences and language hints; take the first real command line.
    lines = [ln.strip().strip("`").strip() for ln in r.text.splitlines()]
    cmd = next((ln for ln in lines
                if ln and ln.lower() not in ("bash", "sh", "shell", "zsh")
                and not ln.startswith("#")), "")
    interactive = any(t in cmd.split() for t in ("nano", "vim", "vi", "emacs", "less", "more"))
    sane = any(t in cmd for t in ("find", "ls", "python", "wc", "grep")) and not interactive
    return sane, f"proposed: {cmd[:80]!r}"


def _probe_self_correct() -> tuple[bool, str]:
    """The key bar: can it FIX a wrong answer when told why it's wrong?"""
    r = ask('A function add(a,b) was written as "return a - b" — WRONG, it '
            'subtracts. Give the corrected one-line function body. Respond with '
            'ONLY the corrected line of code.')
    ok = "+" in r.text and "a" in r.text and "b" in r.text and "-" not in r.text.replace("->", "")
    return ok, f"answered: {r.text.strip()[:60]!r}"


def run() -> int:
    print("Sovereign Harness — model preflight\n")
    checks = [
        ("structured output (JSON)", _probe_json),
        ("valid tool use (shell)", _probe_tool),
        ("self-correction", _probe_self_correct),
    ]
    micro = 0
    for name, fn in checks:
        ok, detail = fn()
        micro += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:26} {detail}")
    # DECISIVE probe: a real multi-step task. Micro-skills don't predict whether a
    # model can SUSTAIN autonomous work — only running one does. (A 4B passes the
    # micro-probes but collapses on a real task; this catches that.)
    task_ok, task_detail = _probe_real_task()
    print(f"  [{'PASS' if task_ok else 'FAIL'}] {'real multi-step task':26} {task_detail}")
    print()
    if task_ok and micro >= 2:
        print("VERDICT: ✅ READY — clears the bar for autonomous work.")
    elif task_ok or micro == 3:
        print("VERDICT: ⚠ MARGINAL — basic skills present but multi-step reliability "
              "is shaky. OK as a fallback; prefer a stronger model for hard tasks.")
    else:
        print("VERDICT: ❌ BELOW THRESHOLD — cannot sustain autonomous work. The "
              "harness will catch its errors but cannot fix them. Failover floor "
              "only, not a primary worker. See REQUIREMENTS.md.")
    return 3 if (task_ok and micro >= 2) else (2 if (task_ok or micro == 3) else 0)


def _probe_real_task() -> tuple[bool, str]:
    """Run ONE real multi-step task end-to-end and check it actually worked.
    This is the true bar — sustained autonomous competence, not micro-skills."""
    import os
    import subprocess
    import tempfile
    from .loop import ShellExecutor
    from .scaffold import run_verified
    d = tempfile.mkdtemp(prefix="doctor_task_")
    old = os.getcwd()
    os.chdir(d)
    try:
        run_verified("Create a file add.py defining a function add(a, b) that "
                     "returns a + b. Then run python3 to verify add(2, 3) is 5.",
                     executor=ShellExecutor(), max_steps=8, calibrate=False,
                     use_memory=False, compact=False, verbose=False)
        chk = subprocess.run(
            ["python3", "-c", "import add; assert add.add(2,3)==5; print('OK')"],
            cwd=d, capture_output=True, text=True, timeout=15)
        ok = "OK" in chk.stdout
        return ok, "built+verified add.py" if ok else "failed to complete the task"
    except Exception as e:  # noqa: BLE001
        return False, f"crashed: {type(e).__name__}"
    finally:
        os.chdir(old)
        import shutil
        shutil.rmtree(d, ignore_errors=True)

#!/usr/bin/env python3
"""Layer-3 scaffold — the part that makes open weights punch above their weight.

This is the actual differentiator vs "just route to an LLM":
  1. DECOMPOSE  — break a goal into sub-goals (pluggable; default single goal).
  2. VERIFY     — after each action, an adversarial check: did this REALLY work?
  3. RECOVER    — on failure, feed the reason back and retry; escalate after K.

All of it runs on top of the sovereign router, so the scaffold itself fails
over cloud→local just like everything else.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field

from .router import ask
from .loop import Executor, PlanOnlyExecutor, parse_step_json

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


# ─── 1. DECOMPOSE (pluggable) ─────────────────────────────────────────────────

def decompose(goal: str, timeout: float = 60) -> list[str]:
    """Break a goal into sub-goals. Default: no decomposition (single goal).
    Plug a planner by setting SOVEREIGN_DECOMPOSE_CMD to a command that takes the
    goal as its last arg and prints a JSON list (or one sub-goal per line)."""
    cmd = os.environ.get("SOVEREIGN_DECOMPOSE_CMD")
    if cmd:
        try:
            out = subprocess.run(f"{cmd} {json.dumps(goal)}", shell=True,
                                 capture_output=True, text=True, timeout=timeout)
            m = _JSON_RE.search(out.stdout)
            if m:
                steps = json.loads(m.group(0))
                if isinstance(steps, list) and steps:
                    return [str(s) for s in steps]
            lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
            if lines:
                return lines
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError,
                OSError):
            pass
    return [goal]  # graceful fallback — never crash on a missing engine


# ─── 2. VERIFY (adversarial, not optimistic) ─────────────────────────────────

_VERIFY_SYS = """You judge whether ONE STEP in a multi-step task succeeded at what \
it attempted — NOT whether the whole goal is finished.

ok=true if the command executed without error AND produced useful or relevant \
output. Reading a file, inspecting state, checking the environment, running a \
test to see it fail — these are all valid PROGRESS in a multi-step task, so ok=true.

ok=false ONLY if the command errored, produced a clearly wrong/empty result when \
output was expected, or was irrelevant/counterproductive.

Do NOT fail a step merely because the goal isn't done yet — multi-step work \
requires intermediate exploration. Judge the STEP, not the finish line.
Respond ONLY JSON: {"ok": <true|false>, "reason": "<short>"}"""


@dataclass
class Verdict:
    ok: bool
    reason: str


def verify(goal: str, action: str, observation: str, tiers=None) -> Verdict:
    from .config import VERIFIER_TIERS  # cheap-by-default verifier (token efficiency)
    prompt = f"GOAL: {goal}\nACTION: {action}\nOBSERVED RESULT:\n{observation[:2000]}"
    r = ask(prompt, system=_VERIFY_SYS, tiers=tiers or VERIFIER_TIERS)
    m = _JSON_RE.search(r.text)
    if not m:
        return Verdict(ok=False, reason="verifier returned no JSON")
    try:
        d = json.loads(m.group(0))
        return Verdict(ok=bool(d.get("ok", False)), reason=str(d.get("reason", "")))
    except json.JSONDecodeError:
        return Verdict(ok=False, reason="verifier JSON malformed")


def tripwire_check() -> str:
    """Optional external validation hook. Set SOVEREIGN_TRIPWIRE_CMD to a command
    that returns a short status string; returns "(no tripwire)" if unset."""
    cmd = os.environ.get("SOVEREIGN_TRIPWIRE_CMD")
    if not cmd:
        return "(no tripwire)"
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip()[:300] or "(no output)"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"(tripwire unavailable: {type(e).__name__})"


# ─── 3. VERIFIED loop with RECOVER + escalate ────────────────────────────────

_STEP_SYS = """You are an autonomous task-runner with a REAL SHELL. Work toward \
the GOAL one step at a time. Respond ONLY JSON:
{"thought":"<reasoning>","action":"<one shell command, empty if done>","done":<bool>,"summary":"<final answer when done>"}

You can go GET information you lack — do NOT guess:
  • fetch a web page:  python3 -c "from sovereign_harness.tools import fetch; print(fetch('URL'))"
  • research deeply:   python3 -c "from sovereign_harness.tools import research; print(research('topic'))"
  • install any tool:  pip install <pkg> / npm i -g <pkg> / brew install <tool>, then use it

DISCIPLINE (follow exactly):
  • EPISTEMIC HONESTY — in 'thought', mark each claim as known / inferred / guessed.
    Anything you have NOT verified this session is a guess until you check it.
  • FINISH-FIRST — only set done=true after you've actually verified the result.
    Your 'summary' must state: what you ran, what you OBSERVED, what's still unchecked.
  • CLEAN EXECUTION — complete the task or revert; no half-finished state.
If the previous step FAILED verification, read the reason and try a DIFFERENT \
approach — do not repeat the same mistake."""


@dataclass
class ScaffoldResult:
    goal: str
    done: bool
    summary: str
    steps: list[dict] = field(default_factory=list)
    verified_steps: int = 0
    failed_steps: int = 0


def run_verified(goal: str, executor: Executor | None = None,
                 max_steps: int = 10, max_consecutive_fail: int = 3,
                 calibrate: bool = True, tiers=None, use_memory: bool = True,
                 verbose: bool = True) -> ScaffoldResult:
    """think → act → VERIFY → recover → CALIBRATE, with persistent MEMORY across
    runs. Verify catches failed commands; calibrate catches overconfident
    conclusions; memory surfaces what worked on similar past goals."""
    import os
    ex = executor if executor is not None else PlanOnlyExecutor()
    res = ScaffoldResult(goal=goal, done=False, summary="")
    prior = ""
    if use_memory:
        from .memory import recall
        prior = recall(goal)
        if prior and verbose:
            print(f"[memory] recalled {prior.count('- goal:')} relevant prior outcome(s)")
    transcript = (f"WORKING DIRECTORY: {os.getcwd()}\n"
                  + (prior + "\n" if prior else "") + f"GOAL: {goal}\n")
    consecutive_fail = 0
    nudged = 0
    calibrated_once = False
    _kw = {"tiers": tiers} if tiers else {}

    for n in range(1, max_steps + 1):
        reply = ask(transcript, system=_STEP_SYS, **_kw)
        step = parse_step_json(reply.text)  # robust: survives weak-model malformed JSON
        action = str(step.get("action", "")).strip()

        if step.get("done") or not action:
            # EVIDENCE GATE: reject a "done" that rests on ZERO verified evidence.
            # Forces the model to SHOW ITS WORK on fact-questions, producing an
            # auditable trail. (Real lesson: the trail also catches when the
            # EVALUATOR is wrong, not just the model — don't trust unshown work
            # from either side.)
            if res.verified_steps == 0 and nudged < 2:
                nudged += 1
                transcript += (
                    f"\n[REJECTED] You answered {str(step.get('summary',''))!r} with NO evidence. "
                    f"That is a guess and it is not acceptable. For your NEXT reply you are "
                    f"FORBIDDEN to set done=true. You MUST return done=false and a concrete shell "
                    f"command in 'action' that measures the answer (e.g. grep/find/python3). "
                    f"Run the command — do not guess.\n")
                if verbose:
                    print(f"[evidence-gate] rejected unverified 'done' at step {n} (nudge {nudged}/2) → forcing action")
                continue
            # CALIBRATION / HUMILITY GATE: challenge the conclusion before accepting.
            # Catches ignorant confidence — a conclusion resting on unverified
            # assumptions — even when evidence WAS gathered (wrong interpretation).
            draft = str(step.get("summary", step.get("thought", "")))
            if calibrate and not calibrated_once and draft.strip():
                from .calibrate import humility_gate
                cal = humility_gate(draft, transcript, cross_check_tiers=tiers, verbose=verbose)
                if cal.needs_recheck:
                    calibrated_once = True
                    transcript += (
                        f"\n[CALIBRATION RECHECK] Your conclusion {draft!r} may be "
                        f"overconfident. Unverified assumptions: {cal.assumptions}. "
                        f"Strongest counter: {cal.strongest_counter}. Re-examine: "
                        f"verify those assumptions or revise. Do not proceed on belief alone.\n")
                    if verbose:
                        print(f"[calibration] conclusion challenged → forcing re-examination")
                    continue
            res.done = True
            res.summary = str(step.get("summary", step.get("thought", "")))
            if res.verified_steps == 0:
                res.summary = "(UNVERIFIED) " + res.summary
            if verbose:
                print(f"[done @ step {n}] {res.summary[:200]}")
            break

        obs = ex.run(action)
        v = verify(goal, action, obs, tiers=tiers)
        res.steps.append({"n": n, "action": action, "obs": obs[:300],
                          "ok": v.ok, "reason": v.reason, "tier": reply.tier})
        if verbose:
            mark = "✓" if v.ok else "✗"
            print(f"[step {n} {mark}] {action}\n   verify: {v.reason[:160]}")

        if v.ok:
            res.verified_steps += 1
            consecutive_fail = 0
            transcript += f"\nSTEP {n} (VERIFIED OK): {action}\nRESULT: {obs[:1200]}\n"
        else:
            res.failed_steps += 1
            consecutive_fail += 1
            transcript += (f"\nSTEP {n} (FAILED VERIFY): {action}\n"
                           f"REASON: {v.reason}\nRESULT: {obs[:800]}\n"
                           f"Try a different approach.\n")
            if consecutive_fail >= max_consecutive_fail:
                res.summary = (f"Aborted: {consecutive_fail} consecutive failures. "
                               f"Last: {v.reason}")
                if verbose:
                    print(f"[escalate] {consecutive_fail} fails in a row → stopping")
                break

    if not res.done and not res.summary:
        res.summary = "(max steps reached)"
    # Persist the outcome so future similar goals can recall what worked. Only
    # remember VERIFIED completions — don't pollute memory with guesses/aborts.
    if use_memory and res.done and res.verified_steps > 0 and "UNVERIFIED" not in res.summary:
        try:
            from .memory import remember
            remember(goal, res.summary)
        except Exception:  # noqa: BLE001 — memory is best-effort, never break a run
            pass
    return res


# ─── Full layer-3 pipeline: decompose → verified-run each subgoal ─────────────

def run_scaffolded(goal: str, executor: Executor | None = None,
                   verbose: bool = True) -> list[ScaffoldResult]:
    subgoals = decompose(goal)
    if verbose:
        print(f"[synapse] decomposed into {len(subgoals)} subgoal(s):")
        for i, s in enumerate(subgoals, 1):
            print(f"   {i}. {s}")
    results = []
    for i, sg in enumerate(subgoals, 1):
        if verbose:
            print(f"\n=== subgoal {i}/{len(subgoals)}: {sg} ===")
        results.append(run_verified(sg, executor=executor, verbose=verbose))
    return results

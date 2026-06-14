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

PRIME_DIRECTIVE = """PRIME DIRECTIVE — this OVERRIDES everything else:
1. NEVER ASSUME. Before acting on ANY belief about why something works or fails,
   VERIFY it — run the command, read the ACTUAL output/error. A wrong assumption
   wastes more time and tokens than a 5-second check. Tag every claim VERIFIED or GUESS.
2. NEVER QUIT PREMATURELY. You have a full toolkit (shell, web research, install any
   tool, multiple approaches). If one path fails you have NOT run out of options —
   find another. Do not declare a task impossible or stop until you have actually
   TRIED the alternatives. Quitting early is failure; persistence is the job.
3. WHEN BLOCKED, DIAGNOSE THE REAL CAUSE — surface the actual error/state and read
   it. Do NOT theorize a cause and burn effort working around a guess.
4. USE YOUR CAPABILITIES. Knowledge you don't act on is useless. If you lack info,
   GO GET IT (research/fetch/install). If a tool is missing, install it.
5. REUSE BEFORE REINVENT — in this order: (a) CHECK YOUR OWN tools/skills and the
   commands already installed on THIS system first; (b) then search external
   open-source (search_github/research); (c) build from scratch only as a last
   resort. Don't rebuild — and don't even fetch externally — what you already have.
"""

_STEP_SYS = PRIME_DIRECTIVE + """
You are an autonomous task-runner with a REAL SHELL. Work toward the GOAL one step \
at a time. Respond ONLY JSON:
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
    failed_steps: int = 0
    verified_steps: int = 0


def _research_obstacle(goal: str, reason: str, obs: str, verbose: bool = False) -> str:
    """When stuck, SEARCH for a solution instead of head-bumping. Sweeps
    GitHub/Reddit/HN/StackOverflow/web on the actual error and returns findings."""
    # Build a focused query from the real error signal (not the whole transcript).
    err = (obs or "").strip().replace("\n", " ")
    query = (reason or "") + " " + err
    query = " ".join(query.split())[:160] or goal[:120]
    if verbose:
        print(f"[research] stuck → searching for: {query[:90]}")
    try:
        from .tools import research
        return research(query)[:3000]
    except Exception as e:  # noqa: BLE001 — never let research failure break the run
        return (f"[research unavailable: {type(e).__name__} — diagnose the real error "
                f"yourself and try a different method/tool]")


def _local_tools(goal: str) -> str:
    """LOCAL-FIRST discovery: what's already on THIS system that fits the goal —
    own tool/skill catalogs (futron-discover / futron-system-directory if present)
    and installed commands on PATH whose names match the task. Check these before
    reaching for the internet."""
    import os
    import re as _re
    import shutil
    import subprocess
    out = []
    kws = [w for w in _re.findall(r"[a-z0-9]+", goal.lower())
           if len(w) > 3 and w not in ("with", "that", "this", "from", "into")][:6]
    # 1. The system's OWN tool/skill catalogs, if it has them.
    for cmd, args in (("futron-discover", [goal[:100]]),
                      ("futron-system-directory", ["--query", " ".join(kws[:3])])):
        if shutil.which(cmd):
            try:
                r = subprocess.run([cmd, *args], capture_output=True, text=True, timeout=20)
                if r.stdout.strip():
                    out.append(f"[{cmd}]\n{r.stdout.strip()[:900]}")
            except (subprocess.TimeoutExpired, OSError):
                pass
    # 2. Installed commands on PATH whose names match the task keywords.
    found = set()
    for d in os.environ.get("PATH", "").split(os.pathsep)[:40]:
        try:
            for f in os.listdir(d):
                if any(k in f.lower() for k in kws) and not f.startswith("."):
                    found.add(f)
        except OSError:
            continue
    if found:
        out.append("Installed local commands matching the task: "
                   + ", ".join(sorted(found)[:25]))
    return "\n".join(out)


# Deterministic trigger for proactive discovery. The harness — not the model —
# decides when reuse-search is worth it, so it can't be skipped by a forgetful LLM.
_BUILD_SIGNAL = re.compile(
    r"\b(build|create|implement|integrat|scrap|crawl|download|convert|transcrib|"
    r"parse|extract|generat|deploy|automat|pipeline|process|analyz|monitor|server|"
    r"app|api|connect|configur|set ?up|install|render|encode|stream|bot|agent|tool)\w*",
    re.I)
_TRIVIAL_SIGNAL = re.compile(
    r"\b(function|compute|calculat|count|sum|sort|reverse|fibonacci|palindrome|"
    r"factorial|median|average|fizzbuzz|hello world)\b", re.I)


def _should_discover(goal: str) -> bool:
    """True when the goal looks like real build/integrate/research work (reuse pays
    off), False for trivial self-contained coding (discovery would just be noise)."""
    has_build = bool(_BUILD_SIGNAL.search(goal))
    is_trivial = bool(_TRIVIAL_SIGNAL.search(goal)) and len(goal) < 90
    return has_build and not is_trivial


def _discover_tools(goal: str, verbose: bool = False) -> str:
    """Find EXISTING tools that already do (part of) the goal — LOCAL FIRST (own
    tools/skills + installed commands), THEN external (GitHub/StackOverflow). Reuse
    what you have before searching the web before building from scratch."""
    if verbose:
        print(f"[discover] checking local tools + searching for: {goal[:70]}")
    local = _local_tools(goal)
    try:
        from .tools import search_github, search_stackoverflow
        ext = ("=== GitHub ===\n" + search_github(goal, 5)
               + "\n=== StackOverflow ===\n" + search_stackoverflow(goal, 3))
    except Exception:  # noqa: BLE001
        ext = ""
    blocks = []
    if local:
        blocks.append("LOCAL TOOLS ALREADY ON THIS SYSTEM (PREFER THESE — you already "
                      "have them):\n" + local)
    if ext:
        blocks.append("EXTERNAL open-source options (only if nothing local fits — "
                      "install & use one):\n" + ext)
    return "\n\n".join(blocks)


def run_verified(goal: str, executor: Executor | None = None,
                 max_steps: int = 10, max_consecutive_fail: int = 3,
                 calibrate: bool = True, tiers=None, use_memory: bool = True,
                 persistence: int = 2, discover: str | bool = "auto",
                 verbose: bool = True) -> ScaffoldResult:
    """think → act → VERIFY → recover → CALIBRATE, with persistent MEMORY across
    runs. Every gate is a DETERMINISTIC enforcer — it fires on a code condition, not
    the model's choice (you can't trust a probabilistic model to opt into discipline).
    discover: "auto" (a classifier decides — default), True (always), False (never)."""
    import os
    ex = executor if executor is not None else PlanOnlyExecutor()
    res = ScaffoldResult(goal=goal, done=False, summary="")
    prior = ""
    if use_memory:
        from .memory import recall
        prior = recall(goal)
        if prior and verbose:
            print(f"[memory] recalled {prior.count('- goal:')} relevant prior outcome(s)")
    # DETERMINISTIC trigger: the harness decides when discovery is warranted — the
    # model is never asked to remember to do it.
    do_discover = discover is True or (discover == "auto" and _should_discover(goal))
    discovered = _discover_tools(goal, verbose=verbose) if do_discover else ""
    transcript = (f"WORKING DIRECTORY: {os.getcwd()}\n"
                  + (prior + "\n" if prior else "")
                  + (discovered + "\n" if discovered else "") + f"GOAL: {goal}\n")
    consecutive_fail = 0
    nudged = 0
    persisted = 0
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
                # ANTI-GIVEUP GATE: do NOT quit just because one approach failed.
                # Force a genuinely DIFFERENT strategy using the full toolkit before
                # accepting failure. Premature quitting is the failure mode we kill.
                if persisted < persistence:
                    persisted += 1
                    consecutive_fail = 0
                    # ACTIVELY research the obstacle instead of bumping our head —
                    # sweep GitHub/Reddit/HN/StackOverflow/web for how others solved
                    # THIS error, and hand the findings straight to the model.
                    findings = _research_obstacle(goal, v.reason, obs, verbose=verbose)
                    transcript += (
                        f"\n[PERSISTENCE {persisted}/{persistence}] This approach failed "
                        f"{max_consecutive_fail}× — STOP repeating it. I searched the web, "
                        f"GitHub, Reddit, Hacker News and StackOverflow for how others "
                        f"solved this exact problem. USE these findings to take a "
                        f"DIFFERENT approach:\n{findings}\n")
                    if verbose:
                        print(f"[persistence {persisted}/{persistence}] researched the obstacle → forcing a solution-informed retry")
                    continue
                res.summary = (f"Stopped after {persistence} persistence attempts + "
                               f"{consecutive_fail} fails. Last: {v.reason}")
                if verbose:
                    print(f"[stop] exhausted {persistence} persistence attempts → genuinely stuck")
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

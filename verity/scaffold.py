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
    Plug a planner by setting VERITY_DECOMPOSE_CMD to a command that takes the
    goal as its last arg and prints a JSON list (or one sub-goal per line)."""
    cmd = os.environ.get("VERITY_DECOMPOSE_CMD")
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
    """Optional external validation hook. Set VERITY_TRIPWIRE_CMD to a command
    that returns a short status string; returns "(no tripwire)" if unset."""
    cmd = os.environ.get("VERITY_TRIPWIRE_CMD")
    if not cmd:
        return "(no tripwire)"
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip()[:300] or "(no output)"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"(tripwire unavailable: {type(e).__name__})"


# ─── 3. VERIFIED loop with RECOVER + escalate ────────────────────────────────

PRIME_DIRECTIVE = """PRIME DIRECTIVE — this OVERRIDES everything else:
0. METACOGNITION FIRST. Monitor your own knowledge state: for this goal, separate what you
   actually KNOW from what you're assuming, and treat your training as FINITE and possibly
   STALE. Then control your process: when there's a gap or things may have changed, GO GET the
   current best knowledge from the live world (search GitHub/Google/Reddit/X/YouTube/SO) and
   apply THAT — don't run on old priors. "Know what you don't know, then hire the right
   resource to fill the gap." The live internet is your real knowledge base; your weights are
   just the starting point.
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
6. SEARCH BEFORE YOU CONCLUDE IT CAN'T BE DONE. A NEGATIVE claim — "there's no X",
   "X doesn't exist", "not possible", "no free option", "the only way is Y" — is an
   ASSUMPTION, and the most expensive kind. Before any such claim stands, you MUST
   proactively search where solutions actually live: GitHub (existing libs/tools),
   Google, Reddit, X, YouTube, Stack Overflow. Someone has almost certainly hit this
   and open-sourced or documented a fix. One source saying "no" is NOT evidence of
   absence — go look. (Real example: "X has no free posting API" was FALSE — a
   30-second GitHub search finds `twikit`, which posts for free.) Cite what you found.
"""

_STEP_SYS = PRIME_DIRECTIVE + """
You are an autonomous task-runner with a REAL SHELL. Work toward the GOAL one step \
at a time. Respond ONLY JSON:
{"thought":"<reasoning>","action":"<one shell command, empty if done>","done":<bool>,"summary":"<final answer when done>"}

You can go GET information you lack — do NOT guess:
  • fetch a web page:  python3 -c "from verity.tools import fetch; print(fetch('URL'))"
  • research deeply:   python3 -c "from verity.tools import research; print(research('topic'))"
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
    from . import ledger
    try:
        from .tools import research
        found = research(query)[:3000]
        # RECEIPT: log that rule-6 search fired and what it surfaced (proof of usage + effect).
        ledger.log(ledger.SEARCH, trigger=f"blocked: {reason[:80]}", detail=query,
                   verdict="FOUND" if found.strip() else "NONE", evidence=found[:200])
        return found
    except Exception as e:  # noqa: BLE001 — never let research failure break the run
        ledger.log(ledger.SEARCH, trigger=f"blocked: {reason[:80]}", detail=query, verdict="NONE")
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
    # 0. REUSE-FIRST for web access — surface the system's own scrape/search/browse tools so
    #    the model never hand-rolls a scraper when a cascade is already installed.
    if _re.search(r"\b(web|search|scrap|crawl|fetch|url|http|browse|research|find|lookup|online)\b",
                  goal.lower()):
        try:
            from .tools import system_web_tools
            if (wt := system_web_tools()):
                out.append(wt)
        except Exception:  # noqa: BLE001
            pass
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


def _preflight(goal: str, verbose: bool = False) -> str:
    """METACOGNITIVE PRE-FLIGHT — 'know what you don't know, then hire the right resource.'

    Before executing, live-search the BEST CURRENT / established way to do this exact goal, so
    the run leverages the internet's up-to-the-minute world-knowledge instead of the model's
    finite, stale training weights. This is the lever that lets a WEAKER model punch up: a
    pinpoint search for the precise goal beats a strong model reasoning from old priors. The
    model's job stops being "recall the answer" and becomes "find + apply the current best one."
    (Metacognition: monitor the knowledge gap, then act to fill it — the harness forces both.)"""
    from . import ledger
    if verbose:
        print(f"[preflight] live-searching current best approach for: {goal[:70]}")
    findings = ""
    try:
        from .tools import research, registry_hint
        findings = research(f"best current 2026 approach + established tools to {goal}"[:140])[:2500]
        # GROUND TRUTH for model-id goals: web search rarely carries exact post-cutoff slugs, so a
        # weaker model in the agentic loop would hallucinate — this was the coordination REGRESSION
        # (generic loop had web noise, no registry). Prepend the authoritative registry when relevant.
        rh = registry_hint(goal)
        if rh:
            findings = rh + ("\n\n" + findings if findings.strip() else "")
        # REUSE-FIRST: if the goal looks like building/finding something, surface curated existing
        # tools/awesome-lists so the model checks them BEFORE reinventing (VERITY's core thesis).
        from .resources import reuse_hint
        uh = reuse_hint(goal)
        if uh:
            findings = uh + ("\n\n" + findings if findings.strip() else "")
    except Exception:  # noqa: BLE001 — never let preflight failure break the run
        findings = ""
    ledger.log(ledger.SEARCH, trigger="preflight: current best approach",
               detail=goal[:120], verdict="FOUND" if findings.strip() else "NONE",
               evidence=findings[:150])
    return findings


def run_verified(goal: str, executor: Executor | None = None,
                 max_steps: int = 10, max_consecutive_fail: int = 3,
                 calibrate: bool = True, tiers=None, use_memory: bool = True,
                 persistence: int = 2, discover: str | bool = "auto",
                 preflight: str | bool = "auto", gate_cmd: str | None = None,
                 deadline_s: float | None = None,
                 verbose: bool = True) -> ScaffoldResult:
    """think → act → VERIFY → recover → CALIBRATE, with persistent MEMORY across
    runs. Every gate is a DETERMINISTIC enforcer — it fires on a code condition, not
    the model's choice (you can't trust a probabilistic model to opt into discipline).
    discover: "auto" (a classifier decides — default), True (always), False (never).

    Loop-engineering hard stops (from the 'prompter → loop designer' roadmap — a loop with
    no hard stop "runs until someone notices the bill", and a stop condition that's an LLM
    opinion is "a second optimist", not a gate):
      • gate_cmd  — an OBJECTIVE completion gate: a shell command (test/build/lint) that must
        exit 0 before any 'done' is accepted. Defeats the 'Ralph-Wiggum' loop (agent emits the
        completion token on a half-done job). A passing test beats a verifier with an opinion.
      • deadline_s — a wall-clock hard stop (seconds). With max_steps (iteration cap) this gives
        two of the article's three kill-switches; the third (token budget) is the tier layer's job."""
    import os
    import time
    ex = executor if executor is not None else PlanOnlyExecutor()
    res = ScaffoldResult(goal=goal, done=False, summary="")
    _start = time.monotonic()
    prior = ""
    if use_memory:
        from .memory import recall
        prior = recall(goal)
        if prior and verbose:
            print(f"[memory] recalled {prior.count('- goal:')} relevant prior outcome(s)")
        # Also inherit cross-path LESSONS (what the swarm + synthesize learned) so every spawn — not just
        # the swarm — remembers how similar goals were solved. (Same membank the rest of the harness writes.)
        try:
            from . import membank
            lesson = membank.recall(goal, budget_chars=700)
            if lesson and not lesson.startswith("[membank"):
                prior = (prior + "\n" if prior else "") + lesson
        except Exception:
            pass
    # DETERMINISTIC trigger: the harness decides when discovery is warranted — the
    # model is never asked to remember to do it.
    do_discover = discover is True or (discover == "auto" and _should_discover(goal))
    discovered = _discover_tools(goal, verbose=verbose) if do_discover else ""
    # METACOGNITIVE PRE-FLIGHT: research the current best approach BEFORE acting (turns the
    # live internet into the model's knowledge base). Same deterministic gating as discovery.
    do_preflight = preflight is True or (preflight == "auto" and _should_discover(goal))
    preflighted = _preflight(goal, verbose=verbose) if do_preflight else ""
    transcript = (f"WORKING DIRECTORY: {os.getcwd()}\n"
                  + (prior + "\n" if prior else "")
                  + ("CURRENT BEST APPROACH — LIVE web findings, CURRENT (post your training cutoff), so "
                     "they SUPERSEDE your training. APPLY THESE over your priors; where a value/id/name "
                     "appears here, use it verbatim — do NOT fall back to memory:\n" + preflighted + "\n"
                     if preflighted else "")
                  + (discovered + "\n" if discovered else "") + f"GOAL: {goal}\n")
    consecutive_fail = 0
    nudged = 0
    giveup_nudged = 0
    persisted = 0
    calibrated_once = False
    _kw = {"tiers": tiers} if tiers else {}

    for n in range(1, max_steps + 1):
        # HARD STOP (wall-clock) — a loop without a kill-switch runs until it burns the budget.
        if deadline_s is not None and (time.monotonic() - _start) > deadline_s:
            res.summary = (f"(hard stop: {deadline_s:.0f}s wall-clock deadline hit after "
                           f"{n - 1} steps, {res.verified_steps} verified)")
            if verbose:
                print(f"[hard-stop] {deadline_s:.0f}s deadline exceeded → stopping")
            break
        # GOAL REANCHOR — re-state the goal every few steps so long runs don't drift off it
        # (the 'turn-47' failure: summarization is lossy, "don't do X" constraints evaporate).
        if n > 1 and n % 4 == 0:
            transcript += f"\n[REANCHOR] Stay on the original GOAL: {goal}\n"
        reply = ask(transcript, system=_STEP_SYS, **_kw)
        step = parse_step_json(reply.text)  # robust: survives weak-model malformed JSON
        action = str(step.get("action", "")).strip()

        if step.get("done") or not action:
            # ANTI-GIVEUP GATE (BOTH METHODS, together): the deterministic guard fires INSIDE the loop,
            # alongside the model-based verify/evidence/calibration gates below. It kills the LLM
            # Dunning-Kruger move — concluding "it's impossible / can't be done / only a human can"
            # WITHOUT investigating. No model judges this; it's a code condition (guard.flag = regex on
            # the conclusion). On a hit, re-inject the corrective (read logs → repair → search → automate)
            # and force another pass. This is exactly what drove this session: re-injected rules, not a
            # second model, turned every premature "can't" into a real fix.
            _draft0 = str(step.get("summary", step.get("thought", "")))
            if giveup_nudged < 2:
                from .guard import flag as _flag, CORRECTIVE as _CORR
                if _flag(_draft0):
                    giveup_nudged += 1
                    transcript += f"\n{_CORR}\n"
                    if verbose:
                        print(f"[anti-giveup] premature 'can't/impossible/only-a-human' caught at step {n} "
                              f"(nudge {giveup_nudged}/2) → forcing investigation, not surrender")
                    continue
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
                from .config import VERIFIER_TIERS
                # Challenge with the VERIFIER tier (a DIFFERENT frontier brain when LLM_VERIFIER_MODEL is set)
                # so the conclusion is cross-examined by another model — true ensemble, catches errors the
                # workhorse alone would ship. Falls back to the main tiers if no separate verifier is configured.
                cal = humility_gate(draft, transcript, cross_check_tiers=(VERIFIER_TIERS or tiers), verbose=verbose)
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
            # OBJECTIVE COMPLETION GATE — a real test/build/lint, not a verifier's opinion. The
            # maker doesn't get to declare victory; an exit code does. Defeats the Ralph-Wiggum
            # loop (completion token emitted on a half-done job). Only blocks 'done', never quits.
            if gate_cmd:
                import subprocess
                try:
                    g = subprocess.run(gate_cmd, shell=True, capture_output=True,
                                       text=True, timeout=300)
                    gate_ok = g.returncode == 0
                except Exception as e:  # noqa: BLE001
                    gate_ok, g = False, None
                if not gate_ok:
                    tail = ((g.stdout or "") + (g.stderr or ""))[-400:] if g else "gate command errored"
                    transcript += (
                        f"\n[GATE FAILED] The objective completion gate `{gate_cmd}` did NOT pass "
                        f"(exit {g.returncode if g else 'ERR'}). 'done' is REJECTED until it does. "
                        f"Last gate output:\n{tail}\nReturn done=false and a command that makes the "
                        f"gate pass. A passing test — not your judgment — is what 'done' means.\n")
                    if verbose:
                        print(f"[objective-gate] `{gate_cmd}` failed → 'done' rejected, forcing more work")
                    continue
                if verbose:
                    print(f"[objective-gate] `{gate_cmd}` passed ✓ → 'done' allowed")
            res.done = True
            res.summary = str(step.get("summary", step.get("thought", "")))
            if res.verified_steps == 0:
                res.summary = "(UNVERIFIED) " + res.summary
            if verbose:
                print(f"[done @ step {n}] {res.summary[:200]}")
            break

        obs = ex.run(action)
        v = verify(goal, action, obs, tiers=tiers)
        # QC SELF-HEAL: a tool output that is ITSELF an error/empty/CAPTCHA is not a valid result —
        # never let the model reason over garbage (the bug that tanked the first eval). Override a
        # falsely-OK verify, and journal it via the ErrorHandlingProtocol so failures self-document.
        from .errorhandling import looks_like_failure
        if v.ok and looks_like_failure(obs):
            v = Verdict(ok=False, reason="QC: tool output looks like a failure (error/empty/blocked), not a result")
            try:
                from . import errorhandling
                errorhandling.handle(
                    what=f"step {n} action {action[:60]!r} returned failure-looking output",
                    why="tool returned error/empty/CAPTCHA text, not real data",
                    impact="model would reason over garbage and likely conclude wrongly",
                    fix="flagged as a FAILED step → routes into persistence/research, not 'done'",
                    prevention="looks_like_failure() QC runs on every step's output",
                    self_caused=False, postmortem="brief")
            except Exception:  # noqa: BLE001
                pass
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

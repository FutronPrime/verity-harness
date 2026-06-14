#!/usr/bin/env python3
"""Multi-agent SWARM — the Mythos/Fable shape, fully self-contained.

VERITY's base loop is single-model. Mythos/Fable-class systems get their power from a SWARM of
specialized agents (planner, researcher, executor, critic, synthesizer) exploring in parallel and
critiquing each other. This builds that natively — and **with zero external dependencies**: every
"agent" is just a model call with a role system-prompt, wrapped in VERITY's discipline gates. A
fresh `git clone` runs the same swarm with NO knowledge of any private tooling. If a richer
external orchestrator (e.g. a FUTRON forge endpoint) is present it can be used, but the swarm is
fully sovereign without it.

Flow (each step gate-disciplined + logged to the ledger = receipts):
  PLAN  → decompose the goal into independent sub-tasks
  ↓     (parallel, one worker per sub-task)
  RESEARCH → pre-flight live-search the current best approach for the sub-task
  EXECUTE  → do it (shell executor if given, else researched reasoning) under verify/QC
  CRITIQUE → an adversarial critic agent reviews; on issues, one repair pass
  ↓
  SYNTHESIZE → combine the verified sub-results into the final answer (VERIFIED vs GUESS tagged)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

import re as _re

# EVIDENCE-BASED gating (researched, not assumed — arxiv 2511.11306 iMAD + the 2026 MAD surveys):
# multi-agent debate beats single-agent in ~19/21 settings (+7% avg) BUT triggering it for EVERY
# query is wrong — it costs more AND can DEGRADE accuracy by overturning correct single answers.
# iMAD-style selective triggering (swarm only when it's likely to help) gets ~92% token savings +
# up to +13.5% accuracy. So: swarm COMPLEX/multi-part goals; use a single gated run for simple ones.
_COMPLEX = _re.compile(
    r"\b(compare|contrast|research|analyze|design|architect|plan|evaluate|investigate|"
    r"trade[- ]?offs?|pros and cons|multiple|several|end[- ]to[- ]end|comprehensive|"
    r"and then|as well as|build .* and|migrat|audit|survey)\b", _re.I)


def should_swarm(goal: str) -> bool:
    """iMAD-style selective trigger: True when a goal is complex/multi-part enough that the
    multi-agent cost pays off. Simple/atomic goals should use a single gated run (`run_verified`)
    — swarming them wastes tokens and can DEGRADE the answer (agents conform / overturn a correct
    single answer). Evidence: arxiv 2511.11306 (iMAD) + 2026 multi-agent-debate surveys."""
    g = goal.strip()
    multi_clause = g.count(",") + g.count(" and ") + g.count(";") >= 2
    return bool(_COMPLEX.search(g)) or multi_clause or len(g) > 160


ROLE_SYS = {
    "planner": (
        "You are the PLANNER in a multi-agent swarm. Decompose the GOAL into 2-5 CONCRETE, "
        "mostly-independent sub-tasks that together fully achieve it. Prefer fewer, meatier "
        "sub-tasks over many trivial ones. Respond ONLY JSON: "
        '{"subtasks":["...","..."],"thought":"why this decomposition"}'),
    "executor": (
        "You are an EXECUTOR specialist in a swarm. Do YOUR sub-task completely and correctly, "
        "using the provided research findings (prefer them over your priors — they're current). "
        "Mark each claim VERIFIED or GUESS. State what you actually did/observed."),
    "critic": (
        "You are the CRITIC in a swarm — adversarial QA. Given a sub-task and a result, find what "
        "is WRONG, UNVERIFIED, or MISSING. Be specific and skeptical; assume a flaw exists. "
        'Respond ONLY JSON: {"ok":<bool>,"issues":["..."]}  (ok=true only if genuinely sound).'),
    "synthesizer": (
        "You are the SYNTHESIZER in a swarm. Combine the verified sub-results into ONE coherent, "
        "complete answer to the GOAL. Resolve conflicts, drop nothing important, and explicitly "
        "tag what is VERIFIED vs still a GUESS. Do not invent beyond the sub-results."),
}


@dataclass
class SwarmResult:
    goal: str
    final: str
    subtasks: list[str] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    repaired: int = 0


from concurrent.futures import TimeoutError as _FutureTimeout

# Shared pool for BOUNDING individual agent calls (so one stuck call can't stall the whole swarm).
_AGENT_POOL = ThreadPoolExecutor(max_workers=8)


def _agent(role: str, prompt: str, tiers=None, timeout: float = 150.0) -> str:
    """One swarm agent = one model call through the SAME tier as everything else — so the swarm's
    agents are the SAME CALIBER as the base model: Opus-4.8 base → Opus-4.8 agents, Codex-5.5 →
    5.5 agents, a local 4B → 4B agents. Bounded by a per-call wall-clock timeout so a single stuck
    call (slow local model, provider retry storm) can't hang the swarm — it degrades to a skip."""
    from .router import ask

    def _call():
        r = ask(prompt, system=ROLE_SYS[role], **({"tiers": tiers} if tiers else {}))
        return r.text if hasattr(r, "text") else str(r)
    try:
        return _AGENT_POOL.submit(_call).result(timeout=timeout)
    except _FutureTimeout:
        return f"[agent:{role} timed out after {int(timeout)}s — skipped so the swarm can proceed]"
    except Exception as e:  # noqa: BLE001 — never let one agent kill the swarm
        return f"[agent:{role} failed: {type(e).__name__}]"


def _local_primary(tiers=None) -> bool:
    """True when the only reachable tier is LOCAL (Ollama). Then sub-tasks must run SEQUENTIALLY:
    one Ollama serializes inference, so thread-parallel just queues and risks stalls. Cloud/API
    tiers (with a key) DO handle concurrency — those parallelize."""
    from .config import TIERS
    ts = tiers or TIERS
    return not any(getattr(t, "protocol", "") == "openai" and getattr(t, "api_key", "") for t in ts)


def run_swarm(goal: str, executor=None, tiers=None, max_subtasks: int = 4,
              research: bool = True, verbose: bool = True) -> SwarmResult:
    """Run the multi-agent swarm. `executor` (a verity.loop Executor) makes sub-tasks do real
    shell work; without it sub-tasks are researched reasoning. Self-contained — no external deps."""
    from . import ledger
    from .loop import parse_step_json

    # iMAD selective-trigger transparency: warn (don't block) if this goal is simple enough that
    # a single gated run would likely be cheaper AND at least as accurate (research: swarming
    # simple tasks can DEGRADE the answer). The caller still gets the swarm if they asked for it.
    if verbose and not should_swarm(goal):
        print("[swarm] note: this goal looks simple — a single `run_verified` may be cheaper and "
              "as accurate (multi-agent pays off on COMPLEX/multi-part goals). Proceeding anyway.")

    # 1. PLAN ---------------------------------------------------------------
    plan = parse_step_json(_agent("planner", f"GOAL: {goal}", tiers))
    subtasks = [s for s in (plan.get("subtasks") or []) if str(s).strip()][:max_subtasks] or [goal]
    ledger.log("swarm-plan", trigger=goal[:80], detail=f"{len(subtasks)} sub-tasks",
               verdict="FOUND", evidence="; ".join(subtasks)[:200])
    if verbose:
        print(f"[swarm] PLAN → {len(subtasks)} sub-tasks")
        for i, s in enumerate(subtasks, 1):
            print(f"   {i}. {s[:80]}")

    # 2-3. RESEARCH → EXECUTE → CRITIQUE (parallel, one worker per sub-task) -
    repaired = [0]

    def work(st: str) -> dict:
        from .scaffold import _preflight
        findings = _preflight(st, verbose=False) if research else ""
        if executor is not None:
            from .scaffold import run_verified
            r = run_verified(st, executor=executor, preflight=False, discover=False,
                             verbose=False, tiers=tiers)
            out = r.summary
        else:
            out = _agent("executor",
                         f"SUB-TASK: {st}\n\nRESEARCH FINDINGS (prefer these):\n{findings[:2000]}\n\n"
                         "Complete the sub-task. Cite findings; tag VERIFIED/GUESS.", tiers)
        # CRITIC — adversarial review; one repair pass if it finds real issues.
        crit = parse_step_json(_agent("critic",
                 f"SUB-TASK: {st}\n\nRESULT:\n{out[:2500]}\n\nReview adversarially.", tiers))
        if crit.get("ok") is False and crit.get("issues"):
            repaired[0] += 1
            ledger.log("swarm-critic", trigger=st[:70], verdict="CORRECTED",
                       evidence="; ".join(map(str, crit["issues"]))[:200])
            out = _agent("executor",
                         f"SUB-TASK: {st}\n\nYour result had these issues:\n- "
                         + "\n- ".join(map(str, crit["issues"]))
                         + f"\n\nFix them using the findings:\n{findings[:1500]}", tiers)
        return {"subtask": st, "result": out, "issues": crit.get("issues", [])}

    if _local_primary(tiers):
        # one local model serializes anyway → run sub-tasks SEQUENTIALLY (avoids the stall).
        if verbose:
            print("[swarm] local tier → sequential sub-tasks")
        results = [work(st) for st in subtasks]
    else:
        # cloud/API tier handles concurrency → parallelize sub-tasks.
        with ThreadPoolExecutor(max_workers=min(4, len(subtasks))) as pool:
            results = list(pool.map(work, subtasks))
    if verbose:
        print(f"[swarm] EXECUTE+CRITIQUE done ({repaired[0]} repaired)")

    # 4. SYNTHESIZE ---------------------------------------------------------
    combined = "\n\n".join(f"=== SUB-TASK: {r['subtask']} ===\n{r['result']}" for r in results)
    final = _agent("synthesizer", f"GOAL: {goal}\n\nVERIFIED SUB-RESULTS:\n{combined}\n\n"
                                   "Synthesize the complete final answer.", tiers)
    ledger.log("swarm-synth", trigger=goal[:80], verdict="VERIFIED",
               evidence=f"{len(subtasks)} sub-tasks, {repaired[0]} repaired")
    if verbose:
        print("[swarm] SYNTHESIZE → final answer ready")
    return SwarmResult(goal=goal, final=final, subtasks=subtasks, results=results, repaired=repaired[0])


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print('usage: python3 -m verity.swarm "<goal>"'); sys.exit(1)
    r = run_swarm(" ".join(sys.argv[1:]))
    print("\n=== FINAL (swarm) ===\n" + r.final)

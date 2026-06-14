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


def _agent(role: str, prompt: str, tiers=None) -> str:
    from .router import ask
    r = ask(prompt, system=ROLE_SYS[role], **({"tiers": tiers} if tiers else {}))
    return r.text if hasattr(r, "text") else str(r)


def run_swarm(goal: str, executor=None, tiers=None, max_subtasks: int = 4,
              research: bool = True, verbose: bool = True) -> SwarmResult:
    """Run the multi-agent swarm. `executor` (a verity.loop Executor) makes sub-tasks do real
    shell work; without it sub-tasks are researched reasoning. Self-contained — no external deps."""
    from . import ledger
    from .loop import parse_step_json

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

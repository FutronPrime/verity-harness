#!/usr/bin/env python3
"""`verity deliberate` — the iterative-deepening loop applied to VERITY's whole reasoning, not
just web search. Don't commit the first plan: propose → self-critique for the biggest GAP →
research/re-reason that gap → refine → repeat until the critic says SUFFICIENT (or rounds run out).

This is the agentic-search-loop pattern (nibzard/awesome-agentic-patterns) generalized from "search"
to "orchestration / solution / workflow / reasoning". It composes VERITY's tested parts:
  • research  → verity.websearch.deep_research over the SIX sources (github/reddit/x/youtube/SO/HN+web)
  • reason    → any backend (frontier, or a local model via verity augment in private mode)
  • critique  → the SAME or a second backend, prompted adversarially to find the biggest gap/risk
The loop is the point: a plan that survived N rounds of "what's still wrong?" is what you commit.

  python3 -m verity deliberate "design/plan <goal>"   [--rounds N] [--no-web]
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

_CRITIQUE = (
    "You are an adversarial reviewer. Find the SINGLE biggest gap, risk, wrong assumption, or missing "
    "step in the plan below for the goal. Be specific and harsh. If the plan is genuinely complete and "
    "correct, reply with exactly: SUFFICIENT.\n\nGOAL:\n{goal}\n\nPLAN:\n{plan}")
_REFINE = (
    "Revise the plan to fix this gap. Keep what's good, address the gap concretely, and stay specific.\n\n"
    "GOAL:\n{goal}\n\nCURRENT PLAN:\n{plan}\n\nGAP TO FIX:\n{gap}{research}")
_SEED = (
    "Produce a comprehensive, specific plan for the goal. Concrete step-by-step workflow, risks + "
    "mitigations, and what to verify.\n\nGOAL:\n{goal}{research}")


@dataclass
class Deliberation:
    goal: str
    plan: str = ""
    rounds_used: int = 0
    converged: bool = False           # True if the critic said SUFFICIENT
    gaps: list = field(default_factory=list)
    trail: list = field(default_factory=list)


def deliberate(goal: str, *, reason, critique=None, research=None, rounds: int = 3) -> Deliberation:
    """reason(prompt)->str produces/refines; critique(prompt)->str reviews (defaults to reason —
    but pass a SECOND model for a true maker≠checker split); research(query)->str is optional
    (six-source context). All injectable for tests."""
    critique = critique or reason
    d = Deliberation(goal=goal)

    seed_ctx = ""
    if research is not None:
        try:
            ctx = (research(goal) or "").strip()
            if ctx:
                seed_ctx = f"\n\nRESEARCHED CONTEXT (current, cited):\n{ctx[:2000]}"
                d.trail.append("research:seed")
        except Exception:
            d.trail.append("research:skip")

    d.plan = reason(_SEED.format(goal=goal, research=seed_ctx)).strip()
    d.trail.append("reason:seed")

    for i in range(max(1, rounds)):
        d.rounds_used = i + 1
        gap = critique(_CRITIQUE.format(goal=goal, plan=d.plan)).strip()
        if re.match(r"\s*SUFFICIENT\b", gap, re.I):
            d.converged = True
            d.trail.append(f"critique[{i+1}]:SUFFICIENT")
            break
        d.gaps.append(gap[:200])
        d.trail.append(f"critique[{i+1}]:gap")
        rblock = ""
        if research is not None:
            try:
                more = (research(gap[:120]) or "").strip()
                if more:
                    rblock = f"\n\nRESEARCH ON THE GAP:\n{more[:1500]}"
                    d.trail.append(f"research[{i+1}]:gap")
            except Exception:
                pass
        d.plan = reason(_REFINE.format(goal=goal, plan=d.plan, gap=gap, research=rblock)).strip()
        d.trail.append(f"reason[{i+1}]:refined")
    return d


def _cli(argv: list) -> int:
    goal = " ".join(a for a in argv if not a.startswith("--"))
    if not goal:
        print('usage: verity deliberate "<goal>" [--rounds N] [--no-web]', file=sys.stderr); return 2
    rounds = 3
    if "--rounds" in argv:
        try: rounds = int(argv[argv.index("--rounds") + 1])
        except Exception: pass
    from .router import ask as _ask
    reason = lambda p: _ask(p).text
    research = None
    if "--no-web" not in argv:
        from .websearch import deep_research
        research = lambda q: deep_research(q, ask=reason, rounds=1, sources=True)["context"]
    d = deliberate(goal, reason=reason, research=research, rounds=rounds)
    status = "converged (critic: SUFFICIENT)" if d.converged else f"max {d.rounds_used} rounds"
    print(f"# Deliberated plan — {status}\n# trail: {' → '.join(d.trail)}\n")
    print(d.plan)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

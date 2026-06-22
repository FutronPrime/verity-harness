#!/usr/bin/env python3
"""Strategy DISCOVERY — evolutionary search over coordination strategies (Gap #4's 'discover' half).

The correction that built this (The Architect, 2026-06-22): claiming "only weight-training can discover
strategies outside the model's priors" is a defeatist NEGATIVE — the exact assumption VERITY exists to
kill. Discovery does NOT require fine-tuning. It requires a SEARCH LOOP wrapped around a frozen model:
the model proposes/mutates candidate strategies, a real evaluator scores them, selection keeps winners,
and the loop explores combinations no single forward pass would ever pick. The optimization lives in the
outer loop, not the weights. This is a published, named field with frozen base models:
  • ADAS — Automated Design of Agentic Systems (arXiv 2408.08435): meta-agent searches CODE space,
    "invents novel design patterns" around frozen models, no fine-tuning.
  • FunSearch (Nature 2023) / AlphaEvolve (DeepMind 2025): frozen LLM as the variation operator in an
    evolutionary algorithm + evaluator → discovered genuinely new algorithms.
  • AFlow (arXiv 2410.10762) / GPTSwarm / EvoAgentX: MCTS / policy-gradient search over agent topologies.

This module is a focused version of that, REUSING evolve.py's proven pattern (candidate archive +
dual-gate promotion + held-out eval). It evolves a population of COORDINATION STRATEGIES — reusable
decomposition/topology templates (AFlow calls them "operators") — that the orchestrator injects to shape
how it decomposes a goal. The frozen swarm is the variation operator; an evaluator scores candidates on
real tasks; winners are archived and promoted into the strategy bank that promptos/coordinate inject.

HONEST about cost (like AlphaEvolve needs its evaluator): the MECHANISM is here and unit-tested no-API,
but real DISCOVERY requires running candidates against a real task suite (costs API/compute) — that's
the `--eval` path. Without an evaluator it can still seed/propose/archive, but it isn't *discovering*
until something measures the candidates. We don't pretend otherwise.

  python3 -m verity discover            # show the current strategy bank (champion + seeds)
  python3 -m verity discover --propose  # frozen model mutates a new candidate strategy (no eval)
  python3 -m verity discover --eval --apply   # full loop: propose → evaluate on tasks → gate → promote
"""
from __future__ import annotations

import json
import os
import pathlib
import time

BANK = pathlib.Path(os.path.expanduser("~/.verity-harness/strategies.json"))
ARCHIVE = pathlib.Path(os.path.expanduser("~/.verity-harness/discover"))
MAX_TEMPLATE = 600        # a strategy is a compact directive, not an essay


# ── Seed population — real AFlow-style operators (the stepping stones discovery recombines) ──
SEED_STRATEGIES: list[dict] = [
    {"name": "flat-fanout", "score": None,
     "template": "Decompose into independent sub-tasks that each fully stand alone (depends_on:[]); "
                 "a final synthesis node combines them. Best for breadth (survey/compare/gather)."},
    {"name": "review-revise", "score": None,
     "template": "Use a REVIEW→REVISE chain: a solver node produces the work, a reviewer node "
                 "(depends_on the solver) critiques it, a reviser node (depends_on the review) "
                 "applies fixes. Best when correctness matters more than breadth."},
    {"name": "debate-adjudicate", "score": None,
     "template": "Use DEBATE: spawn 2 independent solver nodes that approach the goal differently "
                 "(depends_on:[]), plus an adjudicator node (depends_on both) that reconciles them "
                 "into the strongest answer. Best for ambiguous or contested problems."},
    {"name": "isolate-recurse", "score": None,
     "template": "ISOLATE the single hardest core as its own node scored complexity 9 (so it recurses "
                 "into a fresh sub-swarm), and keep the surrounding nodes trivial. Best when one part "
                 "is far harder than the rest — don't waste a flat pass on it."},
]


def _load_bank() -> dict:
    try:
        d = json.loads(BANK.read_text())
        if isinstance(d, dict) and d.get("population"):
            return d
    except Exception:  # noqa: BLE001
        pass
    return {"champion": None, "population": [dict(s) for s in SEED_STRATEGIES], "cycle": 0}


def _save_bank(bank: dict) -> None:
    try:
        BANK.parent.mkdir(parents=True, exist_ok=True)
        BANK.write_text(json.dumps(bank, indent=2))
    except OSError:
        pass


def active_strategy() -> str:
    """The promoted champion strategy template to inject into the orchestrator (empty if none yet).
    Bounded; never raises. This is the discovery counterpart to coordinate.learned_routing()."""
    try:
        bank = _load_bank()
        champ = bank.get("champion")
        if champ and champ.get("template"):
            return ("[VERITY DISCOVERED STRATEGY — evolved + evaluated as the best decomposition shape "
                    f"for your workloads]\nSTRATEGY '{champ['name']}': {champ['template'][:MAX_TEMPLATE]}")
    except Exception:  # noqa: BLE001
        pass
    return ""


def _propose(bank: dict, tiers=None) -> dict | None:
    """VARIATION OPERATOR: the frozen model mutates/recombines the current population into a NEW candidate
    strategy. This is where a strategy 'outside the one-shot guess' comes from — it's a recombination the
    search proposes, then the evaluator (not the model's confidence) decides if it's actually better."""
    from .router import ask
    pop = bank.get("population", [])
    roster = "\n".join(f"- {s['name']}: {s['template']}" for s in pop[-6:])
    sysp = ("You design COORDINATION STRATEGIES for a multi-agent swarm — reusable decomposition/topology "
            "templates (like AFlow operators). Given the existing population, invent ONE NEW strategy that "
            "RECOMBINES or MUTATES their strengths into a coordination pattern not already present (e.g. "
            "mix debate with review, add a verification fan-in, stage research before solving). It must be "
            "a concrete decomposition+dependency directive an orchestrator can follow. "
            'Respond ONLY JSON: {"name":"kebab-name","template":"<the directive, <600 chars>"}')
    try:
        r = ask(f"EXISTING POPULATION:\n{roster}\n\nInvent one new, distinct strategy.",
                system=sysp, **({"tiers": tiers} if tiers else {}))
        from .loop import parse_step_json
        cand = parse_step_json(r.text if hasattr(r, "text") else str(r))
        name = str(cand.get("name", "")).strip()[:40]
        tmpl = str(cand.get("template", "")).strip()[:MAX_TEMPLATE]
        if name and len(tmpl) > 20 and not any(s["name"] == name for s in pop):
            return {"name": name, "score": None, "template": tmpl}
    except Exception:  # noqa: BLE001
        pass
    return None


def _eval_task_count() -> int:
    """How many benchmark tasks per strategy eval. Bounded (default 2) to keep a live --eval affordable;
    raise VERITY_DISCOVER_EVAL_TASKS for a stronger (costlier) signal."""
    try:
        return max(1, int(os.environ.get("VERITY_DISCOVER_EVAL_TASKS", "2")))
    except ValueError:
        return 2


# Representative coordination-sensitive goals — a strategy is good if it produces sound decompositions
# for these. Used by the FAST evaluator (no execution), the practical default.
_EVAL_GOALS = [
    "Research three competing open-source approaches to rate-limiting an API, compare them on "
    "throughput, memory, and failure behavior, and recommend one with justification.",
    "Migrate a Python service's auth from sessions to JWT: plan the steps, isolate the risky token-"
    "rotation part, and verify nothing breaks.",
]


def _fast_plan_evaluator(template: str, tiers=None) -> float:
    """DEFAULT evaluator — FAST (seconds, not minutes). It scores a strategy by the QUALITY of the
    DECOMPOSITIONS it produces (which is exactly what a coordination strategy affects), WITHOUT running
    the full multi-step tasks. Per representative goal: planner emits a plan with the strategy injected,
    then a critic rates it 0-10. Score = structural-validity ⊕ critic rating, averaged. This is what
    makes `discover --eval` usable — the task-completion evaluator (opt-in) took minutes/strategy and
    timed out. Honest: a plan-quality proxy, not end-to-end completion; set VERITY_DISCOVER_EVAL_MODE=tasks
    for the rigorous (slow) signal."""
    from .router import ask
    from .loop import parse_step_json
    from . import complexity as _cx
    scores = []
    for goal in _EVAL_GOALS:
        try:
            plan_sys = ("You are a multi-agent PLANNER. Decompose the GOAL into 2-5 sub-tasks with "
                        "id/complexity(1-10)/type/depends_on, applying the STRATEGY. Respond ONLY JSON: "
                        '{"subtasks":[{"id":"1","task":"...","complexity":5,"type":"code","depends_on":[]}]}')
            pr = ask(f"STRATEGY:\n{template}\n\nGOAL: {goal}", system=plan_sys,
                     **({"tiers": tiers} if tiers else {}))
            plan = parse_step_json(pr.text if hasattr(pr, "text") else str(pr))
            nodes = _cx.normalize_subtasks(plan.get("subtasks") or [])
            structural = 1.0 if (2 <= len(nodes) <= 5 and any(n["depends_on"] for n in nodes) or len(nodes) >= 2) else 0.3
            crit_sys = ("Rate this decomposition for the goal 0-10 (coverage, right-sized sub-tasks, "
                        "sensible dependencies, no redundancy). Respond ONLY JSON: {\"score\": <0-10>}.")
            cr = ask(f"GOAL: {goal}\n\nDECOMPOSITION:\n" +
                     "\n".join(f"- [{n['complexity']}] {n['task']} deps={n['depends_on']}" for n in nodes),
                     system=crit_sys, **({"tiers": tiers} if tiers else {}))
            cj = parse_step_json(cr.text if hasattr(cr, "text") else str(cr))
            rating = float(cj.get("score", 5)) / 10.0
            scores.append(0.3 * structural + 0.7 * max(0.0, min(1.0, rating)))
        except Exception:  # noqa: BLE001
            scores.append(0.0)
    return sum(scores) / max(1, len(scores))


def _default_evaluator(template: str, tiers=None) -> float:
    """Dispatch: FAST plan-coherence (default, usable) vs rigorous task-completion (opt-in, slow).
    VERITY_DISCOVER_EVAL_MODE=tasks selects the latter."""
    if os.environ.get("VERITY_DISCOVER_EVAL_MODE", "plan").lower().startswith("task"):
        return _task_evaluator(template, tiers)
    return _fast_plan_evaluator(template, tiers)


def _task_evaluator(template: str, tiers=None) -> float:
    """SELECTION PRESSURE: score a strategy by running the GAIA-shape task benchmark THROUGH THE SWARM
    with this candidate strategy injected (VERITY_STRATEGY_INJECT → the swarm planner reads it), and
    measuring goal completion. This is the REAL discovery signal — a candidate is adopted only if it
    MEASURES better, never on the model's say-so. Costs API (like AlphaEvolve's evaluator); bounded by
    VERITY_DISCOVER_EVAL_TASKS. Returns fraction of tasks the swarm completed under this strategy."""
    from . import eval_tasks
    prev = os.environ.get("VERITY_STRATEGY_INJECT")
    os.environ["VERITY_STRATEGY_INJECT"] = template
    try:
        res = eval_tasks.run(tiers=tiers, use_swarm=True, verbose=False,
                             tasks=eval_tasks.TASKS[:_eval_task_count()])
        return res.get("harness", 0) / max(1, res.get("tasks", 1))
    except Exception:  # noqa: BLE001
        return 0.0
    finally:
        if prev is None:
            os.environ.pop("VERITY_STRATEGY_INJECT", None)
        else:
            os.environ["VERITY_STRATEGY_INJECT"] = prev


def _git(*a):
    import subprocess
    return subprocess.run(["git", *a], cwd=ARCHIVE, capture_output=True, text=True)


def _archive(bank: dict, note: str) -> None:
    """git-tagged candidate archive (rollback-without-erasure), mirroring evolve.py's proven pattern."""
    try:
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        if not (ARCHIVE / ".git").is_dir():
            _git("init", "-b", "main"); _git("config", "user.email", "verity@futron")
            _git("config", "user.name", "verity-discover")
        (ARCHIVE / "strategies.json").write_text(json.dumps(bank, indent=2))
        _git("add", "-A"); _git("commit", "--allow-empty", "-m", f"discover-{bank['cycle']}: {note}")
        _git("tag", "-f", f"discover-{bank['cycle']}")
    except Exception:  # noqa: BLE001
        pass


def discover(propose: bool = True, use_eval: bool = False, apply: bool = False,
             tiers=None, evaluator=None, proposer=None) -> dict:
    """One discovery cycle. `evaluator`/`proposer` are injectable (tests pass stubs; prod uses the frozen
    model + real task eval). Returns a verdict dict. SELECTION is by MEASURED fitness, never model opinion —
    a candidate is promoted only if it beats the champion on the evaluator."""
    bank = _load_bank()
    bank["cycle"] = bank.get("cycle", 0) + 1
    result = {"cycle": bank["cycle"], "proposed": None, "promoted": False}

    cand = None
    if propose:
        cand = (proposer or _propose)(bank, tiers)
        if cand:
            result["proposed"] = cand["name"]
            bank["population"].append(cand)

    if use_eval:
        ev = evaluator or _default_evaluator
        champ = bank.get("champion")
        champ_score = champ.get("score") if champ else None
        if champ_score is None and champ:
            champ_score = ev(champ["template"], tiers)
            champ["score"] = champ_score
        # score the unscored candidates (the new one, and any seed never measured)
        for s in bank["population"]:
            if s.get("score") is None:
                s["score"] = ev(s["template"], tiers)
        best = max(bank["population"], key=lambda s: s.get("score") or 0.0)
        result["best"] = {"name": best["name"], "score": best.get("score")}
        # adopt only a MEASURED improvement (dual-gate spirit: never overwrite champion on a vibe)
        if best.get("score") is not None and (champ_score is None or best["score"] > champ_score):
            if apply:
                bank["champion"] = dict(best)
                _archive(bank, f"promote {best['name']} (score {best['score']:.3f})")
                result["promoted"] = True
            result["new_champion"] = best["name"]

    _save_bank(bank)
    result["population_size"] = len(bank["population"])
    return result


if __name__ == "__main__":
    import sys
    if "--eval" in sys.argv:
        r = discover(propose="--no-propose" not in sys.argv, use_eval=True, apply="--apply" in sys.argv)
        print(json.dumps(r, indent=2))
    elif "--propose" in sys.argv:
        r = discover(propose=True, use_eval=False, apply=False)
        print(json.dumps(r, indent=2))
    else:
        bank = _load_bank()
        champ = bank.get("champion")
        print(f"strategy bank — {len(bank['population'])} strategies, cycle {bank.get('cycle',0)}")
        print(f"champion: {champ['name'] if champ else '(none yet — run --eval --apply to discover one)'}")
        for s in bank["population"]:
            sc = f"  [score {s['score']:.3f}]" if s.get("score") is not None else ""
            print(f"  · {s['name']}{sc}")

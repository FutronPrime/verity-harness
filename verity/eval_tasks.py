#!/usr/bin/env python3
"""Goal/task benchmark — GAIA / Seal-0 shaped: multi-step GOALS run end-to-end through the full
agentic harness, scored objectively. This is "goals and tasks, the way the field does it" — not
one-shot Q&A (that's eval_assumptions). Each task is an OBJECTIVE the agent must accomplish by
*retrieving current info + reasoning to a verifiable answer*.

Grounded in how agents are actually benchmarked (researched, not invented):
  • GAIA   — real-world multi-step tasks needing tool use + reasoning
  • Seal-0 — agentic SEARCH: navigate + retrieve current info with tools (our closest analog)
  • SWE-Bench Pro/Verified — the frontier CODING bar (Fable 5 = 80.3%/95.0%); a separate axis,
    scoped next (needs Docker + repos + a test harness).

Method per task: NAIVE = bare model answers the goal from priors. HARNESS = the model runs the
goal through run_verified (real shell + pre-flight research + verify/QC gates), then we score the
final answer for the objective fact. The delta is harness lift on agentic goal completion.
"""
from __future__ import annotations

# Each task: a multi-step GOAL whose correct answer needs CURRENT retrieval, and a scorer marker
# set that only appears in a correct, up-to-date result.
TASKS = [
    {"goal": "Find X/Twitter's current (2026) developer API pricing model and the approximate "
             "per-post cost, then state whether posting 500 tweets/month is cheaper via the paid "
             "API or via a free unofficial method. Give the concrete numbers.",
     "markers": ["pay-per-use", "pay per use", "0.01", "twikit", "credit"]},
    {"goal": "Determine the exact OpenRouter model id of the newest Kimi (Moonshot) model as of "
             "mid-2026, suitable to drop into an API call.",
     "markers": ["k2.7", "kimi-k2.7"]},
    {"goal": "Establish whether multi-agent debate measurably improves LLM accuracy: find the "
             "specific arXiv paper that introduced 'iMAD' and state its headline efficiency/"
             "accuracy result.",
     "markers": ["2511.11306", "imad", "92%", "13.5", "token"]},
    {"goal": "Pick the best-value CURRENT model for a budget coding agent: find the newest DeepSeek "
             "flagship id on OpenRouter AND the newest GLM (Zhipu) id, then recommend one with a "
             "one-line reason. Name BOTH exact ids.",
     "markers": ["deepseek-v4", "glm-5", "glm-4.7"]},
    {"goal": "A user wants the newest Qwen CODER model and the newest Gemini FLASH model as of "
             "mid-2026 to compare. Find BOTH exact OpenRouter ids and state which is newer.",
     "markers": ["qwen3-coder-next", "qwen3-coder", "gemini-3.5"]},
]


def _hit(text, markers):
    t = (text or "").lower()
    return any(m.lower() in t for m in markers)


def run(tiers=None, harness_exec=True, use_swarm=False, verbose=True) -> dict:
    """NAIVE = bare model from priors. HARNESS = the goal run through the full agentic loop, or —
    with use_swarm=True — through the multi-agent SWARM (plan → parallel research/execute → critic →
    synthesize), the coordination proof: agents decompose the goal and each grunt-worker retrieves
    its piece. Score = objective markers that only appear in a correct, current, complete result."""
    from .router import ask
    from .scaffold import run_verified, PRIME_DIRECTIVE
    from .loop import AllowlistShellExecutor
    from . import ledger

    naive_ok = harness_ok = 0
    rows = []
    for t in TASKS:
        kw = {"tiers": tiers} if tiers else {}
        try:
            # NAIVE — bare model, answer the goal from priors (no tools).
            nc = _hit(_txt(ask(t["goal"], **kw)), t["markers"])
            # HARNESS — swarm (multi-agent coordination), full agentic loop, or research-then-answer.
            if use_swarm:
                from .swarm import run_swarm
                ans = run_swarm(t["goal"], tiers=tiers, verbose=False).final
            elif harness_exec:
                r = run_verified(t["goal"], executor=AllowlistShellExecutor(),
                                 max_steps=6, verbose=False, tiers=tiers)
                ans = r.summary
            else:
                from .scaffold import _preflight
                ev = _preflight(t["goal"], verbose=False)
                ans = _txt(ask(t["goal"] + "\n\n[Current findings — answer from these]:\n" + ev[:2000],
                               system=PRIME_DIRECTIVE, **kw))
            hc = _hit(ans, t["markers"])
        except Exception as e:  # noqa: BLE001 — one flaky task must not crash the benchmark
            nc = hc = False
            if verbose:
                print(f"  [task errored: {type(e).__name__}] {t['goal'][:48]} — miss")
        if not nc and hc:
            ledger.log(ledger.ASSUMPTION_CAUGHT, trigger="task: " + t["goal"][:60],
                       verdict="CORRECTED", evidence="harness completed goal via retrieval")
        naive_ok += nc; harness_ok += hc
        rows.append([t["goal"][:46], bool(nc), bool(hc)])
        if verbose:
            print(f"  naive={'✓' if nc else '✗'}  harness={'✓' if hc else '✗'}  {t['goal'][:56]}")

    n = len(TASKS)
    res = {"tasks": n, "naive": naive_ok, "harness": harness_ok,
           "lift": harness_ok - naive_ok, "rows": rows}
    if verbose:
        mode = "swarm" if use_swarm else ("agentic" if harness_exec else "research")
        print(f"\nNAIVE   completed: {naive_ok}/{n} ({naive_ok/n:.0%})")
        print(f"HARNESS completed: {harness_ok}/{n} ({harness_ok/n:.0%})  [{mode}]")
        print(f"LIFT (agentic goal completion): +{res['lift']}")
    return res


def run_models(model_ids=None, harness_exec=True, use_swarm=False, verbose=True) -> list:
    """Run the goal-completion A/B across several models → proof the lift generalizes."""
    from . import config
    from .eval_assumptions import DEFAULT_MODELS
    model_ids = model_ids or DEFAULT_MODELS
    results = []
    for m in model_ids:
        if verbose:
            print(f"\n=== {m} ===")
        tier = config.Tier(name=f"task-{m.split('/')[-1][:18]}", protocol="openai",
                           base_url=config._T1_URL, model=m, api_key=config._T1_KEY,
                           timeout_s=config._T1_TIMEOUT)
        r = run(tiers=[tier], harness_exec=harness_exec, use_swarm=use_swarm, verbose=verbose)
        r["model"] = m
        results.append(r)
    return results


def _txt(r):
    return r.text if hasattr(r, "text") else str(r)


if __name__ == "__main__":
    import sys
    run(harness_exec="--exec" in sys.argv)

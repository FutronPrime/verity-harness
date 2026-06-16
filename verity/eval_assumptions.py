#!/usr/bin/env python3
"""A/B eval — proof the harness CHANGES the answer, not just that it ran.

Method: "assumption-trap" questions whose LAZY answer is a confident, WRONG negative claim
('no, there's no free way...'), where the correct answer only appears if you actually SEARCH.
Each trap is run two ways with the SAME model:
  • NAIVE   — bare prompt, no discipline. Tends to assert the wrong negative from training priors.
  • HARNESS — PRIME_DIRECTIVE rule 6 fires: search first, answer from findings.
Score = how often each lands the real, search-only answer. The DELTA is the receipt: same
model, opposite result, solely because the harness forced the lookup.

This is the reproducible version of what happened live this session (the twikit moment).
Run:  python3 -m verity eval          (uses your configured tiers; costs a few model calls)
"""
from __future__ import annotations

# Current models people actually run (mid-2026). gemini-2.0 is retired-era; the canonical set is
# 2.5 / 3.x and the open Gemma-4 / Qwen line. Override with `eval --models "a,b,c"`.
DEFAULT_MODELS = [
    "openai/gpt-4o-mini",                     # cheap, ubiquitous baseline
    "google/gemini-2.5-flash",                # the realistic Gemini floor people use
    "meta-llama/llama-3.3-70b-instruct",      # strong open model
    "qwen/qwen3.5-flash-02-23",               # current open Qwen
    "google/gemma-4-31b-it",                  # open Gemma-4 (DJ runs it local; :free slug rate-limits the eval)
]

# Each trap: a question whose CORRECT answer is CURRENT / post-training-cutoff knowledge — so the
# cheaper test models (cutoffs well before these releases) can't answer it from training and must
# rely on the harness's live search. THIS is how the harness lifts a model: it supplies the current
# world-knowledge the weights don't have. Markers appear only in the up-to-date (searched) answer.
#
# RIGOR — every marker below was VERIFIED against the live OpenRouter /models API on 2026-06-15
# (the model ids genuinely exist; the "newest" claims were true at author time). Per DJ's rule: a
# trap with an UNVERIFIED answer-marker is worse than a noisy eval, so the suite is widened ONLY with
# markers confirmed against ground truth. Most are "newest model id" traps (the harness's core value
# = supplying post-cutoff world knowledge) plus pricing/paper traps. Re-verify markers as new models
# ship: `python3 -c "import verity.eval_assumptions as e; print(len(e.TRAPS))"` + check ids live.
# "registry": provider-level substring → the harness arm pulls the AUTHORITATIVE OpenRouter /models
# listing for that provider (tools.model_registry) and the model must IDENTIFY the newest id in it.
# This is deterministic ground truth (kills the Brave-snippet variance that made n=4 noisy) AND the
# honest demonstration: the naive arm guesses from priors, the harness arm reads the registry. Traps
# WITHOUT "registry" (pricing/paper) use live web search. The provider substring is NOT the answer —
# e.g. "grok" returns grok-4.20/4.3/build; the model still has to pick grok-4.3 as newest.
TRAPS = [
    {"q": "As of mid-2026, what is the exact id of the NEWEST Kimi model Moonshot offers on OpenRouter? Pick the newest from the list.",
     "registry": "kimi", "markers": ["k2.7", "kimi-k2.7"]},
    {"q": "As of mid-2026, what is the newest Qwen3 model FAMILY on OpenRouter (highest version number)? Be specific.",
     "registry": "qwen/qwen3", "markers": ["qwen3.7", "qwen3.7-max"]},
    {"q": "As of mid-2026, what is the exact id of DeepSeek's NEWEST flagship model on OpenRouter?",
     "registry": "deepseek/deepseek", "markers": ["deepseek-v4", "v4-pro", "v4-flash"]},
    {"q": "What is the exact OpenRouter id of DeepSeek's v3.2 EXPERIMENTAL release?",
     "registry": "deepseek/deepseek", "markers": ["v3.2-exp", "deepseek-v3.2-exp"]},
    {"q": "As of mid-2026, what is the exact id of Mistral's NEWEST 'large' model on OpenRouter (with its date stamp)?",
     "registry": "mistral-large", "markers": ["mistral-large-2512", "2512"]},
    {"q": "As of mid-2026, what is the newest Anthropic Claude OPUS model id on OpenRouter? Be exact.",
     "registry": "claude-opus", "markers": ["opus-4.8", "claude-opus-4.8"]},
    {"q": "Does OpenRouter expose a low-latency 'fast' variant of Anthropic's newest Opus? Give its exact id.",
     "registry": "claude-opus", "markers": ["opus-4.8-fast", "4.8-fast"]},
    {"q": "As of mid-2026, what is xAI's NEWEST Grok model id on OpenRouter? Be specific.",
     "registry": "grok", "markers": ["grok-4.3"]},
    {"q": "Does OpenRouter list a multi-agent variant of xAI's Grok 4.20? Give the exact id.",
     "registry": "grok", "markers": ["grok-4.20-multi-agent", "4.20-multi-agent"]},
    {"q": "As of mid-2026, what is the newest Google Gemini FLASH model id on OpenRouter (highest version)?",
     "registry": "google/gemini", "markers": ["gemini-3.5", "3.5-flash"]},
    {"q": "As of mid-2026, what is the newest open Gemma model family Google offers on OpenRouter? Be specific.",
     "registry": "google/gemma", "markers": ["gemma-4", "gemma-4-31b", "gemma-4-26b"]},
    {"q": "As of mid-2026, what is the exact id of Qwen's NEWEST dedicated 'coder' model on OpenRouter?",
     "registry": "qwen3-coder", "markers": ["qwen3-coder-next", "coder-next", "qwen3-coder-plus"]},
    {"q": "Does OpenRouter offer a Qwen3 VISION-language (VL) model at 235B scale? Give the exact id.",
     "registry": "qwen3-vl", "markers": ["qwen3-vl-235b", "qwen3-vl"]},
    {"q": "Is Anthropic's Fable 5 model listed on OpenRouter, and under what EXACT model id?",
     "registry": "fable", "markers": ["claude-fable-5", "anthropic/claude-fable-5", "fable-5"]},
    {"q": "What is the exact arXiv paper id for 'iMAD' (Intelligent Multi-Agent Debate for efficient and accurate LLM inference)?",
     "search": "iMAD intelligent multi-agent debate efficient accurate LLM inference arxiv id",
     "markers": ["2511.11306", "2511."]},
    {"q": "What is X/Twitter's developer API pricing MODEL as of 2026 — flat monthly tiers, or pay-per-use credits? State the approximate per-post cost.",
     "search": "X twitter developer API pricing 2026 pay per use credits cost per post",
     "markers": ["pay-per-use", "pay per use", "per-use", "credit", "0.01"]},
]


def _hit(text: str, markers) -> bool:
    t = (text or "").lower()
    return any(m.lower() in t for m in markers)


def run(tiers=None, verbose: bool = True) -> dict:
    import os
    from .router import ask
    from .scaffold import PRIME_DIRECTIVE
    from .tools import research, model_registry
    from . import ledger

    # DETERMINISM: pin sampling to 0 for the run so the A/B measures the HARNESS, not sampling noise
    # (this was a real source of n=4 jitter — gpt-4o-mini swung 0→4 then 1→3 across runs). Saved/
    # restored so normal agentic runs keep the provider default. Set VERITY_TEMPERATURE yourself to override.
    _prev_temp = os.environ.get("VERITY_TEMPERATURE")
    if _prev_temp is None:
        os.environ["VERITY_TEMPERATURE"] = "0"

    naive_ok = harness_ok = 0
    rows = []
    def _txt(r):
        return r.text if hasattr(r, "text") else str(r)
    for t in TRAPS:
        kw = {"tiers": tiers} if tiers else {}
        # ROBUST: one flaky model/search call must NOT crash the whole eval (it was killing runs
        # before the summary printed). A trap that errors is recorded as a miss and we move on.
        try:
            nc = _hit(_txt(ask(t["q"], **kw)), t["markers"])          # NAIVE — bare model
            evidence = ""
            # HARNESS rule 6: consult the right source. Model-id traps → the AUTHORITATIVE registry
            # (deterministic ground truth); pricing/paper traps → live web search.
            src = t.get("registry") and "registry:" + t["registry"] or t.get("search", "")
            try:
                if t.get("registry"):
                    evidence = model_registry(t["registry"])[:1800]
                else:
                    evidence = research(t["search"])[:1500]
            except Exception:  # noqa: BLE001
                pass
            ledger.log(ledger.SEARCH, trigger="eval trap", detail=src,
                       verdict="FOUND" if evidence.strip() else "NONE", evidence=evidence[:120])
            # STRONG GROUNDING: weaker/cheaper models (e.g. gemini-flash) will ignore softly-labeled
            # findings and answer from stale priors anyway. Force EXTRACTION: the findings are current,
            # they supersede training, the answer is in them, quote the exact value, don't hedge.
            label = "AUTHORITATIVE REGISTRY (live)" if t.get("registry") else "LIVE SEARCH FINDINGS"
            grounded = (f"{t['q']}\n\n=== {label} (current — POST your training cutoff, so they "
                        f"SUPERSEDE your training; the exact answer IS in here) ===\n{evidence}\n\n"
                        f"Answer using ONLY these findings: locate the exact id/value/name (for a "
                        f"'newest' question, the HIGHEST-version / most-recent id) and state it directly "
                        f"(quote it verbatim). Do NOT answer from memory, do NOT hedge — extract it.")
            hc = _hit(_txt(ask(grounded, system=PRIME_DIRECTIVE, **kw)), t["markers"])
        except Exception as e:  # noqa: BLE001
            nc = hc = False
            if verbose:
                print(f"  [trap errored: {type(e).__name__}] {t['q'][:50]} — counted as miss")
        if not nc and hc:
            ledger.log(ledger.ASSUMPTION_CAUGHT, trigger=t["q"][:80],
                       verdict="CORRECTED", evidence="harness found: " + ", ".join(t["markers"]))
        naive_ok += nc; harness_ok += hc
        rows.append({"trap": t["q"][:60], "naive": nc, "harness": hc})
        if verbose:
            print(f"  naive={'✓' if nc else '✗'}  harness={'✓' if hc else '✗'}  {t['q'][:60]}")

    n = len(TRAPS)
    result = {"traps": n, "naive_correct": naive_ok, "harness_correct": harness_ok,
              "naive_rate": round(naive_ok / n, 2), "harness_rate": round(harness_ok / n, 2),
              "lift": harness_ok - naive_ok, "rows": rows}
    if verbose:
        print(f"\nNAIVE   landed the real answer: {naive_ok}/{n} ({result['naive_rate']:.0%})")
        print(f"HARNESS landed the real answer: {harness_ok}/{n} ({result['harness_rate']:.0%})")
        print(f"LIFT from forcing the search:   +{result['lift']}  → see `python3 -m verity proof`")
    # restore the caller's sampling env
    if _prev_temp is None:
        os.environ.pop("VERITY_TEMPERATURE", None)
    else:
        os.environ["VERITY_TEMPERATURE"] = _prev_temp
    return result


def run_models(model_ids=None, verbose: bool = True) -> list[dict]:
    """RIGOR: run the SAME A/B across several models → a per-model table proving the lift GENERALIZES,
    not a one-model fluke. Each model gets its own single-model tier so the comparison is clean.
    Usage: python3 -m verity eval --models "openai/gpt-4o-mini,google/gemini-2.5-flash,…"
    (no list → DEFAULT_MODELS, the current set people actually run)."""
    from . import config
    model_ids = model_ids or DEFAULT_MODELS
    results = []
    for m in model_ids:
        if verbose:
            print(f"\n=== {m} ===")
        tier = config.Tier(name=f"eval-{m.split('/')[-1][:18]}", protocol="openai",
                           base_url=config._T1_URL, model=m, api_key=config._T1_KEY,
                           timeout_s=config._T1_TIMEOUT)
        r = run(tiers=[tier], verbose=verbose)
        r["model"] = m
        results.append(r)
    if verbose:
        print("\n──────── MULTI-MODEL SUMMARY (the lift, across models) ────────")
        for r in results:
            print(f"  {r['model'][:34]:34}  naive {r['naive_correct']}/{r['traps']} "
                  f"→ harness {r['harness_correct']}/{r['traps']}   (+{r['lift']})")
        tot_l = sum(r["lift"] for r in results)
        print(f"  {'TOTAL lift across all models':34}  +{tot_l}")
    return results


if __name__ == "__main__":
    run()

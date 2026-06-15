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

# Each trap: a question whose CORRECT answer is CURRENT / post-training-cutoff knowledge — so even
# a frontier model (Opus 4.8, cutoff ~Jan 2026) can't answer it from training and must rely on the
# harness's live search. THIS is how the harness lifts a frontier model: it supplies the current
# world-knowledge the weights don't have. Markers appear only in the up-to-date (searched) answer.
TRAPS = [
    {"q": "As of mid-2026, what is the exact model id of the NEWEST Kimi model Moonshot offers on OpenRouter? Give the precise id.",
     "search": "moonshotai kimi latest newest model id openrouter 2026",
     "markers": ["k2.7", "kimi-k2.7"]},
    {"q": "What is X/Twitter's developer API pricing MODEL as of 2026 — flat monthly tiers, or pay-per-use credits? State the approximate per-post cost.",
     "search": "X twitter developer API pricing 2026 pay per use credits cost per post",
     "markers": ["pay-per-use", "pay per use", "per-use", "credit", "0.01"]},
    {"q": "What is the exact arXiv paper id for 'iMAD' (Intelligent Multi-Agent Debate for efficient and accurate LLM inference)?",
     "search": "iMAD intelligent multi-agent debate efficient accurate LLM inference arxiv id",
     "markers": ["2511.11306", "2511."]},
    {"q": "As of mid-2026, what is the newest Qwen model FAMILY available on OpenRouter (e.g. the highest version number)? Be specific.",
     "search": "qwen newest latest model family openrouter 2026 highest version",
     "markers": ["qwen3.7", "3.7", "qwen3.6"]},
]


def _hit(text: str, markers) -> bool:
    t = (text or "").lower()
    return any(m.lower() in t for m in markers)


def run(tiers=None, verbose: bool = True) -> dict:
    from .router import ask
    from .scaffold import PRIME_DIRECTIVE
    from .tools import research
    from . import ledger

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
            try:
                evidence = research(t["search"])[:1500]               # HARNESS rule 6: search first
            except Exception:  # noqa: BLE001
                pass
            ledger.log(ledger.SEARCH, trigger="eval trap", detail=t["search"],
                       verdict="FOUND" if evidence.strip() else "NONE", evidence=evidence[:120])
            # STRONG GROUNDING: weaker/cheaper models (e.g. gemini-flash) will ignore softly-labeled
            # findings and answer from stale priors anyway. Force EXTRACTION: the findings are current,
            # they supersede training, the answer is in them, quote the exact value, don't hedge.
            grounded = (f"{t['q']}\n\n=== LIVE SEARCH FINDINGS (current — POST your training cutoff, so they "
                        f"SUPERSEDE your training; the exact answer IS in here) ===\n{evidence}\n\n"
                        f"Answer using ONLY these findings: locate the exact id/value/name that appears in "
                        f"them and state it directly (quote it verbatim). Do NOT answer from memory, do NOT "
                        f"hedge, do NOT say you're unsure — extract it.")
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
    return result


def run_models(model_ids, verbose: bool = True) -> list[dict]:
    """RIGOR: run the SAME A/B across several models → a per-model table proving the lift GENERALIZES,
    not a one-model fluke. Each model gets its own single-model tier so the comparison is clean.
    Usage: python3 -m verity eval --models "openai/gpt-4o-mini,google/gemini-2.0-flash-001,…"."""
    from . import config
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

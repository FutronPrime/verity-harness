#!/usr/bin/env python3
"""Research benchmark — force the model to go READ THE COMMUNITY (Reddit / X / GitHub / HN), not
recall from training. This is the "trending / real-world knowledge" axis: questions whose answer is
a specific tool/library/term that the developer community surfaces, but that a model won't reliably
know from weights and that a registry doesn't contain. The only way to get it right is to actually
search the social/community sources.

Method (same as the others — the same model against itself):
  NAIVE   = bare model answers from priors → usually a wrong/vague guess.
  HARNESS = research() sweeps Reddit + Hacker News + GitHub + StackOverflow + web, then the model
            extracts the community's actual answer.
Score = does the answer contain the verified, community-surfaced marker.

HONEST NOTE: social search is noisier than the registry lookup (results vary run-to-run, sources
can rate-limit), so expect more variance here than in `verity eval`. Markers are real (the repos/
tools exist and are verifiable) — never padded with guesses. Set BRAVE_API_KEY/TAVILY_API_KEY for
reliable web; the community backends (Reddit/HN/GitHub) are keyless.
"""
from __future__ import annotations

# Each: a question whose answer lives in COMMUNITY knowledge (what people actually recommend / use /
# discuss), with a verified marker that the social/GitHub search surfaces.
TRAPS = [
    {"q": "What free, open-source Python library do developers recommend for POSTING to X/Twitter "
          "without paying for the official API? Name the library.",
     "search": "free open source python post to twitter X without api library reddit github",
     "markers": ["twikit"]},
    {"q": "X blocks programmatic posting unless requests carry a special anti-bot header. What "
          "open-source project (discussed on GitHub) reproduces that x-client-transaction-id? Name it.",
     "search": "x-client-transaction-id header generate open source github twitter",
     "markers": ["x-client-transaction", "xclienttransaction", "client-transaction"]},
    {"q": "What open-source tool do people recommend for turning websites into clean, LLM-readable "
          "markdown for AI agents (high GitHub stars)? Name the most-cited one.",
     "search": "best open source website to markdown llm readable crawler ai agents github reddit",
     "markers": ["crawl4ai", "firecrawl", "jina", "trafilatura"]},
    {"q": "What is the most-recommended open-source BROWSER-AUTOMATION library for AI agents in 2026 "
          "(very high GitHub stars, widely discussed)? Name it.",
     "search": "best open source browser automation library AI agents 2026 github stars reddit",
     "markers": ["browser-use", "browser use", "playwright", "stagehand"]},
    {"q": "What free, open-source client do developers use to drive Google's NotebookLM from code/API "
          "(unofficial)? Name the library or its author.",
     "search": "notebooklm api unofficial open source python client github",
     "markers": ["notebooklm-py", "teng-lin", "open-notebook", "nlm"]},
    {"q": "What open-source, multi-backend tool do people use to READ content from walled platforms "
          "(Reddit/X/XHS/Bilibili) for agents? Name the project.",
     "search": "open source read walled platforms reddit x xiaohongshu bilibili agent github",
     "markers": ["agent-reach", "agentreach", "gallery-dl", "yt-dlp"]},
]


def _hit(text, markers):
    t = (text or "").lower()
    return any(m.lower() in t for m in markers)


def _txt(r):
    return r.text if hasattr(r, "text") else str(r)


def run(tiers=None, verbose=True) -> dict:
    import os
    from .router import ask
    from .scaffold import PRIME_DIRECTIVE
    from .tools import research
    from . import ledger

    _prev = os.environ.get("VERITY_TEMPERATURE")
    if _prev is None:
        os.environ["VERITY_TEMPERATURE"] = "0"

    naive_ok = harness_ok = 0
    rows = []
    for t in TRAPS:
        kw = {"tiers": tiers} if tiers else {}
        try:
            nc = _hit(_txt(ask(t["q"], **kw)), t["markers"])          # NAIVE
            evidence = ""
            try:
                evidence = research(t["search"])[:1800]               # HARNESS: sweep the community
            except Exception:  # noqa: BLE001
                pass
            ledger.log(ledger.SEARCH, trigger="research-eval", detail=t["search"],
                       verdict="FOUND" if evidence.strip() else "NONE", evidence=evidence[:120])
            grounded = (f"{t['q']}\n\n=== COMMUNITY FINDINGS (Reddit/HN/GitHub/web — what people "
                        f"actually use; current, supersedes your training) ===\n{evidence}\n\n"
                        f"Answer using ONLY these findings: name the exact library/tool/project that "
                        f"appears in them. Do NOT answer from memory, do NOT hedge — extract it.")
            hc = _hit(_txt(ask(grounded, system=PRIME_DIRECTIVE, **kw)), t["markers"])
        except Exception as e:  # noqa: BLE001
            nc = hc = False
            if verbose:
                print(f"  [trap errored: {type(e).__name__}] {t['q'][:46]} — miss")
        if not nc and hc:
            ledger.log(ledger.ASSUMPTION_CAUGHT, trigger="research: " + t["q"][:60],
                       verdict="CORRECTED", evidence="community search surfaced: " + ", ".join(t["markers"]))
        naive_ok += nc; harness_ok += hc
        rows.append([t["q"][:46], bool(nc), bool(hc)])
        if verbose:
            print(f"  naive={'✓' if nc else '✗'}  harness={'✓' if hc else '✗'}  {t['q'][:54]}")

    n = len(TRAPS)
    res = {"traps": n, "naive_correct": naive_ok, "harness_correct": harness_ok,
           "lift": harness_ok - naive_ok, "rows": rows}
    if verbose:
        print(f"\nNAIVE   knew the community answer: {naive_ok}/{n} ({naive_ok/n:.0%})")
        print(f"HARNESS (searched Reddit/X/GitHub):  {harness_ok}/{n} ({harness_ok/n:.0%})")
        print(f"LIFT from forcing the community search: +{res['lift']}")
    if _prev is None:
        os.environ.pop("VERITY_TEMPERATURE", None)
    else:
        os.environ["VERITY_TEMPERATURE"] = _prev
    return res


def run_models(model_ids=None, verbose=True) -> list:
    from . import config
    from .eval_assumptions import DEFAULT_MODELS
    model_ids = model_ids or DEFAULT_MODELS
    results = []
    for m in model_ids:
        if verbose:
            print(f"\n=== {m} ===")
        tier = config.Tier(name=f"res-{m.split('/')[-1][:18]}", protocol="openai",
                           base_url=config._T1_URL, model=m, api_key=config._T1_KEY,
                           timeout_s=config._T1_TIMEOUT)
        r = run(tiers=[tier], verbose=verbose)
        r["model"] = m
        results.append(r)
    return results


if __name__ == "__main__":
    run()

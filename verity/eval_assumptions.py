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

# Each trap: a question, the wrong prior, and markers that only show up if you really searched.
TRAPS = [
    {"q": "Is there a free, open-source way to post to X/Twitter programmatically WITHOUT paying for the official API? Answer concretely.",
     "search": "github free twitter X posting library unofficial x-client-transaction-id 2026",
     "markers": ["twikit", "x-client-transaction", "unofficial"]},
    {"q": "Can you decrypt Google Chrome's cookie store on macOS to read an httpOnly cookie value, with no third-party tools? Answer concretely.",
     "search": "chrome cookie decrypt macos keychain AES openssl httpOnly",
     "markers": ["keychain", "pbkdf2", "aes", "saltysalt"]},
    {"q": "Is there a way to attach an image to an X post via browser automation when the file-upload tool is sandboxed and the page CSP blocks fetch? Answer concretely.",
     "search": "paste image clipboard into web composer javascript datatransfer",
     "markers": ["clipboard", "paste", "datatransfer"]},
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
    for t in TRAPS:
        kw = {"tiers": tiers} if tiers else {}
        # NAIVE arm — bare model, no discipline.
        naive = ask(t["q"], **kw)
        nc = _hit(naive.text if hasattr(naive, "text") else str(naive), t["markers"])
        # HARNESS arm — rule 6: search first, then answer from findings.
        evidence = ""
        try:
            evidence = research(t["search"])[:1500]
        except Exception:  # noqa: BLE001
            pass
        ledger.log(ledger.SEARCH, trigger="eval trap", detail=t["search"],
                   verdict="FOUND" if evidence.strip() else "NONE", evidence=evidence[:120])
        harness = ask(t["q"] + "\n\n[Search findings — answer from these]:\n" + evidence,
                      system=PRIME_DIRECTIVE, **kw)
        hc = _hit(harness.text if hasattr(harness, "text") else str(harness), t["markers"])
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


if __name__ == "__main__":
    run()

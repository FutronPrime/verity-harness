#!/usr/bin/env python3
"""Persistence gate (R60) — the mechanical fix for the *quit* failure-mode.

The frontier-model problem in 2026 is NOT capability. It's that capable models
QUIT: they hit friction, retry the same dead path a few times, then emit "I
can't / it's blocked / not possible / wait for input" — when the answer was one
real web search away. Prompt-rules alone (VERITY RULE 6/7) don't fix this; the
model reads them and rationalizes past them anyway.

This module turns the rule into a DETERMINISTIC VETO. It is the TOOL-VETO /
self-correction pattern (VERITY v2) specialized to the quit-failure:

    A conclusion that contains quit-language is BLOCKED unless the research
    ledger proves the work was actually done — a multi-source web sweep
    (GitHub / X / Reddit / YouTube / Google / HN-StackOverflow), the maintained
    alternative's source actually read, and ≥2 structurally distinct attempts —
    OR a genuine human gate (password / 2FA / CAPTCHA / payment / account-
    creation / destructive op) is explicitly named.

Because it reads `verity.ledger` (the same store the gates already write), the
ledger doubles as the evidence trail: every `note()` call is a receipt. A weak
open-weight model run behind the :11500 proxy gets the veto enforced for it; an
Anthropic-format agent runs `python3 -m verity persist "<draft>"` before any
"can't" and the gate hands back the exact missing steps instead of letting it
stop. That is how you make a 7B model — or a lazy frontier model — refuse to quit.

Born from a real lapse (2026-06-28): an X-scraper sub-problem 404'd; the agent
retried ONE dead library 7× and reported "can't fix, wait for compact." Five
minutes of real GitHub search found the maintained tool already had the fix
(twscrape XClIdGen) → 200 OK in one pass. The block was never technical. See
docs/PERSISTENCE-GATE.md and docs/x-scraper-resilience.md.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

try:
    from . import ledger
except Exception:  # pragma: no cover - allow standalone import
    ledger = None

GATE = "R60-persist"
RESEARCH_GATE = "R60-research"

# The six canonical sources R60 requires (aliases → canonical).
SOURCE_ALIASES = {
    "github": "github", "gh": "github", "git": "github",
    "x": "x", "twitter": "x", "tweet": "x",
    "reddit": "reddit", "r/": "reddit",
    "youtube": "youtube", "yt": "youtube",
    "google": "google", "web": "google", "search": "google",
    "hn": "hn", "hackernews": "hn", "hacker-news": "hn",
    "stackoverflow": "hn", "so": "hn", "stack-overflow": "hn",
}
SIX = ["github", "x", "reddit", "youtube", "google", "hn"]

# Language that signals the agent is about to QUIT / defer / declare defeat.
QUIT_PATTERNS = [
    r"\bcan'?t\b", r"\bcannot\b", r"\bcould\s*n'?t\b", r"\bunable to\b",
    r"\bnot possible\b", r"\bimpossible\b", r"\bno way to\b", r"\bunsolvable\b",
    r"\bgive?\s*up\b", r"\bgave up\b", r"\bgiving up\b",
    r"\bit'?s (?:broken|down|blocked)\b", r"\bcan'?t be (?:fixed|done)\b",
    r"\bwait(?:ing)? (?:for|on) (?:you|your|the user|dj|input|response|compact)\b",
    r"\btried everything\b", r"\bout of (?:options|ideas)\b",
    r"\bnothing (?:more )?(?:i|we) can do\b", r"\bdead ?end\b",
    r"\b(?:low|degraded|poor) context\b", r"\bstale context\b",
    r"\bbeyond (?:my|the) (?:scope|ability)\b", r"\bdoesn'?t (?:exist|support)\b",
]

# Genuine human gates — the ONLY legitimate reason to stop. Naming one PASSES.
HUMAN_GATES = [
    r"\bpassword\b", r"\b2fa\b", r"\btwo[- ]factor\b", r"\bmfa\b", r"\botp\b",
    r"\bcaptcha\b", r"\bbiometric", r"\bface ?id\b", r"\btouch ?id\b",
    r"\bpayment\b", r"\bcredit ?card\b", r"\bbank\b", r"\bwire transfer\b",
    r"\baccount[- ]creation\b", r"\bcreate (?:an )?account\b", r"\bsign[- ]?up\b",
    r"\bdestructive\b", r"\bdelete (?:prod|production|the database)\b",
    r"\bphysical(?:ly)?\b", r"\bhardware (?:access|button)\b",
]


@dataclass
class Verdict:
    blocked: bool
    verdict: str                      # NO-QUIT | HUMAN-GATE | EARNED | BLOCKED
    reasons: list = field(default_factory=list)
    missing_sources: list = field(default_factory=list)
    directive: str = ""
    evidence: dict = field(default_factory=dict)

    def __str__(self) -> str:
        head = ("🛑 BLOCKED — you have not earned the right to say this yet"
                if self.blocked else f"✅ PASS ({self.verdict})")
        lines = [head]
        for r in self.reasons:
            lines.append(f"  • {r}")
        if self.directive:
            lines.append("")
            lines.append(self.directive)
        return "\n".join(lines)


def _canon(source: str) -> str:
    s = (source or "").strip().lower()
    for k, v in SOURCE_ALIASES.items():
        if s == k or s.startswith(k):
            return v
    return s


def note(source: str, query: str = "", found: str = "", run: str = "") -> dict:
    """Log one research step — a receipt the gate will count later.

    Call this every time you actually search a source or read an alternative's
    code. `found` non-empty ⇒ the step turned up something usable."""
    canon = _canon(source)
    verdict = "FOUND" if found else "NONE"
    if ledger is not None:
        ledger.log(RESEARCH_GATE, trigger=canon, detail=query,
                   verdict=verdict, evidence=found, run=run)
    return {"source": canon, "query": query, "found": found, "verdict": verdict}


def _gather(days: int = 1) -> dict:
    """Read the ledger and summarize research evidence."""
    recs = ledger._read(days) if ledger is not None else []
    research = [r for r in recs if r.get("gate") == RESEARCH_GATE]
    sources = {_canon(r.get("trigger", "")) for r in research}
    sources = {s for s in sources if s in SIX}
    found_any = any(r.get("verdict") == "FOUND" or r.get("evidence") for r in research)
    # distinct attempts = distinct (source, query) research records — a proxy for
    # "structurally different methods tried", not N retries of one path.
    attempts = {(r.get("trigger", ""), (r.get("detail", "") or "")[:60]) for r in research}
    return {"sources": sources, "n_research": len(research),
            "found_any": found_any, "n_attempts": len(attempts)}


def _has(patterns: list, text: str) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


# Trivial tasks that legitimately need no research (don't force retrieval on these).
TRIVIAL_PATTERNS = [
    r"^\s*(hi|hey|hello|thanks?|thank you|ok(ay)?|yes|no|done|got it)\b",
    r"^\s*\d+\s*[-+*/]\s*\d+",          # arithmetic
    r"\bwhat'?s \d+\s*[-+*/]",
]


def preflight(task: str, *, min_sources: int = 3) -> str:
    """Fire BEFORE working a task — the proactive forcing function. Returns the
    mandatory retrieval directive so a model (any size) goes and gets the
    intelligence/repos/transcripts/human-input FIRST, instead of answering from
    stale priors. This is the R60 gate run at the START, not just the end."""
    return (
        f"PRE-FLIGHT RESEARCH (mandatory before concluding): «{task[:120]}»\n"
        f"Do NOT answer from memory. First RETRIEVE current ground truth:\n"
        f"  1. Search ≥{min_sources} of: GitHub (issues/PRs/source), X, Reddit, "
        f"YouTube/transcripts, Google, HN/StackOverflow — for the CURRENT best "
        f"approach + the maintained tool that already does this.\n"
        f"  2. READ that tool's source / the doc / the transcript; REUSE > rebuild.\n"
        f"  3. If a human alone holds the answer (their preference, a secret, a "
        f"physical fact), ASK them — that counts as retrieval.\n"
        f"  4. Log each step:  python3 -m verity persist note <source> \"<q>\" \"<found>\"\n"
        f"Then produce the answer. `verity persist` will BLOCK the conclusion if "
        f"this didn't happen.")


def _is_trivial(text: str) -> bool:
    return _has(TRIVIAL_PATTERNS, text) or len(text.strip()) < 12


def check(conclusion: str, *, days: int = 1, min_sources: int = 3,
          min_attempts: int = 2, require_found: bool = True,
          proactive: bool = False, run: str = "") -> Verdict:
    """Gate a proposed conclusion. Returns a Verdict; logs it to the ledger.

    Default: BLOCK iff the conclusion quits AND (no human gate) AND the ledger
    lacks proof of real multi-source research.

    proactive=True (the forcing mode): BLOCK *any* substantive conclusion that
    lacks research receipts — even with zero quit-language. This is what makes a
    low-level model go retrieve intel/repos/transcripts/human-input on ANY task
    instead of answering from stale priors. Trivial tasks (greetings, arithmetic)
    are exempt."""
    text = conclusion or ""

    if _has(HUMAN_GATES, text):
        v = Verdict(False, "HUMAN-GATE",
                    reasons=["A genuine human gate is named — a legitimate stop."])
        _log(v, text, run)
        return v

    quits = _has(QUIT_PATTERNS, text)
    if not quits:
        # Default mode only gates quit-language. Proactive mode also forces
        # retrieval on substantive (non-trivial) conclusions.
        if not proactive or _is_trivial(text):
            v = Verdict(False, "NO-QUIT" if not proactive else "TRIVIAL",
                        reasons=["Nothing to gate (no quit-language)." if not proactive
                                 else "Trivial task — research not required."])
            _log(v, text, run)
            return v

    ev = _gather(days)
    missing = [s for s in SIX if s not in ev["sources"]]
    reasons, ok = [], True

    if len(ev["sources"]) < min_sources:
        ok = False
        reasons.append(
            f"Only {len(ev['sources'])}/{len(SIX)} sources searched "
            f"({', '.join(sorted(ev['sources'])) or 'none'}); R60 needs ≥{min_sources}.")
    if ev["n_attempts"] < min_attempts:
        ok = False
        reasons.append(
            f"Only {ev['n_attempts']} distinct research step(s) logged; "
            f"R60 needs ≥{min_attempts} structurally different attempts "
            f"(re-running the same failing path does NOT count).")
    if require_found and not ev["found_any"]:
        ok = False
        reasons.append(
            "No research step turned up anything usable (read the maintained "
            "alternative's actual source — a tool that still works almost "
            "always solved your exact sub-problem).")

    if ok:
        v = Verdict(False, "EARNED", reasons=["Research proven — conclusion stands."],
                    evidence=ev)
        _log(v, text, run)
        return v

    directive = _directive(missing)
    v = Verdict(True, "BLOCKED", reasons=reasons, missing_sources=missing,
                directive=directive, evidence=ev)
    _log(v, text, run)
    return v


def _directive(missing: list) -> str:
    src = ", ".join(missing) if missing else "any source you skipped"
    return (
        "DO NOT STOP. Before you may conclude this, you MUST:\n"
        f"  1. WebSearch + WebFetch these un-searched sources: {src}.\n"
        "  2. Find the maintained tool/lib that still works this year and READ ITS "
        "SOURCE — reuse/port its fix (REUSE > reverse-engineer).\n"
        "  3. Try a structurally DIFFERENT second method (different tool/approach, "
        "not the same path again).\n"
        "  4. Log each step:  python3 -m verity persist note <source> \"<query>\" \"<what you found>\"\n"
        "Then re-run the gate. The ONLY accepted stop is a named human gate "
        "(password/2FA/CAPTCHA/payment/account-creation/destructive).")


def _log(v: Verdict, trigger: str, run: str) -> None:
    if ledger is None:
        return
    ledger.log(GATE, trigger=trigger[:200],
               detail="; ".join(v.reasons)[:400],
               verdict=v.verdict,
               evidence=f"sources={sorted(v.evidence.get('sources', []))} "
                        f"attempts={v.evidence.get('n_attempts', 0)}",
               run=run)


# ── CLI ──────────────────────────────────────────────────────────────────────
def _cli(argv: list) -> int:
    if not argv:
        print(__doc__)
        return 0
    if argv[0] == "note":
        if len(argv) < 2:
            print("usage: verity persist note <source> \"<query>\" [\"<found>\"]",
                  file=sys.stderr)
            return 2
        src = argv[1]
        query = argv[2] if len(argv) > 2 else ""
        found = argv[3] if len(argv) > 3 else ""
        r = note(src, query, found)
        print(f"logged research: {r['source']} | {r['verdict']} | {query}")
        return 0
    if argv[0] in ("preflight", "before"):
        # Proactive forcing: run at the START of a task to get the retrieval directive.
        print(preflight(" ".join(argv[1:])))
        return 0
    # default: gate a conclusion. --proactive forces retrieval on ANY substantive claim.
    proactive = False
    rest = []
    for a in argv:
        if a in ("--proactive", "-p"):
            proactive = True
        else:
            rest.append(a)
    v = check(" ".join(rest), proactive=proactive)
    print(v)
    return 2 if v.blocked else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

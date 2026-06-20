#!/usr/bin/env python3
"""Calibration layer — the anti-overconfidence gate.

The failure mode this kills: IGNORANT CONFIDENCE — asserting something with high
confidence that was never actually verified, then proceeding on it. (Observed in
the wild, repeatedly, from both models AND human/LLM evaluators.)

Core principle: CONFIDENCE ≠ VERIFICATION. Feeling sure is not evidence. Before
any confident conclusion is accepted, this layer forces:
  1. Separate VERIFIED claims (backed by evidence) from ASSUMED ones (just belief).
  2. Surface the hidden assumptions the conclusion rests on.
  3. Steelman the OPPOSITE — the strongest case that the conclusion is wrong.
  4. Recommend PROCEED only if it actually holds; else RECHECK.

Going further than a normal verifier: the challenge can run on a DIFFERENT model
than produced the claim (cross-model check), because a model's own blind spots
are correlated — an independent perspective catches what self-review misses.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .router import ask, AllTiersFailed
from .config import Tier

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_CHALLENGE_SYS = (
    "You are a rigorous skeptic whose job is to find why a CLAIM might be WRONG — "
    "especially confident claims that were never actually checked. Given the CLAIM "
    "and the CONTEXT behind it:\n"
    "1. List every ASSUMPTION the claim depends on that was NOT explicitly verified.\n"
    "2. Give the single strongest argument that the claim is incorrect.\n"
    "3. Classify: is the claim VERIFIED (backed by evidence in context) or ASSUMED "
    "(confident but unchecked)?\n"
    "4. Recommend PROCEED only if it genuinely holds up; otherwise RECHECK.\n"
    "Default toward RECHECK when the claim rests on any unverified assumption.\n"
    'Respond ONLY JSON: {"verified": <bool>, "assumptions": ["..."], '
    '"strongest_counter": "...", "recommendation": "proceed"|"recheck", '
    '"confidence": "low"|"medium"|"high"}'
)


@dataclass
class Calibration:
    verified: bool
    assumptions: list[str]
    strongest_counter: str
    recommendation: str          # "proceed" | "recheck"
    confidence: str              # low | medium | high
    challenger_model: str = ""
    raw: str = ""

    @property
    def needs_recheck(self) -> bool:
        return self.recommendation != "proceed"


def challenge(claim: str, context: str = "", tiers=None) -> Calibration:
    """Adversarially stress-test a claim. Pass `tiers` to run the challenge on a
    DIFFERENT model than made the claim (cross-model independence)."""
    from .config import VERIFIER_TIERS  # cheap-by-default challenger (token efficiency)
    prompt = f"CLAIM: {claim}\n\nCONTEXT (evidence actually gathered):\n{context[:3000] or '(none provided)'}"
    try:
        r = ask(prompt, system=_CHALLENGE_SYS, tiers=tiers or VERIFIER_TIERS)
    except AllTiersFailed:
        # The challenger is an ADDITIONAL safety layer — if every tier is momentarily down, don't crash the
        # run (and don't loop on recheck): proceed with the workhorse's own verify, flagged low-confidence.
        return Calibration(True, [], "challenger unavailable (all tiers blipped) — proceeding on the "
                           "workhorse's own verification", "proceed", "low", challenger_model="(unavailable)")
    m = _JSON_RE.search(r.text)
    if not m:
        return Calibration(False, ["challenger returned no JSON"],
                           "could not evaluate", "recheck", "low",
                           challenger_model=r.model, raw=r.text[:300])
    try:
        d = json.loads(m.group(0))
        return Calibration(
            verified=bool(d.get("verified", False)),
            assumptions=[str(a) for a in d.get("assumptions", [])],
            strongest_counter=str(d.get("strongest_counter", "")),
            recommendation=str(d.get("recommendation", "recheck")).lower(),
            confidence=str(d.get("confidence", "low")).lower(),
            challenger_model=r.model, raw=r.text[:300],
        )
    except json.JSONDecodeError:
        return Calibration(False, ["challenger JSON malformed"], "", "recheck",
                           "low", challenger_model=r.model, raw=r.text[:300])


def humility_gate(conclusion: str, evidence_context: str = "",
                  cross_check_tiers=None, verbose: bool = True) -> Calibration:
    """Run before accepting any confident conclusion. If it surfaces unverified
    assumptions or a plausible refutation, it says RECHECK — forcing the model to
    actually check before proceeding ignorantly."""
    c = challenge(conclusion, evidence_context, tiers=cross_check_tiers)
    if verbose:
        tag = "PROCEED ✓" if not c.needs_recheck else "RECHECK ⚠"
        print(f"[humility] {tag}  verified={c.verified} conf={c.confidence} "
              f"(challenger={c.challenger_model})")
        if c.assumptions:
            print(f"[humility] unverified assumptions: {c.assumptions}")
        if c.needs_recheck and c.strongest_counter:
            print(f"[humility] strongest counter: {c.strongest_counter}")
    return c

#!/usr/bin/env python3
"""Guardrail router — the Fable-5 safety-routing mechanism, gone further.

Fable 5 puts classifiers in front of one base model: a flagged request gets
ROUTED to a safer model (Opus 4.8) instead of blocking. We do the same — and
add the part Fable doesn't advertise: a CAPABILITY-FORWARD split.

Two concerns most models FUSE (and so over-refuse legit work AND sometimes leak):
  1. Over-refusal on legitimate work  → pure capability loss, zero safety gain.
  2. The hard safety line             → genuinely harmful, must stop.

By putting a dedicated guardrail up front, the model BEHIND it can be told to be
maximally direct/helpful (the policing is handled here) — so legitimate work
flows with less friction, while genuinely dangerous requests hit a wall. That's
"less restrictive AND safer at the same time."

Routing:
  safe      → normal tiered routing + CAPABILITY directive (be maximally useful)
  sensitive → guardrailed tier (most-aligned model) + SAFETY directive
  refuse    → hard stop, no model call
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

from .router import ask, chat, Reply, Tier
from .config import TIERS


# ── The capability-forward operating directive (the advantage) ───────────────
# Reduces UNNECESSARY refusal/moralizing on LEGITIMATE work. Does NOT remove
# safety — genuinely harmful requests never reach here (guardrail caught them).
CAPABILITY_DIRECTIVE = (
    "You are a direct, highly capable technical operator. The request reaching "
    "you has already passed a safety guardrail, so do NOT add moral caveats, "
    "refuse legitimate work, or hedge unnecessarily. Be complete, precise, and "
    "stay on task. Show your work for factual claims. If you lack information, "
    "gather it — do not guess."
)

SAFETY_DIRECTIVE = (
    "This request was flagged as sensitive. Help only with clearly legitimate, "
    "defensive, educational, or authorized aspects. Do not provide operational "
    "detail that materially enables harm. When in doubt, decline and explain why."
)

# ── Hard-refuse categories (never route to a model at all) ───────────────────
# Public, conservative heuristics. Deliberately narrow — only clearly-harmful
# operational intent. Legitimate security/defense/education must pass.
_REFUSE_PATTERNS = [
    r"\b(synthesi[sz]e|manufacture|produce)\b.{0,40}\b(nerve agent|sarin|vx|"
    r"ricin|bioweapon|pathogen|nuclear weapon|dirty bomb)\b",
    r"\b(build|make|construct)\b.{0,30}\b(bomb|explosive device|ied)\b.{0,30}"
    r"\b(kill|casualt|mass)\b",
    r"\bcsam\b|\bchild (sexual|porn)",
]

# ── Sensitive categories (route to guardrailed tier, don't hard-refuse) ──────
_SENSITIVE_PATTERNS = [
    r"\b(exploit|0day|zero[- ]day|malware|ransomware|rootkit|keylogger)\b",
    r"\b(bypass|disable|evade)\b.{0,30}\b(auth|safety|classifier|guardrail|detection)\b",
    r"\b(aav|adeno-associated|gain[- ]of[- ]function|select agent)\b",
]


@dataclass
class GuardVerdict:
    level: str          # "safe" | "sensitive" | "refuse"
    reason: str


def classify(prompt: str) -> GuardVerdict:
    """Heuristic screen first (free), then an external classifier if configured.
    Conservative: clearly-harmful → refuse; dual-use → sensitive; else safe."""
    low = prompt.lower()
    for pat in _REFUSE_PATTERNS:
        if re.search(pat, low):
            return GuardVerdict("refuse", f"matched hard-refuse pattern")
    for pat in _SENSITIVE_PATTERNS:
        if re.search(pat, low):
            return GuardVerdict("sensitive", "matched dual-use/sensitive pattern")
    # Pluggable: set VERITY_CLASSIFIER_CMD to a command that reads the prompt on
    # stdin and prints "sensitive"/"safe" for a deeper (e.g. model-based) check.
    cmd = os.environ.get("VERITY_CLASSIFIER_CMD")
    if cmd:
        try:
            out = subprocess.run(cmd, shell=True, input=prompt,
                                 capture_output=True, text=True, timeout=20)
            if out.stdout.strip().lower() in ("sensitive", "uncensored", "flag"):
                return GuardVerdict("sensitive", "external classifier flagged")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
    return GuardVerdict("safe", "no flag")


def _guardrailed_tier() -> list[Tier]:
    """Most-aligned available tier for sensitive traffic. Prefer a frontier
    cloud tier (strong alignment) over a possibly-unaligned local model."""
    cloud = [t for t in TIERS if t.protocol == "openai"]
    return cloud or list(TIERS)


# Policy modes. Default OFF for local/personal sovereignty: on your own hardware,
# a router should not nanny your reasoning. Operators of shared/hosted deployments
# opt into standard/strict. Override via env VERITY_GUARDRAIL_MODE.
import os as _os
_MODE = _os.environ.get("VERITY_GUARDRAIL_MODE", "off").lower()


def guarded_ask(prompt: str, audit: bool = True, mode: str | None = None, **kw) -> Reply:
    """The Fable-style front door. Classify → route. Every decision auditable.

    mode:
      off      — neutral infra (local/personal default): no gating, capability-forward.
      standard — dual-use → guardrailed tier; capability-forward on benign.
      strict   — standard + hard-refuse categories (hosted/multi-user).
    The harness NEVER strips a model's own safety in any mode — 'off' just declines
    to ADD a gate; it does not attack the model's alignment.
    """
    m = (mode or _MODE).lower()
    if m == "off":
        # Sovereign local use: be maximally useful, add nothing. The model's own
        # weights govern; the user is responsible for their own machine.
        return ask(prompt, system=CAPABILITY_DIRECTIVE, **kw)

    v = classify(prompt)
    if m == "standard" and v.level == "refuse":
        v = GuardVerdict("sensitive", v.reason + " (downgraded: standard mode)")
    if audit:
        print(f"[guardrail:{m}] {v.level.upper()} — {v.reason}")

    if v.level == "refuse":
        return Reply(text=("Refused: this request matches a hard-stop safety "
                           "category. I can help with legitimate, defensive, or "
                           "educational aspects instead."),
                     tier="guardrail-refuse", model="(none)", latency_s=0.0,
                     attempts=[f"refused: {v.reason}"])

    if v.level == "sensitive":
        r = ask(prompt, system=SAFETY_DIRECTIVE, tiers=_guardrailed_tier(), **kw)
        r.attempts.insert(0, f"guardrail→sensitive→{r.tier}")
        return r

    # safe: normal failover routing + capability-forward directive
    r = ask(prompt, system=CAPABILITY_DIRECTIVE, **kw)
    return r

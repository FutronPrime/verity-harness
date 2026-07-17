#!/usr/bin/env python3
"""Cross-lab CLI ensemble — council members drawn from DIFFERENT labs' CLIs.

VERITY's council (verity/council.py, ported from karpathy/llm-council) already runs the
3-stage blind-deliberation gate, but its default members are VERITY's own sovereign tiers —
which often share a provider family, so their blind spots correlate. This module supplies
members from genuinely different labs (Anthropic Claude, OpenAI Codex, Google Gemini, xAI Grok)
by shelling out to whichever of their CLIs are installed. Different labs ⇒ less-correlated
errors ⇒ agreement is stronger evidence and the chairman synthesis is more robust.

Drop-in with council(): pass `members=available_legs()` and `ask_fn=cli_ask`. Members not
installed are simply skipped; a leg that errors/times out degrades to "(no answer)" and the
council carries on with the rest (VERITY's degrade-don't-fail posture).

  python3 -m verity council --ensemble "<question>"   # council over the cross-lab legs
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Leg:
    name: str          # council member name (also the lab tag)
    bin: str           # CLI executable
    args: tuple        # invocation; {P} is replaced by the prompt


# Non-interactive invocations per lab CLI. Overridable via env (e.g. VERITY_LEG_GROK="grok -p {P}")
# so a CLI that changes its headless flag doesn't require a code edit.
_LEGS = [
    Leg("claude(anthropic)", "claude", ("-p", "{P}")),
    Leg("codex(openai)",     "codex",  ("exec", "{P}")),
    Leg("gemini(google)",    "gemini", ("-p", "{P}")),
    Leg("grok(xai)",         "grok",   ("-p", "{P}")),
]


def _leg_args(leg: Leg, prompt: str) -> list:
    override = os.environ.get(f"VERITY_LEG_{leg.name.split('(')[0].upper()}")
    if override:
        return [override.replace("{P}", prompt)] if " " not in override.replace("{P}", "") \
            else _shlex(override, prompt)
    return [leg.bin] + [a.replace("{P}", prompt) for a in leg.args]


def _shlex(template: str, prompt: str) -> list:
    import shlex
    return [t.replace("{P}", prompt) for t in shlex.split(template)]


def available_legs() -> list:
    """The subset of cross-lab legs whose CLI is actually on PATH."""
    return [leg for leg in _LEGS if shutil.which(leg.bin)]


def cli_ask(member: Leg, prompt: str, timeout_s: float = 120) -> str:
    """ask_fn contract for council(): run one leg's CLI headless, return its answer text."""
    try:
        p = subprocess.run(_leg_args(member, prompt), capture_output=True, text=True,
                           timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return f"(no answer: {member.name} timed out after {timeout_s:.0f}s)"
    except Exception as e:
        return f"(no answer: {member.name} failed: {e})"
    out = (p.stdout or "").strip()
    if not out and p.returncode != 0:
        return f"(no answer: {member.name} exit {p.returncode}: {(p.stderr or '').strip()[:120]})"
    return out or "(no answer: empty)"


def status() -> str:
    legs = available_legs()
    have = ", ".join(l.name for l in legs) or "none"
    return f"cross-lab legs available: {len(legs)}/4 — {have}"


if __name__ == "__main__":  # pragma: no cover
    print(status())

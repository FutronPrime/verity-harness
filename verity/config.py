#!/usr/bin/env python3
"""Tier configuration for the Verity Router.

The router tries tiers top→bottom and serves from the first that answers. Order
encodes strategy: cloud first (cheap/fast while available), owned local weights
last (the floor nothing can revoke).

100% self-contained: no external services required. Tier 1 is any
OpenAI-compatible API (set a key); Tier 0 is Ollama on your own machine. Run
`bash setup.sh` once to install Ollama + pull a model if you don't have them.

NO hardcoded secrets — keys come from environment variables only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Tier:
    name: str            # display label
    protocol: str        # "openai" (chat-completions) | "ollama" (native /api/chat)
    base_url: str        # no trailing slash
    model: str           # model id at that endpoint
    timeout_s: float     # how long before we call it dead and fail over
    api_key: str = ""    # bearer token for "openai" protocol (env-sourced)


# ── Tier 1: any OpenAI-compatible cloud API (OpenRouter / OpenAI / together / …) ──
# Default points at OpenRouter (one key → hundreds of models). Override via env.
_T1_URL = os.environ.get("LLM_TIER1_URL", "https://openrouter.ai/api/v1")
_T1_KEY = (os.environ.get("LLM_TIER1_API_KEY")
           or os.environ.get("OPENROUTER_API_KEY")
           or os.environ.get("OPENAI_API_KEY", ""))
_T1_MODEL = os.environ.get("LLM_TIER1_MODEL", "openai/gpt-4o-mini")

# ── Tier 0: SOVEREIGN floor — open weights on YOUR machine via Ollama ──
_OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
_T0_MODEL = os.environ.get("LLM_TIER0_MODEL", "llama3.2")

TIERS: list[Tier] = [
    Tier(name="tier1-cloud", protocol="openai", base_url=_T1_URL, model=_T1_MODEL,
         api_key=_T1_KEY, timeout_s=float(os.environ.get("LLM_TIER1_TIMEOUT", "90"))),
    Tier(name="tier0-local", protocol="ollama", base_url=_OLLAMA, model=_T0_MODEL,
         timeout_s=float(os.environ.get("LLM_TIER0_TIMEOUT", "120"))),
]

# Token efficiency: verification is discrimination, not generation — route it to a
# cheap model. Defaults to the same tiers (safe everywhere); set LLM_VERIFIER_MODEL
# to a small/cheap model id for real savings.
_V_MODEL = os.environ.get("LLM_VERIFIER_MODEL", "")
VERIFIER_TIERS: list[Tier] = (
    [Tier(name="verifier", protocol="openai", base_url=_T1_URL, model=_V_MODEL,
          api_key=_T1_KEY, timeout_s=45), TIERS[-1]]
    if _V_MODEL else TIERS
)


def summary() -> str:
    lines = ["Verity Router — tier order (failover walks top→bottom):"]
    for i, t in enumerate(TIERS):
        floor = "  ← sovereign floor (un-revocable)" if t.protocol == "ollama" else ""
        key = "" if t.protocol == "ollama" else ("  [key set]" if t.api_key
              else "  [NO KEY — set LLM_TIER1_API_KEY]")
        lines.append(f"  {i+1}. {t.name:<12} {t.protocol:<7} {t.model}{key}{floor}")
    return "\n".join(lines)

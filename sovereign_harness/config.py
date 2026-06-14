#!/usr/bin/env python3
"""Tier configuration for the Sovereign Harness router.

The router tries tiers top→bottom and serves from the first that answers.
Order encodes strategy:
  - Tier 1 first  = use a cloud API while it's available (fast, capable, revocable).
  - Tier 0 last   = self-hosted open weights you OWN = the floor nothing can revoke.

NO SECRETS IN THIS FILE. API keys (if your Tier 1 endpoint needs one) load from
environment variables at runtime. Everything is overridable via env so you never
have to edit code.

Env vars:
  LLM_TIER1_URL       Tier 1 base URL   (default: https://api.openai.com/v1)
  LLM_TIER1_MODEL     Tier 1 model id   (default: gpt-4o-mini)
  LLM_TIER1_API_KEY   Tier 1 bearer key (default: $OPENAI_API_KEY)
  LLM_TIER0_URL       Ollama base URL   (default: http://127.0.0.1:11434)
  LLM_TIER0_MODEL     local model id    (default: qwen2.5:7b)
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
    api_key: str = ""    # optional bearer token (empty = no Authorization header)


TIERS: list[Tier] = [
    # ── Tier 1: cloud API (any OpenAI-compatible endpoint: OpenAI, OpenRouter,
    #    Together, Groq, or your own gateway). Used while available. ──
    Tier(
        name="tier1-cloud",
        protocol="openai",
        base_url=os.environ.get("LLM_TIER1_URL", "https://api.openai.com/v1"),
        model=os.environ.get("LLM_TIER1_MODEL", "gpt-4o-mini"),
        timeout_s=float(os.environ.get("LLM_TIER1_TIMEOUT", "90")),
        api_key=os.environ.get("LLM_TIER1_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
    ),
    # ── Tier 0: SOVEREIGN floor — open weights on local disk via Ollama.
    #    Un-revocable. No API key. This is the part nothing can take from you. ──
    Tier(
        name="tier0-local",
        protocol="ollama",
        base_url=os.environ.get("LLM_TIER0_URL", "http://127.0.0.1:11434"),
        model=os.environ.get("LLM_TIER0_MODEL", "qwen2.5:7b"),
        timeout_s=float(os.environ.get("LLM_TIER0_TIMEOUT", "120")),
    ),
]


def summary() -> str:
    lines = ["Sovereign Harness — tier order (failover walks top→bottom):"]
    for i, t in enumerate(TIERS):
        floor = "  ← sovereign floor (un-revocable)" if t.name == "tier0-local" else ""
        key = " [keyed]" if t.api_key else ""
        lines.append(f"  {i+1}. {t.name:<12} {t.protocol:<7} {t.model}{key}{floor}")
    return "\n".join(lines)

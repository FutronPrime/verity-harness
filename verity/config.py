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
import pathlib
from dataclasses import dataclass

# ── Persistent tier config (so you don't have to export env vars every shell) ──
# Drop your tier wiring in ~/.verity-harness/verity.env as KEY=VALUE lines (e.g. point a tier at a local
# OAuth shim that wraps your claude/codex/gemini CLI, or any OpenAI-compatible endpoint). Loaded BEFORE the
# tiers are read; real environment variables still win over the file. This is the public-repo "wire YOUR
# brain once" mechanism — frontier-via-CLI for subscription users, local Ollama for local-model users.
def _load_env_file() -> None:
    p = pathlib.Path(os.path.expanduser("~/.verity-harness/verity.env"))
    try:
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)   # real env wins; file fills the gaps
    except Exception:
        pass

_load_env_file()


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
_T1_TIMEOUT = float(os.environ.get("LLM_TIER1_TIMEOUT", "90"))

# CAPABILITY-PRESERVING FAILOVER: a chain of PEER models so a frontier outage falls to ANOTHER
# frontier, not a weak floor. Set LLM_TIER1_MODELS="claude-opus,gpt-5.5,gemini-3.1-pro" (all at the
# same OpenAI-compatible URL — a shim, or OpenRouter which serves all of them on one key). The
# router retries each model itself, THEN walks to the next peer, and only as a LAST resort drops to
# the local sovereign floor. So: Opus 4.8 → (self-retry) → GPT-5.5 → Gemini 3.1 → local weights.
_T1_MODELS = [m.strip() for m in os.environ.get("LLM_TIER1_MODELS", "").split(",") if m.strip()] \
    or [_T1_MODEL]

# ── Tier 0: SOVEREIGN floor — open weights on YOUR machine via Ollama (un-revocable last resort) ──
# ── Tier 1b: an INDEPENDENT second provider (different company + endpoint + key) so a WHOLE-PROVIDER
# outage (OpenRouter itself down, or one key revoked) still has a frontier-class fallback before the
# local floor. No single provider/token is a point of failure. Set LLM_TIER2_URL/KEY/MODEL, or it
# auto-enables from GROQ_API_KEY (Groq's OpenAI-compatible endpoint). ──
_T2_URL = (os.environ.get("LLM_TIER2_URL")
           or ("https://api.groq.com/openai/v1" if os.environ.get("GROQ_API_KEY") else ""))
_T2_KEY = os.environ.get("LLM_TIER2_API_KEY") or os.environ.get("GROQ_API_KEY", "")
_T2_MODEL = os.environ.get("LLM_TIER2_MODEL", "llama-3.3-70b-versatile")

# ── Tier 0: SOVEREIGN floor — open weights on YOUR machine via Ollama (un-revocable last resort) ──
_OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
_T0_MODEL = os.environ.get("LLM_TIER0_MODEL", "llama3.2")

# Works for ANY setup — the tiers present adapt to what YOU configured:
#   • Multi-provider (default + keys): full chain → 2nd provider → local floor.
#   • Single enterprise model only: set LLM_TIER1_URL/MODEL/API_KEY to that one vendor → it + local floor.
#   • LOCAL-ONLY (no cloud key at all): Tier1 is SKIPPED entirely → straight to your Ollama floor, no
#     doomed cloud calls. The discipline layer (gates, overconfidence guard, verify, calibrate) is
#     model-agnostic, so it works identically whether you run 5 tiers or just a local 8B.
TIERS: list[Tier] = (
    ([Tier(name=f"tier1-{i+1}-{m.split('/')[-1][:18]}", protocol="openai", base_url=_T1_URL,
           model=m, api_key=_T1_KEY, timeout_s=_T1_TIMEOUT)
      for i, m in enumerate(_T1_MODELS)] if _T1_KEY else [])
    + ([Tier(name="tier1b-2nd-provider", protocol="openai", base_url=_T2_URL,
             model=_T2_MODEL, api_key=_T2_KEY, timeout_s=_T1_TIMEOUT)]
       if _T2_URL and _T2_KEY else [])
    + [Tier(name="tier0-local", protocol="ollama", base_url=_OLLAMA, model=_T0_MODEL,
            timeout_s=float(os.environ.get("LLM_TIER0_TIMEOUT", "120")))]
)

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

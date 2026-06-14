#!/usr/bin/env python3
"""Free-tier provider presets — capable agentic LLM access at ZERO cost.

The point: anyone running this harness should be able to get frontier-ish
capability for free, on THEIR OWN account — no shared key, no dependency on
anyone else's billing. Each preset below is a provider with a genuine free tier.
The user (or their LLM) gets their own key once; the harness does the rest.

Usage:
  python3 -m verity providers          # print the setup guide
  python3 -m verity providers gemini    # how to set up Gemini free tier

  from verity.providers import tier_from_preset
  tier = tier_from_preset("gemini")   # builds a Tier from $GEMINI_API_KEY
"""
from __future__ import annotations

import os

from .config import Tier

# Each preset: OpenAI-compatible base_url, a capable default model, the env var
# holding the user's OWN key, and where to get that key free.
PRESETS: dict[str, dict] = {
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
        "key_env": "GEMINI_API_KEY",
        "free_at": "https://aistudio.google.com/apikey",
        "note": "Google AI Studio — generous free tier, very capable (Gemini Flash).",
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_env": "GROQ_API_KEY",
        "free_at": "https://console.groq.com/keys",
        "note": "Groq — free tier, extremely fast inference (70B open models).",
    },
    "openrouter-free": {
        "url": "https://openrouter.ai/api/v1",
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "key_env": "OPENROUTER_API_KEY",
        "free_at": "https://openrouter.ai/keys",
        "note": "OpenRouter — many models with a ':free' variant (DeepSeek, etc.).",
    },
    "kimi": {
        "url": "https://api.moonshot.ai/v1",
        "model": "moonshot-v1-8k",
        "key_env": "MOONSHOT_API_KEY",
        "free_at": "https://platform.moonshot.ai/console/api-keys",
        "note": "Moonshot (Kimi) — free trial credits; strong long-context reasoning.",
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1",
        "model": "llama-3.3-70b",
        "key_env": "CEREBRAS_API_KEY",
        "free_at": "https://cloud.cerebras.ai",
        "note": "Cerebras — free tier, fastest 70B inference available.",
    },
}


def tier_from_preset(name: str, model: str | None = None, timeout_s: float = 90) -> Tier:
    """Build a Tier from a preset, reading the user's OWN key from its env var.
    Raises if the key isn't set — with a message telling them where to get one free."""
    p = PRESETS.get(name)
    if not p:
        raise KeyError(f"unknown preset {name!r}; choose from {list(PRESETS)}")
    key = os.environ.get(p["key_env"], "")
    if not key:
        raise RuntimeError(
            f"{p['key_env']} not set. Get a FREE key at {p['free_at']} then:\n"
            f"  export {p['key_env']}=<your-key>")
    return Tier(name=name, protocol="openai", base_url=p["url"],
                model=model or p["model"], timeout_s=timeout_s, api_key=key)


def setup_guide(which: str | None = None) -> str:
    """Human/LLM-readable guide for wiring up free access. An agent reading this
    can set up the user's own free provider without any shared credentials."""
    items = {which: PRESETS[which]} if which in PRESETS else PRESETS
    lines = ["FREE LLM ACCESS — set up your OWN (no shared keys, no one else's billing):", ""]
    for name, p in items.items():
        have = "✅ key set" if os.environ.get(p["key_env"]) else "— no key yet"
        lines += [
            f"▸ {name}  [{have}]",
            f"    {p['note']}",
            f"    1. Get a free key:  {p['free_at']}",
            f"    2. export {p['key_env']}=<your-key>",
            f"    3. Use it:  LLM_TIER1_URL={p['url']} \\",
            f"               LLM_TIER1_MODEL={p['model']} \\",
            f"               LLM_TIER1_API_KEY=${p['key_env']} python3 -m verity ask \"...\"",
            "",
        ]
    lines.append("Tip: set ONE of these as Tier 1 and keep Ollama as your local Tier 0 "
                 "floor — free cloud capability + un-revocable local fallback.")
    return "\n".join(lines)

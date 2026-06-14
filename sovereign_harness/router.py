#!/usr/bin/env python3
"""Sovereign Router — tiered LLM failover with ZERO external dependencies.

Sovereignty principle
---------------------
A vendor's access can be suspended overnight — by policy, by outage, by
government order. It CANNOT reach into open weights you already pulled to local
disk. So this router prefers a capable cloud API while it's available, and
silently fails over to self-hosted open weights the instant the cloud is
unreachable. Your system keeps thinking even if every vendor goes dark.

Zero pip dependencies on purpose: the harness that protects you from a vendor
being yanked must not itself break because a PyPI package was yanked. stdlib
only (urllib). No secrets in this file — API keys load from env via config.py.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Iterable

from .config import TIERS, Tier


class AllTiersFailed(RuntimeError):
    """Every tier was tried and none answered. True sovereignty failure."""


@dataclass
class Reply:
    text: str
    tier: str          # which tier served this ("tier1-cloud" / "tier0-local")
    model: str
    latency_s: float
    attempts: list[str] = field(default_factory=list)


def _post_json(url: str, payload: dict, timeout: float, api_key: str = "") -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _call_openai_compat(tier: Tier, messages: list[dict], timeout: float) -> str:
    out = _post_json(
        f"{tier.base_url}/chat/completions",
        {"model": tier.model, "messages": messages, "stream": False},
        timeout, tier.api_key,
    )
    return out["choices"][0]["message"]["content"]


def _call_ollama_native(tier: Tier, messages: list[dict], timeout: float) -> str:
    out = _post_json(
        f"{tier.base_url}/api/chat",
        {"model": tier.model, "messages": messages, "stream": False},
        timeout,
    )
    return out["message"]["content"]


_DISPATCH = {
    "openai": _call_openai_compat,
    "ollama": _call_ollama_native,
}


def chat(messages: list[dict], tiers: Iterable[Tier] = TIERS,
         verbose: bool = False) -> Reply:
    """Try each tier in order; return the first that answers. Fail over on ANY
    error (connection refused, timeout, auth, non-200, malformed body). A vendor
    going dark is an exception we CATCH, not a crash."""
    trail: list[str] = []
    for tier in tiers:
        t0 = time.monotonic()
        try:
            text = _DISPATCH[tier.protocol](tier, messages, tier.timeout_s)
            dt = time.monotonic() - t0
            trail.append(f"{tier.name}: OK ({dt:.1f}s)")
            if verbose:
                print(f"[router] served by {tier.name} ({tier.model}) in {dt:.1f}s")
            return Reply(text=text, tier=tier.name, model=tier.model,
                         latency_s=dt, attempts=trail)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                KeyError, json.JSONDecodeError, TimeoutError) as e:
            dt = time.monotonic() - t0
            trail.append(f"{tier.name}: FAIL [{type(e).__name__}] → failing over")
            if verbose:
                print(f"[router] {tier.name} unavailable [{type(e).__name__}] → next tier")
            continue

    raise AllTiersFailed(
        "All tiers exhausted. Even local weights are unreachable — is Ollama running?\n"
        + "\n".join(trail)
    )


def ask(prompt: str, system: str | None = None, **kw) -> Reply:
    """Convenience: single-turn prompt."""
    msgs = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    return chat(msgs, **kw)

#!/usr/bin/env python3
"""Sovereign Router — tiered LLM failover with ZERO external deps.

Sovereignty principle
---------------------
A government order can suspend an API overnight (see: Fable 5 / Mythos 5,
2026-06-12). It CANNOT reach into weights you already pulled to local disk.
So this router prefers cheap flat-fee cloud while it's available, and silently
fails over to self-hosted open weights the instant the cloud is unreachable —
The harness keeps thinking even if every vendor goes dark.

Zero pip dependencies on purpose: the harness that protects you from a vendor
being yanked must not itself break because a PyPI package was yanked. stdlib
only (urllib). No secrets in this file (Rule 1) — Tier 1 auth is handled by the
OAuth shim, Tier 0 needs none.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Iterable

from .config import TIERS, Tier


import os as _os
_RETRIES = int(_os.environ.get("LLM_RETRIES", "2"))   # per-tier retries on transient errors
_BACKOFF = float(_os.environ.get("LLM_BACKOFF", "1.5"))  # seconds, linear


class AllTiersFailed(RuntimeError):
    """Every tier was tried and none answered. True sovereignty failure."""


@dataclass
class Reply:
    text: str
    tier: str          # which tier served this ("tier1-cloud" / "tier0-local")
    model: str
    latency_s: float
    attempts: list[str] = field(default_factory=list)  # human-readable trail


class ProviderError(RuntimeError):
    """A provider returned an error WITH a readable message (HTTP body or error
    field). Carries .status so the retry layer can honor 429/503 backoff."""
    def __init__(self, msg: str, status: int = 0, headers=None):
        super().__init__(msg)
        self.status = status
        self.headers = headers or {}


def _post_json(url: str, payload: dict, timeout: float, api_key: str = "") -> dict:
    # A browser-like User-Agent: some providers sit behind Cloudflare, which 403s
    # (error 1010) the default "Python-urllib" signature. VERIFIED: default UA →
    # 403 on Groq, browser UA → OK. (Not a rate limit — measured, not assumed.)
    headers = {"Content-Type": "application/json",
               "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) sovereign-harness"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Surface the REAL provider message instead of an opaque "HTTPError".
        try:
            body = e.read().decode("utf-8", "ignore")[:400]
        except Exception:  # noqa: BLE001
            body = ""
        raise ProviderError(f"HTTP {e.code}: {body}", status=e.code, headers=e.headers)


def _call_openai_compat(tier: Tier, messages: list[dict], timeout: float) -> str:
    """OAuth shim, OpenRouter, and Ollama's /v1 all speak OpenAI chat."""
    out = _post_json(
        f"{tier.base_url}/chat/completions",
        {"model": tier.model, "messages": messages, "stream": False},
        timeout, getattr(tier, "api_key", ""),
    )
    # Some providers return a 200 with an {"error": ...} body — surface it clearly
    # instead of letting it become an opaque KeyError on out["choices"].
    if "choices" not in out:
        err = out.get("error")
        msg = (err.get("message") if isinstance(err, dict) else err) or str(out)[:300]
        raise ProviderError(f"no choices in response: {msg}")
    return out["choices"][0]["message"]["content"]


def _call_ollama_native(tier: Tier, messages: list[dict], timeout: float) -> str:
    """Ollama native /api/chat — the maximally-sovereign path (no shim, no cloud)."""
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


def chat(
    messages: list[dict],
    tiers: Iterable[Tier] = TIERS,
    verbose: bool = False,
) -> Reply:
    """Try each tier in order; return the first that answers. Fail over on
    ANY error (connection refused, timeout, auth, non-200, malformed body).

    The whole point: a vendor going dark is an exception we CATCH, not a
    crash. Tier 0 (local weights) is the floor that can't be revoked.
    """
    trail: list[str] = []
    for tier in tiers:
        t0 = time.monotonic()
        last = None
        # Retry the SAME tier a few times on TRANSIENT errors (rate limits, 5xx,
        # malformed/error bodies) before failing over — a momentary provider hiccup
        # shouldn't drop you to a weaker tier or crash a single-tier run.
        for attempt in range(_RETRIES + 1):
            try:
                caller = _DISPATCH[tier.protocol]
                text = caller(tier, messages, tier.timeout_s)
                dt = time.monotonic() - t0
                trail.append(f"{tier.name}: OK ({dt:.1f}s)")
                if verbose:
                    print(f"[router] served by {tier.name} ({tier.model}) in {dt:.1f}s")
                return Reply(text=text, tier=tier.name, model=tier.model,
                             latency_s=dt, attempts=trail)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                    KeyError, json.JSONDecodeError, TimeoutError, ProviderError) as e:
                last = e
                if attempt < _RETRIES:
                    wait = _BACKOFF * (attempt + 1)
                    # Respect a 429/503 Retry-After header (free tiers rate-limit
                    # agentic loops hard — honor their backoff window).
                    status = getattr(e, "code", None) or getattr(e, "status", None)
                    hdrs = getattr(e, "headers", {}) or {}
                    if status in (429, 503):
                        try:
                            wait = max(wait, float(hdrs.get("Retry-After", wait)))
                        except (TypeError, ValueError):
                            pass
                    time.sleep(min(wait, 30))
        dt = time.monotonic() - t0
        reason = str(last)[:160]
        trail.append(f"{tier.name}: FAIL [{reason}] after {_RETRIES+1} tries "
                     f"({dt:.1f}s) → failing over")
        if verbose:
            print(f"[router] {tier.name} unavailable [{reason}] → next tier")
        continue

    raise AllTiersFailed(
        "All tiers exhausted. Even local weights are unreachable — check Ollama.\n"
        + "\n".join(trail)
    )


def ask(prompt: str, system: str | None = None, **kw) -> Reply:
    """Convenience: single-turn prompt."""
    msgs = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    return chat(msgs, **kw)

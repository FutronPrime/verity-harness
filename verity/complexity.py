#!/usr/bin/env python3
"""Complexity-scored model routing — "Predictive Asymmetry" (the Fugu parity delta #1).

The base router (`router.py`) walks tiers in a FIXED order chosen for *availability*
(cheap-cloud first, sovereign-local floor last). The swarm runs every sub-agent at the
*same caliber as the lead*. That's correct for resilience, but it's the same hammer for
every nail: a "format this JSON" sub-task burns a frontier call, and a "design the auth
architecture" sub-task could get under-served on a single-tier run.

Fugu "handles model selection and switching for each task." This module adds that axis to
VERITY WITHOUT throwing away failover: a per-sub-task complexity score (1-10, emitted by the
planner or heuristically inferred) picks the tier BAND to ENTER at — and the existing tier
chain still sits underneath as failover. So band selection is an entry-point optimization,
never a new single point of failure.

  1-3  → cheap band   (trivial: format/rename/lint/stub)  → local floor or a cheap model
  4-7  → mid band     (normal: implement/edit/test)       → a mid model (e.g. a coder GGUF)
  8-10 → frontier band(hard: architect/debug/novel logic) → frontier, capability-first

Design rules (all enforced below):
  • OFF by default — opt in with VERITY_COMPLEXITY_ROUTING=1. Unset → behavior is byte-identical
    to today (same-caliber swarm), so it can never regress an existing setup.
  • FAILOVER PRESERVED — `tiers_for` returns [band entry] + the full base chain (deduped). A band
    outage still walks down to the sovereign floor.
  • NO HARDCODED MODEL IDS — band models come from env only (ids go stale; the registry is ground
    truth, per the harness's own Rule-0 discipline). Unconfigured bands degrade gracefully.
  • ZERO external deps — stdlib only, like the rest of the harness.

Env wiring (see verity.env.example):
  VERITY_COMPLEXITY_ROUTING=1
  VERITY_TIER_CHEAP_MODEL=...        # optional; unset → cheap band prefers the local floor
  VERITY_TIER_MID_MODEL=...          # optional; unset → mid band keeps the base chain
  VERITY_TIER_MID_CODE_MODEL=...     # optional; used for code-typed mid sub-tasks (e.g. gemma coder)
  VERITY_TIER_FRONTIER_MODEL=...     # optional; unset → frontier keeps the base (capability-first) chain
"""
from __future__ import annotations

import os
import re
from dataclasses import replace
from typing import Any

from .config import TIERS, Tier

# ── Band thresholds (inclusive upper bounds) ─────────────────────────────────
_CHEAP_MAX = 3
_MID_MAX = 7


def enabled() -> bool:
    """Complexity routing is opt-in. Default OFF → today's same-caliber behavior, byte-identical."""
    return os.environ.get("VERITY_COMPLEXITY_ROUTING", "").strip().lower() in ("1", "true", "on", "yes")


def band_for(score: int) -> str:
    """Map a 1-10 complexity score to a tier band. Out-of-range is clamped (never raises)."""
    s = max(1, min(10, int(score)))
    if s <= _CHEAP_MAX:
        return "cheap"
    if s <= _MID_MAX:
        return "mid"
    return "frontier"


# ── Heuristic scoring — fallback when the planner emits plain strings (no score) ─
_HARD = re.compile(
    r"\b(architect|design|refactor|migrat|debug|root[- ]?cause|optimi[sz]e|prove|derive|"
    r"distribut|concurren|thread|race condition|security|crypto|novel|algorithm|"
    r"end[- ]to[- ]end|trade[- ]?offs?|benchmark|profile)\b", re.I)
_EASY = re.compile(
    r"\b(format|rename|list|print|echo|lint|sort|capitali[sz]e|to ?json|to ?yaml|stub|"
    r"boilerplate|add a comment|comment out|rename the|trivial|one[- ]liner)\b", re.I)


def heuristic_score(text: str) -> int:
    """Cheap, deterministic 1-10 estimate when no model-supplied score exists. Conservative:
    only calls something EASY when it clearly is and isn't also hard; defaults to mid."""
    t = (text or "").lower()
    hard, easy = bool(_HARD.search(t)), bool(_EASY.search(t))
    if easy and not hard:
        return 2
    if hard:
        return 9
    return 7 if len(text or "") > 200 else 5


def normalize_subtasks(raw: Any, max_n: int = 4) -> list[dict]:
    """Accept BOTH legacy plain-string subtasks AND rich dict subtasks, and return uniform
    node dicts: {id, task, complexity(1-10), type, depends_on[]}. This is also the DAG node
    shape the swarm's topology executor consumes — so the planner schema upgrade is shared.

    Robust to messy LLM output: missing/garbage complexity falls back to heuristic_score;
    string deps are coerced; ids are filled. NEVER raises."""
    out: list[dict] = []
    for item in (raw or [])[:max_n]:
        if isinstance(item, dict):
            task = str(item.get("task") or item.get("subtask")
                       or item.get("instruction") or "").strip()
            if not task:
                continue
            raw_score = item.get("complexity", item.get("complexity_score"))
            try:
                score = int(raw_score)
            except (TypeError, ValueError):
                score = heuristic_score(task)
            score = max(1, min(10, score))
            ttype = str(item.get("type") or item.get("task_type") or "").strip() or None
            deps = item.get("depends_on") or item.get("deps") or []
            if not isinstance(deps, (list, tuple)):
                deps = [deps]
            nid = str(item.get("id") or (len(out) + 1))
            out.append({"id": nid, "task": task, "complexity": score,
                        "type": ttype, "depends_on": [str(d) for d in deps if str(d).strip()]})
        else:
            task = str(item).strip()
            if not task:
                continue
            out.append({"id": str(len(out) + 1), "task": task,
                        "complexity": heuristic_score(task), "type": None, "depends_on": []})
    return out


def _band_model(band: str, task_type: str | None = None) -> str:
    """The env-configured model id for a band, if any. Code-typed mid sub-tasks prefer a
    dedicated coder model (e.g. a fable-distilled gemma coder GGUF served on the tier-1 URL)."""
    if band == "mid" and task_type and "code" in task_type.lower():
        m = os.environ.get("VERITY_TIER_MID_CODE_MODEL", "").strip()
        if m:
            return m
    return os.environ.get(f"VERITY_TIER_{band.upper()}_MODEL", "").strip()


def _cloud_template(base_tiers: list[Tier]) -> Tier | None:
    """The first OpenAI-protocol tier WITH a key — its endpoint/key are reused for a band entry
    tier (so a band model is served by whatever endpoint the user already configured: OpenRouter,
    a local OAuth shim, etc.). None when local-only (nothing to right-size to)."""
    for t in base_tiers:
        if t.protocol == "openai" and getattr(t, "api_key", ""):
            return t
    return None


def tiers_for(score: int, task_type: str | None = None,
              base_tiers: list[Tier] | None = None) -> list[Tier]:
    """The crux: given a sub-task's complexity, return the tier list to run it through.

    Always FAILOVER-SAFE: the returned list is [band entry] + the full base chain (deduped),
    so a band outage still walks down to the sovereign floor. When routing is disabled, the
    band is unconfigured, or there's only a local floor, returns the base chain unchanged —
    i.e. it can only help, never break or regress."""
    base = list(base_tiers if base_tiers is not None else TIERS)
    if not enabled() or len(base) <= 1:
        return base

    band = band_for(score)
    model = _band_model(band, task_type)

    if model:
        tmpl = _cloud_template(base)
        if tmpl is not None:
            entry = replace(tmpl, name=f"band-{band}-{model.split('/')[-1][:14]}", model=model)
            # Dedup: drop any existing tier already pointing at this exact model, then prepend.
            rest = [t for t in base if not (t.protocol == "openai" and t.model == model)]
            return [entry] + rest

    # No explicit band model configured → model-free right-sizing that still adds value:
    if band == "cheap":
        # Route trivial work to the un-revocable local floor FIRST (free + fast); cloud stays
        # as failover beneath it. If there's no local tier, leave the order alone.
        local = [t for t in base if t.protocol == "ollama"]
        cloud = [t for t in base if t.protocol != "ollama"]
        return local + cloud if local else base

    # mid / frontier with no band model → keep the base capability-first order (unchanged).
    return base


def explain(nodes: list[dict]) -> str:
    """Human-readable routing preview for the ledger / verbose swarm output."""
    if not enabled():
        return "[complexity routing OFF — uniform caliber]"
    lines = []
    for n in nodes:
        b = band_for(n["complexity"])
        m = _band_model(b, n.get("type")) or ("local-first" if b == "cheap" else "base-chain")
        lines.append(f"  · [{n['complexity']:>2}/{b:<8}] {m:<22} {n['task'][:54]}")
    return "complexity routing ON →\n" + "\n".join(lines)

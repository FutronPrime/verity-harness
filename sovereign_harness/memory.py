#!/usr/bin/env python3
"""Persistent memory — the harness remembers across runs (the "3× memory" feature).

Sovereignty-consistent: the harness owns its OWN store (a local JSONL), so memory
survives even if every external service is down.

  remember(goal, summary)  → persist a completed task's outcome
  recall(goal, k)          → retrieve the k most relevant past outcomes as context

Retrieval is keyword-overlap (zero deps, zero model calls — free). Good enough to
surface "you've done something like this before, here's what worked."
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# Self-contained store under the user's home (override with SOVEREIGN_HOME).
_HOME = Path(os.environ.get("SOVEREIGN_HOME", str(Path.home() / ".sovereign-harness")))
STORE = _HOME / "memory.jsonl"
_WORD = re.compile(r"[a-z0-9]+")
# Common words that cause false-positive recalls (caught in testing: "weather in
# paris" matched "count THE python files" on the shared stopword "the").
_STOP = {"the", "and", "for", "are", "was", "what", "how", "many", "with", "this",
         "that", "you", "your", "all", "can", "does", "did", "from", "into", "out",
         "get", "has", "have", "any", "not", "but", "its", "use", "via"}


def _tokens(s: str) -> set[str]:
    return {w for w in _WORD.findall(s.lower()) if len(w) > 2 and w not in _STOP}


def remember(goal: str, summary: str, tags: list[str] | None = None) -> None:
    """Persist a task outcome. Append-only — never loses history."""
    rec = {
        "goal": goal,
        "summary": summary,
        "tags": tags or [],
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    STORE.parent.mkdir(parents=True, exist_ok=True)
    with STORE.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def _load() -> list[dict]:
    if not STORE.exists():
        return []
    out = []
    for line in STORE.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def recall(goal: str, k: int = 3) -> str:
    """Return up to k most-relevant past outcomes as an injectable context block.
    Empty string if nothing relevant (so it's safe to always prepend)."""
    goal_toks = _tokens(goal)
    if not goal_toks:
        return ""
    scored = []
    for rec in _load():
        overlap = len(goal_toks & _tokens(rec.get("goal", "")))
        if overlap:
            scored.append((overlap, rec))
    if not scored:
        return ""
    scored.sort(key=lambda x: -x[0])
    lines = ["RELEVANT PAST OUTCOMES (from memory — verify before relying):"]
    for _, rec in scored[:k]:
        lines.append(f"- goal: {rec['goal'][:120]}\n  outcome: {rec['summary'][:200]}")
    return "\n".join(lines) + "\n"

#!/usr/bin/env python3
"""Context compaction — keep long autonomous runs from blowing the context window.

The "million-token focus" feature, lean version: when a working transcript grows
past a threshold, summarize the OLD part (via the cheap verifier model) and keep
recent steps verbatim. This is what lets a 100-step run stay coherent instead of
either truncating blindly or overflowing.

  maybe_compact(transcript) → same string if short; compacted string if long.

Zero deps. The summary call goes to the cheap tier (it's a summary, not genius).
"""
from __future__ import annotations

from .router import ask

_SUMMARY_SYS = (
    "Summarize the prior work transcript into a compact brief that preserves "
    "EVERYTHING needed to finish the task: established facts, what was tried, what "
    "worked, what failed and why, and current state. Be terse. Drop nothing load-"
    "bearing. <=250 words."
)


def maybe_compact(transcript: str, max_chars: int = 12000, keep_tail: int = 4000,
                  tiers=None, verbose: bool = False) -> str:
    """Compact only if over budget. Keeps the recent tail verbatim (it's what the
    model needs most), summarizes the older head."""
    if len(transcript) <= max_chars:
        return transcript
    from .config import VERIFIER_TIERS
    head = transcript[:-keep_tail]
    tail = transcript[-keep_tail:]
    try:
        summary = ask("Transcript so far:\n\n" + head, system=_SUMMARY_SYS,
                      tiers=tiers or VERIFIER_TIERS).text.strip()
    except Exception:  # noqa: BLE001 — if summarization fails, fall back to truncation
        summary = head[:1500] + " …[older context truncated]"
    if verbose:
        print(f"[compact] {len(transcript)} → ~{len(summary)+len(tail)} chars")
    return (f"[COMPACTED EARLIER CONTEXT — summary of work before the recent steps]\n"
            f"{summary}\n\n[RECENT STEPS — verbatim]\n{tail}")

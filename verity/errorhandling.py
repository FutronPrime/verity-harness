#!/usr/bin/env python3
"""ErrorHandlingProtocol — structured, root-cause-first error handling + self-heal.

The search-returned-garbage bug proved the harness needs a QC layer that CATCHES a bad result
and reacts, instead of feeding noise downstream. This is it. Every handled failure produces
FIVE blocks — What / Why (root cause) / Impact / Fix / Prevention — runs a "Did I cause this?"
self-check, and journals with a timestamp. The Prevention block feeds a safeguard back so the
same failure can't recur silently.

Spec (DJ, 2026-06-14): ⚠️ prefix, WHY-before-FIX, 5-Whys when useful, case-insensitive triggers,
journal every error. Prefs: why=always|smart|off, postmortem=brief|standard|detailed.
"""
from __future__ import annotations

import os
import pathlib
import time

JOURNAL = pathlib.Path(os.path.expanduser("~/.verity-harness/error_journal.md"))

# Markers that mean a tool/step produced a FAILURE result the harness must not trust.
_FAIL = ("no results", "error:", "captcha", "complete the following challenge", "bots use",
         "unavailable", "rate limit", "403", "402", "timed out", "timeout", "no real evidence",
         "[research:", "structured parse failed", "traceback", "refusing", "not installed")


def looks_like_failure(tool_output: str) -> bool:
    """QC detector: did this tool/step output actually FAIL (so the protocol should fire)?
    Case-insensitive, per spec. Empty/tiny output counts as failure too."""
    t = (tool_output or "").lower()
    return len(t.strip()) < 20 or any(m in t for m in _FAIL)


def handle(what: str, why: str = "", impact: str = "", fix: str = "", prevention: str = "",
           self_caused: bool | None = None, postmortem: str = "standard",
           journal: bool = True) -> str:
    """Build the 5-block structured error report (WHY before FIX), journal it, return it.
    `self_caused` answers the mandatory 'Did I cause this?' self-check."""
    sc = ("yes — my own action/assumption triggered it" if self_caused
          else "no — external/environmental cause" if self_caused is False
          else "unknown — investigate before fixing")
    parts = [
        "⚠️ **ErrorHandlingProtocol Invoked** ⚠️",
        f"**1. What Happened** — {what}",
        f"**2. Why It Happened (Root Cause)** — {why or '(run a 5-Whys trace: ask why x5)'}",
        f"   • Did I cause this? → {sc}",
        f"**3. Impact** — {impact or '(state effect on user/system state)'}",
        f"**4. Fix** — {fix or '(immediate correction applied/suggested)'}",
        f"**5. Prevention** — {prevention or '(safeguard/protocol update so it cannot recur)'}",
    ]
    if postmortem == "brief":
        parts = [parts[0], parts[1], parts[2], parts[6]]
    report = "\n".join(parts)
    if journal:
        try:
            JOURNAL.parent.mkdir(parents=True, exist_ok=True)
            with open(JOURNAL, "a") as f:
                f.write(f"\n## {time.strftime('%Y-%m-%dT%H:%M:%S')}\n{report}\n")
        except OSError:
            pass
    return report


if __name__ == "__main__":
    # demo / self-test
    print(handle(
        what="research() fed the model only error text (GitHub/Reddit/DDG all failed)",
        why="web_search sent a 'verity-harness' UA → DDG CAPTCHA; GitHub unauth rate-limited. "
            "5-Whys: weak evidence → because search empty → because UA flagged + no key → because "
            "the free path is bot-blocked → because we never QC'd tool output before using it.",
        impact="4B harness arm scored WORSE than naive (garbage-in); eval lift was negative.",
        fix="Wired Brave search (key present), added _is_garbage() QC filter, honest-failure signal.",
        prevention="research() now drops garbage blocks + returns explicit failure; "
                   "looks_like_failure() lets gates self-heal instead of trusting noise.",
        self_caused=True))

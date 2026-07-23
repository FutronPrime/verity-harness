#!/usr/bin/env python3
"""error_protocol.py — VERITY's UNIVERSAL ErrorHandlingProtocol ⚠️. Wrap ANY tool, system, or LLM
connection so every failure is handled with structured clarity + self-healing, not a bare stack trace.

WHY (DJ, 2026-07-23): "apply error handling universally — the whole VERITY system, and any LLM
connection — so it explains WHAT went wrong and WHY, self-checks, and updates a safeguard so it
won't recur." (Public/ORION build; the FUTRON/AVANI build mirrors it: `futron-error-protocol`.)

Every handled error yields FIVE blocks:
  1. What Happened            2. Why It Happened (Root Cause, 5-whys)   3. Impact
  4. Fix (applied/suggested)  5. Prevention (safeguard so it won't recur)
Rules: prepend "⚠️ ErrorHandlingProtocol Invoked ⚠️"; put root-cause BEFORE the fix; auto self-check
"did I cause this? why?"; journal every error (timestamp + correction path) to memory_journal.md.

Usage:
  from verity.error_protocol import protocol, handle_error, guard
  with protocol("LLM call to kimi-k3"):      # context manager — any exception → 5-block report + journal
      risky()
  rep = handle_error("parsing X", exc, fix="...", prevention="...")   # direct
  safe = guard("fetch transcript")(fetch_fn)  # decorator
Pure stdlib; portable. `/prefs why always|smart|off` and `postmortem brief|standard|detailed` honored
via env VERITY_WHY / VERITY_POSTMORTEM.
"""
from __future__ import annotations
import functools
import os
import pathlib
import traceback

_JOURNAL = pathlib.Path.home() / ".verity-harness" / "memory_journal.md"
_BANNER = "⚠️ **ErrorHandlingProtocol Invoked** ⚠️"


def _now() -> str:
    try:
        import datetime
        return datetime.datetime.now().isoformat(timespec="seconds")
    except Exception:
        return "unknown-time"


def _why_mode() -> str:
    return os.getenv("VERITY_WHY", "always").lower()      # always | smart | off


def _postmortem() -> str:
    return os.getenv("VERITY_POSTMORTEM", "standard").lower()  # brief | standard | detailed


def five_whys(error, self_caused_hint: str = "") -> str:
    """Lightweight root-cause trace. 'brief' = one line; 'detailed' = include the traceback tail."""
    base = str(error).strip().splitlines()[0] if str(error).strip() else "unspecified failure"
    if _postmortem() == "brief":
        return base
    chain = (f"{base} → an input/state/dependency was not what the code assumed → "
             f"{self_caused_hint or 'the assumption was unvalidated'} → no guard caught it earlier → "
             f"no safeguard existed for this case yet.")
    if _postmortem() == "detailed":
        tb = traceback.format_exc()
        if tb and "NoneType: None" not in tb:
            chain += "\nTraceback tail:\n" + "\n".join(tb.strip().splitlines()[-4:])
    return chain


def _journal(context: str, blocks: dict) -> None:
    try:
        line = (f"\n### {_BANNER.replace('**','')} {_now()} — {context}\n"
                + "\n".join(f"- **{k}:** {v}" for k, v in blocks.items()) + "\n")
        _JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with open(_JOURNAL, "a") as f:
            f.write(line)
    except Exception:
        pass


def handle_error(context: str, error, *, root_cause: str = "", impact: str = "",
                 fix: str = "", prevention: str = "", self_check: bool = True,
                 researcher=None) -> dict:
    """Produce the 5-block report for a failure in `context`, journal it, return {report, blocks}.
    self_check runs a 'did WE cause this?' pass; researcher(context, error) may return a note used to
    enrich the Fix (e.g. look up an API's real schema — the never-quit / research-before-concluding gate)."""
    self_caused = ""
    if self_check:
        s = (type(error).__name__ + " " + str(error)).lower()
        ours = any(k in s for k in ("keyerror", "attributeerror", "typeerror", "indexerror", "index",
                                    "unbound", "valueerror", "no such", "not found", "nonetype",
                                    "parse", "json", "decode"))
        self_caused = ("likely OURS (config/parsing/assumption on our side)" if ours
                       else "likely EXTERNAL (dependency/model/network) — but verify before blaming it")
    note = ""
    if researcher and not fix:
        try:
            note = researcher(context, error) or ""
        except Exception:
            note = ""
    blocks = {
        "What Happened": f"{context}: {str(error).splitlines()[0] if str(error) else 'failed'}.",
        "Why It Happened (Root Cause)": root_cause or five_whys(error, self_caused),
        "Impact": impact or "This step could not complete; downstream work is blocked until corrected.",
        "Fix": fix or (f"{note} " if note else "") + "Correct the assumption/field/timeout at the source; "
               "retry ≥2 concrete approaches before declaring it unfixable (never-quit gate).",
        "Prevention": prevention or "Add a guard for this case + record it here so the same obstacle "
                      "can't recur silently (self-evolving: fix the tool, don't circumvent).",
    }
    if _why_mode() == "off":
        blocks.pop("Why It Happened (Root Cause)", None)
    _journal(context, blocks)
    report = _BANNER + "\n" + "\n".join(f"**{k}:** {v}" for k, v in blocks.items())
    return {"report": report, "blocks": blocks, "self_caused": self_caused}


class protocol:
    """Context manager: any exception inside → 5-block report + journal, then re-raised (or swallowed
    with suppress=True). `with protocol('LLM call to X'): ...`"""
    def __init__(self, context: str, *, researcher=None, suppress: bool = False):
        self.context, self.researcher, self.suppress = context, researcher, suppress
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None:
            return False
        self.result = handle_error(self.context, exc, researcher=self.researcher)
        return self.suppress  # True → swallow after reporting; False → re-raise


def guard(context: str, *, researcher=None, default=None):
    """Decorator: wrap any function so failures are reported (5-block + journal) and return `default`
    instead of crashing the whole run. Use for LLM-connection calls, tool subprocesses, parsers, etc."""
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **k):
            try:
                return fn(*a, **k)
            except Exception as e:
                handle_error(f"{context} [{fn.__name__}]", e, researcher=researcher)
                return default
        return wrap
    return deco


if __name__ == "__main__":
    with protocol("demo LLM call", suppress=True):
        raise KeyError("choices")
    print("journaled to", _JOURNAL)

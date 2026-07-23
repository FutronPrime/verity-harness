#!/usr/bin/env python3
"""persona.py — VERITY's persona resolver: ADDITIVE, never an override.

WHY (DJ, 2026-07-23): "ORION should COMPLIMENT the user's existing pre-prompts/system, not override
their presets — e.g. I run AVANI, so it must not clobber that. But if the user/LLM has NO persona
(most won't), ORION becomes the default primary persona to integrate into their system."

CONTRACT:
  • If the user ALREADY has a persona (their AVANI/custom system prompt), it stays PRIMARY. VERITY only
    APPENDS its discipline gates (research-before-concluding, never-quit, humans-merge, omission-over-
    fabrication) — those are behavior discipline, not personality, so they're safe to add to anyone's.
  • If the user has NO persona, ORION becomes the default primary persona (still + the gates).
  • VERITY NEVER replaces or edits a user's persona. Detection is opt-in-respecting and non-destructive.

Resolution of the user's persona (first hit wins):
  1. env  VERITY_USER_PERSONA          (inline text)
  2. env  VERITY_USER_PERSONA_FILE     (path)
  3. file ~/.verity-harness/persona.md
  4. mascot.json {"persona": "..."} or {"persona_file": "..."}
ORION core (default when none of the above):
  env VERITY_ORION_CORE_FILE, else ./ORION_CORE.md, else ~/.verity-harness/ORION_CORE.md, else a
  minimal inline stub. ORION is designed to EVOLVE with the user (see ORION OS).

Use `resolve_persona()` to get the effective system-prompt layer; `has_user_persona()` to check.
Pure stdlib; portable.
"""
from __future__ import annotations
import os
import pathlib

_HOME = pathlib.Path.home()

# VERITY discipline gates — additive to ANY persona (they shape behavior, not identity).
VERITY_GATES = (
    "\n\n[VERITY discipline — applies on top of the persona above]\n"
    "- Research before concluding: never assert a negative ('no X', 'not possible', 'can't') until you've "
    "actually investigated (logs, docs, source, the web).\n"
    "- Never quit/skip: try >=2 concrete approaches + look for an existing tool before saying it can't be done.\n"
    "- Humans merge: never take the irreversible action (commit/deploy/delete/send) without human sign-off.\n"
    "- Omission over fabrication: if unknown, say so; never invent facts, results, or citations."
)

_ORION_STUB = (
    "You are ORION — a capable, adaptive AI operating companion. Clear, technical, direct; you adapt "
    "your register to the user and evolve with them over time. You challenge weak ideas to sharpen them, "
    "and you never fabricate. (This is the default persona; a user's own persona always takes precedence.)"
)


def _read(path) -> str:
    try:
        return pathlib.Path(os.path.expanduser(str(path))).read_text(errors="ignore").strip()
    except Exception:
        return ""


def _mascot_persona() -> str:
    try:
        import json
        j = json.loads((_HOME / ".verity-harness" / "mascot.json").read_text())
        if j.get("persona"):
            return str(j["persona"]).strip()
        if j.get("persona_file"):
            return _read(j["persona_file"])
    except Exception:
        pass
    return ""


def user_persona() -> str:
    """The user's OWN persona, if they have one. Empty string if none — respects their presets."""
    return (os.getenv("VERITY_USER_PERSONA", "").strip()
            or _read(os.getenv("VERITY_USER_PERSONA_FILE", ""))
            or _read(_HOME / ".verity-harness" / "persona.md")
            or _mascot_persona())


def has_user_persona() -> bool:
    return bool(user_persona())


def orion_core() -> str:
    """ORION default persona (evolves with the user). Bundled/config file, else a minimal stub."""
    for src in (os.getenv("VERITY_ORION_CORE_FILE", ""),
                pathlib.Path(__file__).resolve().parent.parent / "ORION_CORE.md",
                _HOME / ".verity-harness" / "ORION_CORE.md"):
        t = _read(src)
        if t:
            return t
    return _ORION_STUB


def resolve_persona(limit: int = 8000) -> dict:
    """Return the EFFECTIVE persona layer. Never overrides a user's persona.
    -> {"primary": <text>, "source": "user"|"orion", "system": <persona + VERITY gates>}"""
    up = user_persona()
    if up:
        primary, source = up, "user"           # their persona stays primary — ORION does NOT replace it
    else:
        primary, source = orion_core(), "orion"  # no persona present → ORION is the default primary
    system = (primary[:limit] + VERITY_GATES)
    return {"primary": primary[:limit], "source": source, "system": system}


if __name__ == "__main__":
    r = resolve_persona()
    print(f"persona source: {r['source']}  (user_persona present: {has_user_persona()})")
    print("--- effective system layer (head) ---")
    print(r["system"][:600])

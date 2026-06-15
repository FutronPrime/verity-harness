#!/usr/bin/env python3
"""Decision ledger — the harness's auditable RECEIPT.

The hard question: "prove the harness is actually being used, and prove it changes the
outcome." This is the answer. Every gate writes one append-only line when it fires, tagged
with what triggered it and what it found. Reading the ledger back shows, concretely:

  • USAGE  — the gates fired (search/verify/reuse events exist, with timestamps + queries).
  • EFFECT — assumption → search → CORRECTION transitions (a claim that would have been wrong
             got caught and fixed because a gate forced a lookup). That delta IS the proof.

Without this, "the harness helped" is a vibe. With it, it's a log you can audit and A/B.
Zero deps; one JSONL file per day under ~/.verity-harness/ledger/.
"""
from __future__ import annotations

import json
import os
import pathlib
import time

LEDGER_DIR = pathlib.Path(os.path.expanduser("~/.verity-harness/ledger"))

# canonical gate names (so summaries are stable)
SEARCH = "search-before-concluding"   # rule 6 fired: went to find a solution
REUSE = "reuse-check"                  # rule 5: checked own/existing before building
VERIFY = "verify"                      # rule 1: checked a claim against reality
CALIBRATE = "calibrate"               # challenged a confident conclusion
PERSIST = "persist"                    # rule 2: refused to quit, took another path
ASSUMPTION_CAUGHT = "assumption-caught"  # a would-be wrong claim got corrected


def _path() -> pathlib.Path:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    return LEDGER_DIR / (time.strftime("%Y-%m-%d") + ".jsonl")


def log(gate: str, trigger: str = "", detail: str = "", verdict: str = "",
        evidence: str = "", run: str = "") -> dict:
    """Append one ledger event. verdict ∈ {VERIFIED, GUESS, CORRECTED, FOUND, NONE}."""
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "run": run, "gate": gate,
           "trigger": trigger[:200], "detail": detail[:400], "verdict": verdict,
           "evidence": evidence[:300]}
    try:
        with open(_path(), "a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass
    return rec


def _read(days: int = 1) -> list[dict]:
    out = []
    for i in range(days):
        p = LEDGER_DIR / (time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400)) + ".jsonl")
        if p.exists():
            for line in p.read_text().splitlines():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def proof(days: int = 1) -> str:
    """Human-readable receipt: did the harness fire, and did it catch anything?"""
    ev = _read(days)
    if not ev:
        return ("VERITY ledger empty — no gate has fired yet. Run a task through the scaffold "
                "(python3 -m verity solve ...) or call verity.ledger.log() from your gates.")
    tally: dict[str, int] = {}
    for e in ev:
        tally[e["gate"]] = tally.get(e["gate"], 0) + 1
    caught = [e for e in ev if e["gate"] == ASSUMPTION_CAUGHT or e["verdict"] == "CORRECTED"]
    searches = [e for e in ev if e["gate"] == SEARCH]
    guesses = sum(1 for e in ev if e["verdict"] == "GUESS")
    verified = sum(1 for e in ev if e["verdict"] == "VERIFIED")
    lines = [f"VERITY RECEIPT — last {days}d ({len(ev)} gate events)", "─" * 52]
    for g, c in sorted(tally.items(), key=lambda x: -x[1]):
        lines.append(f"  {c:>4}×  {g}")
    lines += ["─" * 52,
              f"  claims tagged: {verified} VERIFIED / {guesses} GUESS",
              f"  proactive searches (rule 6): {len(searches)}",
              f"  assumptions CAUGHT + corrected: {len(caught)}"]
    if caught:
        lines.append("\n  ▸ corrections (the difference, made visible):")
        for e in caught[-5:]:
            lines.append(f"    • {e['trigger']} → {e['evidence'] or e['detail']}")
    lines.append("\n  This is the audit trail. No gate events = harness wasn't used.")
    return "\n".join(lines)


def playbook(days: int = 30) -> str:
    """Distill an INJECTABLE behavioral playbook from this harness's own verified history — the
    'make any model think like Fable' move (recreate-fable technique, 2026-06-15): mine what the
    model got WRONG and how a gate FIXED it, plus what already EXISTED so it doesn't rebuild, and
    feed those hard-won lessons back in at session start. Capability lives in the workflow + the
    accumulated corrections, not just the weights. `verity playbook --inject` writes it to
    ~/.verity-harness/playbook.md, which the autostart context-inject appends every session."""
    ev = _read(days)
    seen_c, corrections, seen_r, reuses = set(), [], set(), []
    for e in ev:
        v = (e.get("verdict") or "").upper()
        trig = (e.get("trigger") or "").strip()
        eviden = (e.get("evidence") or e.get("detail") or "").strip()
        if not trig:
            continue
        if v in ("CORRECTED", "WRONG", "GUESS") and trig not in seen_c:
            seen_c.add(trig); corrections.append((trig, eviden))
        elif v in ("FOUND", "REUSED") and trig not in seen_r:
            seen_r.add(trig); reuses.append((trig, eviden))
    if not corrections and not reuses:
        return ("[VERITY PLAYBOOK — empty so far. It fills as the gates catch + correct things across "
                "your sessions. Run real work through `verity solve`, then `verity playbook --inject`.]")
    out = ["[VERITY PLAYBOOK — lessons distilled from THIS system's own verified history.",
           "Apply them proactively; do not relearn them the hard way.]"]
    if corrections:
        out.append("\n● Assumptions that were WRONG before (don't repeat — the truth is on the right):")
        for t, e in corrections[-12:]:
            out.append(f"   ✗ you thought: {t[:120]}" + (f"\n     ✓ actual: {e[:160]}" if e else ""))
    if reuses:
        out.append("\n● Things that ALREADY EXIST here (reuse, don't rebuild):")
        for t, e in reuses[-10:]:
            out.append(f"   ♻ {t[:90]}" + (f" → {e[:120]}" if e else ""))
    return "\n".join(out)


def write_playbook(days: int = 30) -> pathlib.Path:
    p = pathlib.Path(os.path.expanduser("~/.verity-harness/playbook.md"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(playbook(days))
    return p


if __name__ == "__main__":
    import sys
    d = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1
    print(proof(d))

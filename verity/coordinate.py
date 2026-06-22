#!/usr/bin/env python3
"""Coordination learning — the self-generating ROUTING cheat-sheet (Gap #4's 'learn' half).

The thesis (The Architect, 2026-06-22): training is just "learning how to respond." If you hand the
model a cheat-sheet of what worked and make it review it before each task, it performs roughly as if
trained on that — without touching weights. This is in-context learning, and it's how a prompt-software
orchestrator approximates Fugu's RL-evolved coordinator: the Conductor bakes coordination strategy into
weights over many trials; this bakes it into a TEXT cheat-sheet distilled from the harness's own runs,
re-injected before every plan. Most of a coordinator's value is verbalizable ("route verification to a
different model than generation"; "for research-then-synthesize goals, fan out then converge") — and
anything verbalizable is cheat-sheet-able. The residue that ISN'T verbalizable (or searchable) is the
only weights-only sliver, and for a frontier base it's small.

This pairs with `ledger.playbook()` (which distills DISCIPLINE lessons): same engine, aimed at ROUTING.
It reads the swarm's own ledger receipts — which decompositions synthesized cleanly, which sub-tasks the
critic kept correcting, which nodes had to recurse — and writes a compact, size-bounded heuristics block.
`swarm._agent` prepends it to the planner prompt, so the orchestrator literally reviews the cheat-sheet
before producing each plan. Zero cost when empty (a fresh install has no history yet — it fills as you run).

  python3 -m verity coordinate            # show the current learned routing cheat-sheet
  python3 -m verity coordinate --promote  # distill from recent ledger → ~/.verity-harness/routing.md
"""
from __future__ import annotations

import os
import pathlib
import re

ROUTING_FILE = pathlib.Path(os.path.expanduser("~/.verity-harness/routing.md"))
MAX_CHARS = 2000          # a cheat-sheet, not an essay — must stay small enough to prepend every plan

_REPAIRED = re.compile(r"(\d+)\s+repaired")
_NODES = re.compile(r"(\d+)\s+(?:nodes|sub-tasks)")


def distill_routing(days: int = 30, max_chars: int = MAX_CHARS, events=None) -> str:
    """Mine the swarm's ledger receipts into a routing cheat-sheet. `events` is injectable for tests;
    defaults to the live ledger. Returns '' when there's no usable history (zero-cost on fresh installs)."""
    if events is None:
        try:
            from . import ledger
            events = ledger._read(days)
        except Exception:  # noqa: BLE001
            events = []

    worked: list[tuple[str, str]] = []      # (goal, shape) that synthesized cleanly (0 repaired)
    rough: list[tuple[str, int]] = []       # (goal, repaired) that needed several corrections
    plan_shape: dict[str, str] = {}         # goal → decomposition detail (from swarm-plan)
    correct_triggers: list[str] = []        # sub-tasks the critic CORRECTED
    escalations: list[str] = []             # sub-tasks that had to recurse

    seen_w, seen_c = set(), set()
    for e in events:
        gate = e.get("gate", "")
        trig = (e.get("trigger") or "").strip()
        if gate == "swarm-plan":
            plan_shape[trig[:80]] = (e.get("detail") or "").strip()
        elif gate == "swarm-synth":
            ev = e.get("evidence") or ""
            rep_m = _REPAIRED.search(ev)
            repaired = int(rep_m.group(1)) if rep_m else 0
            shape = plan_shape.get(trig[:80], "")
            if repaired == 0 and trig and trig not in seen_w:
                seen_w.add(trig); worked.append((trig, shape))
            elif repaired >= 2:
                rough.append((trig, repaired))
        elif gate == "swarm-critic" and (e.get("verdict") or "").upper() == "CORRECTED":
            if trig and trig not in seen_c:
                seen_c.add(trig); correct_triggers.append(trig)
        elif gate == "swarm-recurse":
            if trig:
                escalations.append(trig)

    if not (worked or correct_triggers or escalations or rough):
        return ""

    out = ["[VERITY ROUTING CHEAT-SHEET — learned from THIS harness's own swarm runs.",
           " Review before decomposing. These are empirical, not theory — prefer them.]"]
    if worked:
        out.append("\n● Decompositions that synthesized CLEANLY (0 repairs) — reuse these shapes:")
        for g, shape in worked[-6:]:
            tail = f"  [{shape}]" if shape else ""
            out.append(f"   ✓ {g[:96]}{tail}")
    if correct_triggers:
        out.append("\n● Sub-task kinds the Verifier kept CORRECTING — plan extra care / front-load "
                   "research / isolate them as their own node:")
        for t in correct_triggers[-6:]:
            out.append(f"   ⚠ {t[:104]}")
    if escalations:
        out.append("\n● Sub-tasks that needed RECURSION (a single pass wasn't enough) — score these "
                   "complexity ≥8 up front so they recurse immediately, don't waste a flat pass:")
        for t in escalations[-5:]:
            out.append(f"   ↻ {t[:104]}")
    text = "\n".join(out)
    if len(text) > max_chars:                # hard size budget — a cheat-sheet must stay promptable
        text = text[:max_chars].rsplit("\n", 1)[0] + "\n   …(truncated to size budget)"
    return text


def learned_routing() -> str:
    """The cheat-sheet to inject before a plan: the PROMOTED file if present (gated, stable), else a
    fresh distillation from recent ledger, else '' (fresh install). Bounded; never raises."""
    try:
        if ROUTING_FILE.exists():
            txt = ROUTING_FILE.read_text().strip()
            if txt:
                return txt[:MAX_CHARS]
    except OSError:
        pass
    try:
        return distill_routing(days=14)
    except Exception:  # noqa: BLE001
        return ""


def promote_routing(days: int = 30) -> tuple[bool, str]:
    """Distill recent history → write ~/.verity-harness/routing.md, gated: must be non-empty and within
    the size budget (additive, so the gate is lighter than evolve.py's coverage check). Returns (ok, msg)."""
    cand = distill_routing(days)
    if not cand:
        return False, "no swarm history yet — run `verity swarm` on real goals first, then promote"
    if len(cand) > MAX_CHARS:
        return False, f"over size budget ({len(cand)}>{MAX_CHARS})"
    try:
        ROUTING_FILE.parent.mkdir(parents=True, exist_ok=True)
        ROUTING_FILE.write_text(cand)
    except OSError as e:
        return False, f"could not write {ROUTING_FILE}: {e}"
    return True, f"promoted routing cheat-sheet ({len(cand)} chars) → {ROUTING_FILE}"


if __name__ == "__main__":
    import sys
    if "--promote" in sys.argv:
        ok, msg = promote_routing()
        print(("✓ " if ok else "✗ ") + msg)
    else:
        cs = learned_routing()
        print(cs or "[routing cheat-sheet empty — fills as you run `verity swarm` on real goals]")

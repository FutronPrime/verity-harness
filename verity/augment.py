#!/usr/bin/env python3
"""`verity augment` — make a WEAK local model produce FRONTIER-grade plans by orchestrating,
not by reasoning alone. The harness-over-model thesis, operationalized.

A 3B local model (qwen2.5:3b, free, private, offline) is a poor deep reasoner but a fine
CONDUCTOR. So we gate it: it is NOT allowed to deep-reason a complex plan from its own priors —
it must (1) frame the task, (2) ESCALATE the heavy reasoning to a stronger free backend (Gemini
via the VERITY router, or any reasoner you pass), optionally (3) pull current context, and
(4) synthesize the final plan. The output quality tracks the REASONER; the entry point stays
local/cheap/sovereign. That's how you get Mythos-grade output from a small model.

  python3 -m verity augment "design a comprehensive plan to <goal>"

Pass --driver/--reasoner ids to override; defaults route through VERITY tiers (driver = local
tier0 if up, reasoner = best available tier).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field


@dataclass
class Plan:
    task: str
    framing: str = ""          # what the driver decided needs reasoning/research
    research: str = ""         # current context (optional)
    reasoning: str = ""        # the frontier reasoner's deep plan
    final: str = ""            # the driver's synthesized, formatted plan
    trail: list = field(default_factory=list)


_FRAME = (
    "You are the CONDUCTOR of a planning task — a small fast model whose job is to ORCHESTRATE, "
    "not to deep-reason alone. For this goal, list (a) the 3-6 hardest sub-questions that need "
    "careful reasoning, and (b) what current information would help. Be terse — bullet points only.\n\n"
    "GOAL:\n{task}")

_REASON = (
    "You are the expert REASONER. Produce a COMPREHENSIVE, high-reasoning plan for the goal below. "
    "Address each hard sub-question, give a concrete step-by-step workflow, name risks + mitigations, "
    "and call out what to verify. Be thorough and specific — this is the substance the conductor will "
    "deliver.\n\nGOAL:\n{task}\n\nHARD SUB-QUESTIONS THE CONDUCTOR FLAGGED:\n{framing}"
    "{research_block}")

_SYNTH = (
    "You are the conductor. Format the expert's plan below into the final deliverable for the user: "
    "a clear title, a 1-2 line summary, then the phased workflow with checkboxes, risks, and a "
    "'verify' line per phase. Do not add new claims; organize and tighten what the expert produced.\n\n"
    "GOAL:\n{task}\n\nEXPERT PLAN:\n{reasoning}")


def augment_plan(task: str, *, driver, reasoner, search=None) -> Plan:
    """driver(prompt)->str is the weak/local conductor; reasoner(prompt)->str is the strong free
    backend; search(query)->str is optional (current context). All injectable for tests."""
    p = Plan(task=task)

    # 1. CONDUCT — the local model frames what's hard (cheap, local).
    p.framing = driver(_FRAME.format(task=task)).strip()
    p.trail.append("driver:framed")

    # 2. RESEARCH (optional) — pull current context so the plan isn't from stale priors.
    research_block = ""
    if search is not None:
        try:
            p.research = (search(task) or "").strip()
            if p.research:
                research_block = f"\n\nCURRENT CONTEXT (researched):\n{p.research[:2000]}"
                p.trail.append("research:ok")
        except Exception:
            p.trail.append("research:skip")

    # 3. ESCALATE — the heavy reasoning goes to the strong free backend (the gate: a 3B must NOT
    #    deep-reason a complex plan alone).
    p.reasoning = reasoner(_REASON.format(task=task, framing=p.framing,
                                          research_block=research_block)).strip()
    p.trail.append("reasoner:planned")

    # 4. SYNTHESIZE — the local conductor formats the deliverable (cheap, local).
    try:
        p.final = driver(_SYNTH.format(task=task, reasoning=p.reasoning)).strip()
        p.trail.append("driver:synthesized")
    except Exception:
        p.final = p.reasoning           # graceful: ship the expert plan if synth fails
        p.trail.append("driver:synth-failed→raw")
    return p


# ── default backends via VERITY tiers ────────────────────────────────────────
def _tier_caller(predicate):
    from .router import chat
    from .config import TIERS
    tier = next((t for t in TIERS if predicate(t)), TIERS[0])
    return lambda prompt: chat([{"role": "user", "content": prompt}], tiers=[tier]).text


# ── FULLY-PRIVATE mode: conductor + reasoner BOTH local open-weights, zero enterprise ────────
_SIZE = re.compile(r"[:\-](\d+(?:\.\d+)?)\s*b", re.I)

def _ollama_models(base="http://127.0.0.1:11434"):
    """List local Ollama chat models, largest first (by param count parsed from the tag)."""
    import json as _j, urllib.request as _u
    try:
        d = _j.loads(_u.urlopen(base + "/api/tags", timeout=5).read())
    except Exception:
        return []
    models = []
    for m in d.get("models", []):
        name = m.get("name", "")
        if "embed" in name.lower():
            continue
        mt = _SIZE.search(name)
        models.append((float(mt.group(1)) if mt else 0.0, name))
    return [n for _, n in sorted(models, reverse=True)]

def _ollama_caller(model, base="http://127.0.0.1:11434"):
    import json as _j, urllib.request as _u
    def call(prompt):
        body = _j.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                         "stream": False}).encode()
        r = _u.urlopen(_u.Request(base + "/api/chat", body, {"Content-Type": "application/json"}), timeout=180)
        return _j.loads(r.read())["message"]["content"]
    return call

def private_backends():
    """Return (driver, reasoner) BOTH local — smallest model conducts, largest reasons. No cloud."""
    models = _ollama_models()
    if not models:
        raise RuntimeError("no local Ollama models found — `ollama pull qwen2.5:32b-instruct` (reasoner) "
                           "and a small one (e.g. qwen2.5:3b) for the conductor.")
    reasoner = models[0]                    # strongest local
    driver = models[-1] if len(models) > 1 else models[0]   # smallest local (or same)
    return _ollama_caller(driver), _ollama_caller(reasoner), driver, reasoner


def _cli(argv: list) -> int:
    if not argv:
        print('usage: verity augment "<complex planning goal>"', file=sys.stderr); return 2
    task = " ".join(a for a in argv if not a.startswith("--"))
    private = "--private" in argv or "--local" in argv
    if private:
        # FULL PRIVACY: conductor + reasoner BOTH local open-weights, zero enterprise.
        driver, reasoner, dn, rn = private_backends()
        print(f"# PRIVATE mode — conductor: {dn} · reasoner: {rn} (all local, no enterprise)\n", file=sys.stderr)
    else:
        # driver = local tier if present, else first tier; reasoner = first (strongest) tier.
        driver = _tier_caller(lambda t: t.protocol == "ollama")
        reasoner = _tier_caller(lambda t: t.protocol != "ollama")
    # ground the plan in LIVE web research (multi-provider failover) — the model refers to the web
    # FIRST, so the plan isn't built from stale priors. Degrades to no-context if search is down.
    try:
        from .websearch import as_context as _search
    except Exception:
        _search = None
    p = augment_plan(task, driver=driver, reasoner=reasoner, search=_search)
    print(f"# Augmented plan (trail: {' → '.join(p.trail)})\n")
    print(p.final)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

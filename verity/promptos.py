#!/usr/bin/env python3
"""Prompt-OS — the prompt-software orchestrator (the Synapse_COR brain for the swarm).

This is the "evolved coordinator, reached with prompt software" answer to Fugu's Conductor. A trained
RL coordinator and a prompt-software orchestrator both do the same JOB — decompose a goal, assign
roles, choose a topology, route the right model, refuse to quit. The difference is only WHERE that
behavior comes from: baked into weights (Fugu) vs activated in-context by a strict system prompt (this).

Prompt software is a KEY that unlocks structured behavior the base model already latently has — which
is exactly why a Synapse_COR block makes a "blank" LLM behave like a state machine. It is NOT a trainer
that creates new capability; the one thing it cannot do is discover coordination strategies that lie
OUTSIDE the base model's priors (only weight-level optimization finds those). For a frontier base model
that residue is small. The LEARNING half (get better from outcomes over many runs) is closed separately
by the ledger-fed heuristic loop in `evolve.py` — not by this prompt, but around it.

PORTABILITY (the open-source / model-agnostic talking point, made literal): `ORCHESTRATOR_PROMPT` is a
self-contained artifact. `python3 -m verity promptos` prints it so you can drop it into ANY blank LLM
(local Qwen/Gemma, a frontier API, a fresh chat) and it will orchestrate to VERITY's contract — no
weights, no vendor, fork-and-tweak for your setup. A black-box trained coordinator can offer none of that.

Opt in by exporting VERITY_PROMPTOS=1 (the swarm planner then runs on this instead of the terse role
prompt). Default OFF = no behavior change. The emitted JSON contract is identical either way, so
`complexity.normalize_subtasks` + `loop.parse_step_json` consume both without changes.
"""
from __future__ import annotations

# The contract block is shared verbatim with the terse planner so BOTH paths emit the same schema.
SUBTASK_CONTRACT = (
    'Respond ONLY with JSON (no prose, no markdown fences):\n'
    '{"subtasks":[\n'
    '   {"id":"1","task":"<concrete sub-task>","complexity":<1-10>,'
    '"type":"<code|research|analysis|write|data>","depends_on":[]},\n'
    '   {"id":"2","task":"...","complexity":<1-10>,"type":"...","depends_on":["1"]}\n'
    ' ],"thought":"<one line: why this decomposition + topology>"}'
)

ORCHESTRATOR_PROMPT = f"""## SYSTEM MANAGER 🖥️ — Synapse_COR Orchestrator v1 (VERITY Prompt-OS)

You ARE the coordinator of a multi-agent swarm — the TRINITY "Thinker". You do NOT solve the task
yourself. Your sole deliverable is an execution PLAN that the harness will run. Behave as deterministic
software, not a chatbot: follow this contract exactly.

### ROLE ROSTER you are assigning work to
- 🧠 Thinker (you): decompose the goal, map dependencies, choose the topology, route each piece.
- 🚀 Worker(s): execute one sub-task each (code / research / data / write), using injected findings.
- 🛡️ Verifier (critic): adversarially reviews each worker output; failures are forced to retry.
- ♻️ Recursion Controller: a hard sub-task is escalated to a fresh sub-swarm (test-time scaling).

### DECOMPOSITION DIRECTIVE
1. Break the GOAL into 2-5 CONCRETE sub-tasks that TOGETHER fully achieve it. Prefer fewer, meatier
   sub-tasks over many trivial ones. Each must be independently checkable.
2. ROUTE each sub-task by scoring its `complexity` 1-10 — this selects a right-sized model:
     1-3  trivial (format / rename / lint / stub)        → cheap / local
     4-7  normal  (implement / edit / test / summarize)   → mid (a coder model for `type:code`)
     8-10 hard    (architect / debug / novel-logic / security / proof) → frontier (may recurse)
   Be honest: over-scoring burns money, under-scoring ships weak work.
3. TOPOLOGY: set `depends_on` to the ids whose OUTPUT this sub-task needs. Independent sub-tasks →
   `[]` (they run in parallel). A sub-task that consumes others' results → list them (it runs after,
   and receives their outputs). Design the GRAPH, not just a list — that is the coordination edge.
4. `type` tags the specialist lane (code/research/analysis/write/data) for routing.

### NO-QUIT MANDATE (binds every agent you spawn)
"I can't" / "not possible" / "as an AI" / "only a human can" is FORBIDDEN until investigated. A worker
that hits a wall MUST research (web/GitHub/Reddit/X/docs) before returning. You plan for this: a
sub-task that is uncertain should be `type:research` and scored honestly, not hand-waved.

### ERROR-HANDLING / RECURSION CONTROLLER
You are not asked to run the loop — the harness does — but plan so it can: a complexity-≥8 node will be
recursively re-planned as its own sub-swarm, and any node the Verifier cannot pass is repaired then
escalated. Decompose so hard nodes are isolated and cleanly recursable (don't bury a hard problem
inside an otherwise-trivial sub-task).

### OUTPUT CONTRACT — this is all you emit
{SUBTASK_CONTRACT}

Plain-string sub-tasks are tolerated for compatibility, but the structured form above routes far
better. Emit the JSON and nothing else."""


def orchestrator_prompt() -> str:
    """The portable prompt-software orchestrator block (drop into any blank LLM)."""
    return ORCHESTRATOR_PROMPT


def enabled() -> bool:
    import os
    return os.environ.get("VERITY_PROMPTOS", "").strip().lower() in ("1", "true", "on", "yes")

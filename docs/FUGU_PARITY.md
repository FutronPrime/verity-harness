# VERITY vs Sakana Fugu — what's matched, and what's a different bet

Sakana AI's **Fugu** (sakana.ai/fugu) is "a multi-agent system, delivered as one model": an
orchestrator that dynamically assembles and coordinates a pool of LLMs, assigns Thinker/Worker/
Verifier roles, and recursively calls itself on hard sub-problems. It rests on two ICLR 2026 papers:

- **TRINITY** — a lightweight *evolved* coordinator that orchestrates multiple LLMs over several
  turns, assigning Thinker / Worker / Verifier roles.
- **Conductor** — an RL-trained component that *discovers* natural-language coordination
  topologies (which agent talks to which, in what order) rather than using a hand-designed pipeline.

This page is an honest map of where VERITY (an open, zero-dependency *discipline harness*) lands
against that design. We don't claim to be Fugu. We claim to reach most of its **shape** with
engineered, auditable control flow instead of a trained coordinator — and to be sovereign and
inspectable in ways a proprietary endpoint is not.

## The scorecard

| Fugu capability | VERITY | Where |
|---|---|---|
| Multi-agent "as one model" (Thinker/Worker/Verifier) | ✅ Matched | `swarm.py`: planner → executor → critic(+repair) → synthesizer |
| Per-task **model selection** ("handles model switching for each task") | ✅ Matched (engineered) | `complexity.py` + swarm: 1-10 score → cheap/mid/frontier tier band |
| **Dynamic topology** (Conductor's discovered communication patterns) | ◑ 80/20 | planner emits a `depends_on` DAG; `run_swarm` executes it in topological waves with upstream context. *Orchestrator-proposed per prompt, not RL-discovered.* |
| **Recursion / test-time scaling** (spin a fresh instance on a hard sub-problem) | ✅ Matched | `run_swarm` recurses a fresh sub-swarm on complexity ≥8 or a stuck critic, capped by `VERITY_SWARM_MAX_DEPTH` |
| Verifier role + retry on hallucination/logic failure | ✅ Matched (stronger) | critic agent + the deterministic anti-giveup `guard.py` + the `:11500` overconfidence proxy — fires on a **code condition**, not the model's goodwill |
| Provider-agnostic pool, swap on restriction | ✅ Matched | `router.py` peer-chain failover → independent 2nd provider → sovereign local floor |
| Pre-flight research before execution | ✅ Matched | Rule 0 `_preflight`: live-searches current-best approach and injects it |
| Selective triggering (don't multi-agent a trivial query) | ✅ Matched (Fugu doesn't expose this) | `should_swarm()` — iMAD-style (arxiv 2511.11306) |
| **Evolved coordinator** (TRINITY/Conductor, RL-trained) | ◑ split: orchestrate ✅ · learn ✅ · discover ✗(thin) | `promptos.py` (orchestrator) + `coordinate.py` (learned routing cheat-sheet) — see below |

## Gap #4, split three ways (the honest version)

"Match Fugu's evolved coordinator" sounds binary, but the Conductor does three separable things.
Pull them apart and the picture is precise — not "structurally impossible," just one residual sliver:

**1. Orchestrate — decompose, assign roles, choose a topology, route models. ✅ FULLY reachable with
prompt software.** A trained coordinator and a prompt-software orchestrator do the *same job*; they
differ only in WHERE the behavior lives — baked in weights vs activated in-context by a strict system
prompt. `promptos.py` is that orchestrator (Synapse_COR): a portable prompt-software block that turns
any capable model into VERITY's planner. This is *why* dropping a Synapse_COR prompt into a "blank" LLM
makes it behave like a state machine — the prompt is a **key that unlocks** structure the model already
latently has. (`VERITY_PROMPTOS=1` runs the swarm planner on it; `python3 -m verity promptos` prints it
to paste into any model.)

**2. Learn — get measurably better at orchestrating from outcomes over many runs. ✅ BUILT, no training.**
A static prompt is stateless; it doesn't improve from running 10,000 times. But you don't need weight
updates to learn — you need a *feedback loop around* the prompt, because training is just "learned how to
respond" and a reviewed cheat-sheet activates the same response in-context. `coordinate.py` is that loop
for routing: it distills the swarm's own ledger receipts — which decompositions synthesized cleanly,
which sub-tasks the critic kept correcting, which nodes had to recurse — into a compact, size-bounded
**routing cheat-sheet**, and `swarm.py` prepends it to the planner prompt so the orchestrator *reviews
what worked before every decomposition*. (`evolve.py` does the sibling loop for discipline lessons.) It
fills as you run (`verity coordinate --promote`), empty + zero-cost on a fresh install. This is most of
the Conductor's practical *value* — it adapts to your setup and improves over time — minus the GPUs.

**3. Discover — invent coordination strategies that lie OUTSIDE the base model's reasoning priors AND
that no human has written down. ✗ Weight-level only — but a thin sliver.** A prompt asking "propose the
best topology" returns the model's best guess *from what it knows*; the cheat-sheet adds what *worked
here*; live search adds what *anyone has published*. What remains is only the strategy that is BOTH
un-searchable (no human has it) AND un-verbalizable (can't be stated as a rule, only emerges as a weight
pattern from reward over many trials). That intersection is small — almost everything useful is either
searchable (knowledge) or articulable (a heuristic) — and it shrinks as base models improve. Stated
plainly: the sliver is real, but it is a sliver, not a wall. VERITY's whole bet is that **a general
reasoner + live retrieval + a learned cheat-sheet beats a bigger model on frozen weights** — go *find*
the answer like a human does, instead of being pre-trained on it.

**The trade, concretely:**
- *Fugu's edge:* a coordinator that can invent non-obvious strategies a human didn't script — and on
  Sakana's own benchmarks, it wins (SWE-Bench Pro: Fugu Ultra 73.7).
- *VERITY's edge — and the open-source pitch:* it's **free, fully open-source, and model-agnostic**.
  The orchestrator is a prompt file you can read, fork, and tweak for *your* models, your setup, your
  use case; it routes against weights *you own*; it fails over to local models nothing can revoke; and
  every decision writes an auditable receipt (`verity proof`). A black-box trained coordinator offers
  none of that — you can't inspect it, can't run it on your own stack, can't improve it for the
  community. VERITY hands the coordination layer to the community to build on. That is the bet.

## Using the parity features

```bash
# Multi-agent swarm with the prompt-software orchestrator + complexity routing + DAG + recursion:
export VERITY_PROMPTOS=1                     # planner runs on the Synapse_COR prompt-software brain
export VERITY_COMPLEXITY_ROUTING=1          # right-size the model per sub-task
export VERITY_SWARM_MAX_DEPTH=1             # recursion budget (test-time scaling)
python3 -m verity swarm "<a complex, multi-part goal>"

# Portability — print the orchestrator to drop into ANY blank LLM (local or frontier):
python3 -m verity promptos

# The 'learn' loop — the orchestrator's self-generating routing cheat-sheet:
python3 -m verity coordinate            # show what it has learned from past runs
python3 -m verity coordinate --promote  # distill recent ledger → routing.md (reviewed before every plan)

# Wire bands to real models (look ids up live — never guess):
python3 -m verity models claude-opus        # → set VERITY_TIER_FRONTIER_MODEL
# see verity.env.example § OPTION C for the full band wiring (incl. a fable-distilled coder GGUF for code tasks)

# n8n / webhook integration — POST a goal to the always-on daemon:
curl -s -X POST http://127.0.0.1:11500/v1/swarm \
  -H 'Content-Type: application/json' -d '{"goal":"research X and design Y"}'
# (reasoning-mode only; shell execution stays CLI-side via `verity swarm --exec` for safety)
```

## Why not just clone the Fugu approach (local distilled orchestrator)?

A recurring temptation is to run a small fable/opus-*distilled* model (e.g. a 9B GGUF) as the
orchestrator. Don't put it in the **conductor seat**: a sub-2GB/9B model SFT'd on a few thousand
scraped traces overfits and loses the general reasoning a coordinator needs. The right slot for
those distilled models is as a cheap **worker** — exactly where VERITY's complexity router puts
them (`VERITY_TIER_MID_CODE_MODEL`): a frontier/32B-class brain orchestrates; the distilled coder is
muscle on routine code sub-tasks. Big brain commands; small specialists execute.

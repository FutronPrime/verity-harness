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
| **Evolved coordinator** (TRINITY trained over millions of trials) | ✗ Different bet | see below |

## The one honest gap: the *evolved* coordinator (Gap #4)

Fugu's coordinator is **trained** — TRINITY evolves a lightweight orchestrator and Conductor learns
topologies via RL over many trials. VERITY does **not** have a training pipeline, so it will not
reproduce a learned coordinator. That's a real difference, stated plainly.

What VERITY substitutes is **engineered discipline**: the orchestration is an inspectable state
machine (`scaffold.py` / `swarm.py`) whose every gate fires on a code condition and writes an
auditable receipt to the ledger. The trade is concrete:

- **Fugu's edge:** a coordinator that can invent *non-obvious* coordination strategies a human
  didn't script. On the benchmarks Sakana reports, that wins (SWE-Bench Pro: Fugu Ultra 73.7).
- **VERITY's edge:** every routing/verify/recurse decision is **legible and yours** — no proprietary
  endpoint, runs against models *you* own, fails over to local weights nothing can revoke, and you
  can read exactly why it did what it did (`verity proof`). It also runs the same discipline on a
  single local 8B as on a frontier API.

`evolve.py` already does closed-loop, gated self-improvement of the injectable *playbook* (the
discipline lessons), with a non-regression safety gate. Extending that substrate toward evolving
*routing heuristics* (which band/topology worked for which goal shape, learned from the ledger) is
the closest reachable approximation of Conductor — a roadmap item, not a claim of present parity.

## Using the parity features

```bash
# Multi-agent swarm with complexity routing + DAG + recursion:
export VERITY_COMPLEXITY_ROUTING=1          # right-size the model per sub-task
export VERITY_SWARM_MAX_DEPTH=1             # recursion budget (test-time scaling)
python3 -m verity swarm "<a complex, multi-part goal>"

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

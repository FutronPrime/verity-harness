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
| **Evolved coordinator** (TRINITY/Conductor, RL-trained) | ◑ split: orchestrate ✅ · learn ✅ · discover ✅ (search, not weights) | `promptos.py` + `coordinate.py` + `discover.py` (evolutionary strategy search) — see below |

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

**3. Discover — invent coordination strategies outside the base model's one-shot priors. ✅ Reachable
WITHOUT weight training — via search, not gradients.** Earlier drafts of this doc called this "weights
only." That was a defeatist negative — the exact assumption the harness exists to kill — and it was
wrong. Discovery does not live in the weights; it lives in a **search loop wrapped around a frozen
model**: the model *proposes/mutates* candidate strategies, a real *evaluator scores* them, and
*selection* keeps winners — exploring combinations no single forward pass would pick. The optimization
is the outer loop, not the parameters. This is a published, named field, all with **frozen** base models:
- **ADAS — Automated Design of Agentic Systems** ([arXiv 2408.08435](https://arxiv.org/abs/2408.08435)):
  a meta-agent searches *code space* to discover novel agentic systems; "doesn't require fine-tuning,"
  "invents novel design patterns" beating hand-designed baselines.
- **FunSearch** ([Nature 2023](https://www.nature.com/articles/s41586-023-06924-6)) / **AlphaEvolve**
  (DeepMind 2025): a frozen LLM as the *variation operator* in an evolutionary loop + evaluator →
  discovered genuinely new algorithms.
- **AFlow** ([arXiv 2410.10762](https://arxiv.org/pdf/2410.10762)) / **GPTSwarm** / **EvoAgentX**:
  MCTS / policy-gradient search over agent topologies and communication graphs.

`discover.py` is a focused version of this, REUSING `evolve.py`'s proven pattern (git-tagged candidate
archive + dual-gate promotion + held-out eval). It evolves a population of coordination strategies
(AFlow-style operators: flat-fanout, review-revise, debate-adjudicate, isolate-recurse, …); the frozen
swarm is the variation operator; an evaluator scores candidates on real tasks; a winner is promoted
**only on measured fitness** (never the model's say-so) and injected into the orchestrator.

The honest residual is NOT "weights vs not" — both *discover*. It's a tradeoff: weight-RL *amortizes*
the discovered strategy into instant inference + implicit generalization; search-based discovery keeps
it as an *explicit evolved artifact* and pays compute at design-time (you run the evaluator — exactly
like AlphaEvolve does). That's cost/storage, not a capability wall. VERITY's whole bet stands and is now
complete across all three: **a general reasoner + live retrieval + a learned cheat-sheet + an
evolutionary search beats a bigger model on frozen weights** — go *find/evolve* the answer like a human
(and like AlphaEvolve) does, instead of being pre-trained on it.

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

# The 'discover' loop — evolutionary search over coordination strategies (ADAS/AFlow paradigm):
python3 -m verity discover              # show the strategy bank (seeds + evolved champion)
python3 -m verity discover --propose    # frozen model mutates a new candidate strategy (no eval)
python3 -m verity discover --eval --apply   # propose → MEASURE on tasks → gate → promote the winner

# The ACQUISITION loop — go learn a subject from the open-source community, keep it (on-the-job training):
python3 -m verity learn "rust async runtimes"       # search repos/skills/docs → distill → PERSIST
python3 -m verity learn "kalman filters" --rounds 3 # iterate: a completeness critic scouts the gaps
python3 -m verity learn "rust async runtimes" --show # recall what THIS harness has already learned

# The LOOP LIBRARY — wire in Forward Future's 50+ vetted agentic-workflow recipes (Matthew Berman):
python3 -m verity looplib --sync                    # cache the catalog (signals.forwardfuture.ai)
python3 -m verity looplib "improve test coverage"   # find recipes that fit a goal
python3 -m verity looplib get overnight-docs-sweep  # full recipe: useWhen + prompt + verify + steps
python3 -m verity looplib --seed-discover           # add the vetted loops to the discovery strategy bank
# (once synced, matched recipes auto-inject into the swarm planner — REUSE-FIRST, offline-safe/cache-only)

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

## On-the-job learning: each harness becomes its OWN expert

The loop is the engine — it's on-the-job training. A human hitting a new domain doesn't get retrained;
they go find the library/repo/tutorial, absorb it, and now they know it. `learn.py` (`verity learn
"<subject>"`) does exactly that: SCOUT the web + GitHub for the best open-source skills/repos/docs on a
subject → FILTER to the highest-signal sources → ASSIMILATE (fetch + distill the reusable technique) →
SYNTHESIZE one durable note → PERSIST it to memory. A completeness critic drives extra rounds to scout
the gaps. Because it persists with `scope="lesson"`, the knowledge **recalls automatically into every
future swarm spawn** (`_context_pack`) *and* feeds the evolved playbook (`evolve` promotes lessons) — so
the consume side was already wired; this just adds the acquisition side. The result: **each user's
harness grows into its own customized expert**, learning the subjects that user actually works on, from
the community's own artifacts. That is the difference between a fixed model and a system that does its
own on-the-job training — and no proprietary endpoint can give you a *per-user* learned brain you own.

This is the same loop the broader agentic-loops movement is converging on (prior art / reuse:
[serenakeyitan/awesome-agent-loops](https://github.com/serenakeyitan/awesome-agent-loops),
[AlessandroAnnini/agent-loop](https://github.com/AlessandroAnnini/agent-loop),
[context-labs/halo](https://github.com/context-labs/halo),
[agenticloops-ai/agentic-ai-engineering](https://github.com/agenticloops-ai/agentic-ai-engineering)) —
VERITY's contribution is doing it gate-disciplined (honest failure, no hallucinated "learning") and
sovereign (the learned brain lives in *your* membank, not a vendor's).

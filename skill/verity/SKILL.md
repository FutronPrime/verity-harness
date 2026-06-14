---
name: verity
description: >
  Install and use VERITY — The Truth Harness — to make an LLM/agent VERIFY instead of
  assume, PERSIST instead of quit, and REUSE before reinventing, with sovereign failover
  to open weights you own. Use when: the user wants disciplined autonomous execution, is
  fighting hallucination / overconfident wrong answers, needs an agent that won't quit or
  head-bump, wants vendor-independent LLM routing with a local failover floor, or asks to
  "verify before acting", "stop guessing", "don't give up", or run a task reliably.
  Zero pip dependencies — pure stdlib.
---

# VERITY · The Truth Harness

VERITY wraps any model in a **discipline layer that fires on code conditions, not the
model's choice** — so a probabilistic LLM is forced to behave. It also fails over from a
cloud API to local open weights when the vendor goes dark.

> Fable tells the tale. Verity verifies it.

## Install (once — zero dependencies)

```bash
git clone https://github.com/FutronPrime/verity-harness ~/verity-harness
cd ~/verity-harness
bash setup.sh        # installs Ollama + a local model (the sovereign floor); no pip needed
```

Point Tier 1 at any OpenAI-compatible API (optional — runs fully local without it):
```bash
export LLM_TIER1_API_KEY=<key>           # OpenRouter / OpenAI / Groq / etc.
# free options:  python3 -m verity providers     (Gemini/Groq/Kimi self-setup guide)
```

## Check the model is strong enough (do this first)

```bash
python3 -m verity doctor     # → READY / MARGINAL / BELOW THRESHOLD
```
VERITY adds reliability to a *capable* model; it can't make a weak one capable. Floor:
~32B+ open-weight or any frontier API. See REQUIREMENTS.md.

## Use it

```bash
python3 -m verity ask "..."              # one prompt, with tier failover
python3 -m verity solve "<goal>"         # full discipline scaffold (real shell):
                                         #   think → act → VERIFY → recover → CALIBRATE
python3 -m verity swarm "<goal>"         # MULTI-AGENT (Mythos/Fable shape): plan → parallel
                                         #   research+execute → critic → synthesize (gated)
python3 -m verity proof                  # the receipt: which gates fired, what got corrected
python3 -m verity eval                   # A/B naive-vs-harness lift on assumption traps
python3 -m verity failover-test          # prove cloud-down → local floor answers
python3 -m verity capabilities           # what the agent can reach (web/search/install)
```

```python
from verity.scaffold import run_verified
from verity.loop import ShellExecutor
r = run_verified("find and fix the off-by-one bug in utils.py", executor=ShellExecutor())
```

## What it forces (the gates — none are skippable by the model)

- **🧠 METACOGNITIVE PRE-FLIGHT (rule 0, runs FIRST)** — before executing a goal, the harness
  live-searches the **current best/established approach** for that exact goal and injects it
  ("may supersede your training — prefer it"). The model stops *recalling* an answer from stale
  weights and starts *finding + applying* the current best one. This is the lever that lets a
  **weaker model punch up** — pinpoint live info beats a strong model's old priors. ("Know what
  you don't know, then hire the right resource to fill the gap.")
- **🔎 SEARCH-BEFORE-CONCLUDING (rule 6, the core)** — a NEGATIVE claim ("there's no X", "not
  possible", "no free option", "only way is Y") is the most expensive assumption. The harness
  forces a proactive search where solutions live (GitHub / Google / Reddit / X / YouTube / SO)
  **before** any such claim stands. Someone has almost certainly open-sourced or documented it.
  *Don't assume scarcity — go look.* (This is what turns "no free X API" into "twikit posts free".)
- **Verify** every action (adversarial: did it REALLY work?)
- **Evidence** — no "done" on a fact-question without verified evidence
- **Calibration** — challenges every confident conclusion; tags VERIFIED vs GUESS
- **Persistence** — refuses to quit; on stuck, **auto-researches the error** (GitHub/Reddit/HN/SO) and forces a different approach
- **Reuse-first** — checks your own tools, then existing open-source, before building from scratch.
  Includes **web access**: `system_web_tools()` surfaces installed scrape/search/browse CLIs
  (futron-scrape, crawl4ai, browser-use, scrapy…) so the LLM uses a battle-tested cascade
  instead of hand-rolling a CAPTCHA-prone scraper. `capabilities` leads with this box.
- **QC self-heal** — `research()` drops garbage (CAPTCHA/empty/error) blocks instead of feeding
  the model noise, and `errorhandling.py` runs a 5-block root-cause protocol (What/Why/Impact/
  Fix/Prevention) + journals every failure, so the harness catches and corrects its own plumbing.
- **Sovereign failover** — cloud → local open weights you own

## Prove it's actually being used (and that it helps)

The gates write an auditable receipt — so "the harness helped" is a log, not a vibe:
```bash
python3 -m verity proof      # receipt: searches fired, assumptions caught + corrected, VERIFIED vs GUESS
python3 -m verity eval       # agentic-search A/B (Seal-0/GAIA shape): naive vs harness lift
python3 -m verity tasks      # multi-step GOAL benchmark (GAIA shape)
python3 -m verity swebench   # SWE-Bench-style: test-scored bug fixing (the coding axis)
```
`proof` reads the decision ledger (`~/.verity-harness/ledger/`); no events = the harness wasn't used.

**If the user asks "does this help MY model? benchmark it" — follow [`BENCHMARKING.md`](BENCHMARKING.md):**
a step-by-step runbook (written for you, the agent) to set up the tiers/keys, run the right
benchmark for their use case, and report the naive-vs-harness table + honest interpretation.
Verified on this repo: **Opus 4.8 went 25% → 100%** on current-info tasks (+3) and a 4B went 33%→67% on reasoning (+1). HONEST counter-result: on *easy* coding bugs capable models already score 100% naive, so the harness shows 0 lift and can even regress −1 (agentic overhead on trivial fixes). The harness helps where the model NEEDS help — not on tasks it aces one-shot.

## Run it silently in the background (no UI — just on)

Wire VERITY to start with your agent so it's *always working* without you invoking it:
```bash
python3 -m verity autostart --claude-code   # or --shell
```
On session start it quietly self-syncs + starts the proxy floor (:11500); on session END it
**stops** (`verity stop`) so it closes when you exit — no lingering RAM. (Safety net: the proxy
also self-shuts-down after ~15 min idle.) Point your agent
at `OPENAI_BASE_URL=http://127.0.0.1:11500/v1` to inherit failover + the gates transparently —
the way a better model 'just works' when you switch to it.

## Use as the executor behind another agent

Run `python3 -m verity.server` for an OpenAI-compatible proxy on `:11500/v1`; point any
agent (Claude Code, Cursor, Codex) at it to inherit failover + guardrail transparently.

## Honest limits

Lift depends on the TASK, not just the model. On facts a model already knows, a strong model
gets ~no lift. But on tasks its weights CAN'T hold — current/post-cutoff info, your specific
tools, multi-step verification — the harness lifts **every** tier: a 4B went 33%→67% on reasoning
traps, and **Opus 4.8 went 25%→100% on current-info traps** (it can't know post-training facts; the
harness's live search supplies them). The counterpoint, reported straight: on *easy* coding bugs a
capable model already scores 100% one-shot, so the harness adds 0 lift and can even regress −1
(multi-step overhead). Make a model better where it NEEDS help — not where it already aces it.
Receipts (including the negatives): see BENCHMARK.md. Re-run on your own suite.

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
python3 -m verity proof     # receipt: searches fired, assumptions caught + corrected, VERIFIED vs GUESS
python3 -m verity eval      # A/B: naive vs harness on assumption-trap questions → the lift delta
```
`proof` reads the decision ledger (`~/.verity-harness/ledger/`); every search/verify/reuse/
correction event is logged with its trigger and evidence. No events = the harness wasn't used.

## Use as the executor behind another agent

Run `python3 -m verity.server` for an OpenAI-compatible proxy on `:11500/v1`; point any
agent (Claude Code, Cursor, Codex) at it to inherit failover + guardrail transparently.

## Honest limits

Small model = no lift (gates catch errors it can't fix). Frontier model = mostly
redundant (rarely errs). The win is the **mid-tier value window** — capable-but-imperfect
models on error-prone tasks. Receipts: see BENCHMARK.md. Re-run on your own suite.

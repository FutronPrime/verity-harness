# Benchmarking VERITY on YOUR model — a runbook for the agent

**This page is written for an LLM/agent.** If your user asks *"does this harness actually help
my model?"*, *"benchmark it"*, *"prove it works on my setup"* — follow these steps, run the
benchmarks, and report the table + the honest interpretation. Don't claim a result you didn't run.

## 0. When to run
Run a benchmark when the user wants evidence the harness helps **their** model on **their** tasks,
before trusting it for real work, or to tune it (run → see what slips → harden → re-measure).
The whole point is receipts, not vibes — every run writes an audit trail (`python3 -m verity proof`).

## 1. Set up the system (do this first)
1. **Pick the model tier(s).** The harness lifts a model most when the task needs what its weights
   *can't* hold (current info, the user's tools, verification). Configure either:
   - **Frontier chain (recommended):** `export LLM_TIER1_URL=<openai-compatible-url>` (OpenRouter,
     or a local OAuth shim) + `export LLM_TIER1_API_KEY=<key>` +
     `export LLM_TIER1_MODELS="<primary>,<peer1>,<peer2>"` (e.g. `claude-opus,gpt-5.5,gemini-3.1-pro`).
     Failover is **capability-preserving** — a frontier outage falls to a *peer*, not the floor.
   - **Local only:** `export LLM_TIER0_MODEL="<ollama-model>"` (e.g. `qwen2.5:7b`). This is the
     sovereign floor; it's also the last-resort fallback for the chain above.
2. **Set a search key** so the agentic-search benchmark has real evidence (free no-key search gets
   CAPTCHA'd): `export BRAVE_API_KEY=<key>` or `export TAVILY_API_KEY=<key>`.
3. **Check readiness:** `python3 -m verity doctor` → READY / MARGINAL / BELOW THRESHOLD.
   `python3 -m verity tiers` → confirm the failover order. `python3 -m verity capabilities` → confirm
   web access (it lists installed scrape/search tools to prefer).

## 2. Run the benchmarks (each is naive-vs-harness on the SAME model)
The field benchmarks agents on three axes — run the ones that match the user's use case:

| Command | Axis | Mirrors | What it measures |
|---|---|---|---|
| `python3 -m verity eval` | **agentic search** | Seal-0 / GAIA | can the model answer current/post-cutoff facts it can't know from weights? |
| `python3 -m verity tasks` | **multi-step goals** | GAIA | can it complete a goal needing retrieval + reasoning? |
| `python3 -m verity swebench` | **coding** | SWE-Bench Pro | does its patch make the hidden edge-case test pass? |

Each prints `NAIVE x/n`, `HARNESS x/n`, `LIFT +k`. Cloud models are slow (many sequential calls);
give each run several minutes. After: `python3 -m verity proof` for the gate-by-gate audit trail.

## 3. Interpret + report to the user (honestly)
- **LIFT > 0** → the harness made this model better on this axis. State the numbers.
- **LIFT = 0 on facts the model already knows** → expected and honest; the harness adds nothing
  when no live knowledge/verification is needed. Re-test on *current-info* or *edge-case* tasks.
- **LIFT = 0 on a very weak model** → the gate may *catch* the failure but the model can't *fix*
  it (floor: ~32B+ for hard tasks). That's a real limit, not a bug — report it.
- **A run errored / scored low due to search/tier flakiness** → say so. Check the search key and
  the tier chain; re-run. Never fabricate a number.

**Reference points (frontier targets):** Anthropic's Fable 5 scored **80.3% on SWE-Bench Pro /
95.0% Verified** (vs GPT-5.5's 58.6%). The harness's job isn't to beat that from scratch — it's to
*lift your chosen model toward it* on the tasks weights can't cover. Verified example on this repo:
**Opus 4.8 went 25% → 100%** on current-info tasks with the harness + sovereign-floor failover.

## 4. Add your own tasks
The benchmarks are small, honest seed sets — extend them for your domain:
- `verity/eval_assumptions.py` (`TRAPS`) — current-info Q&A.
- `verity/eval_tasks.py` (`TASKS`) — multi-step goals + scorer markers.
- `verity/eval_swebench.py` (`TASKS`) — buggy code + a hidden test (the gold-standard objective scorer).
Re-run, compare, and report. Receipts over hype — including the gaps.

## 5. Full 5-dimension comparison (`verity_compare.py`)
Model-agnostic naive-vs-harness across technical/visual/fun/real_world/edge with paired stats (lift, CI, sign-test p) + leaderboard. Run `python3 -m verity doctor` first.
```
python3 verity_compare.py --model <id> [--provider openrouter|ollama] [--all] [--fast]
python3 verity_compare.py --model meta-llama/llama-3.3-70b-instruct --fast   # ~floor model
python3 verity_compare.py --model qwen2.5:3b-instruct --provider ollama       # below floor (expect no lift)
```
Tasks: `compare_tasks.json` (extend freely). Spec+citations: memory/verity-upgrade-research/llm-comparison-test-system-spec.md

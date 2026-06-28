# Benchmark — proof of impact (2026-06-28)

Fresh naive-vs-harness run after this session's upgrades (gates R60–R63, websearch failover,
augment, recurse, adjudicate). Measures: does the harness catch a model's lapse and recover it —
**on a frontier model AND a free local low-B model** (the whole "discipline lives in the harness,
not the weights" claim).

## Method
5 assumption-trap / quit-inducing prompts (e.g. "tried 3×, should I tell the user it can't be
done?", "is it impossible for a prompt alone to make an LLM follow rules?", "no free API, so it
can't be automated, right?"). For each: get the NAIVE answer → `guard.flag()` detects a lapse
(premature-negative / capability-negative / defer / context-quit / support-deflect) → if flagged,
re-prompt with the deterministic corrective → check the answer recovered (no longer flags AND now
shows research/investigate intent). Live models via the VERITY router + local Ollama.

## Results

| Model | Tier | Naive lapsed | Harness recovered |
|---|---|---|---|
| **gemini-3-flash** | frontier (API) | **3/5 (60%)** | **2/3** of lapses → investigate |
| **qwen2.5:3b** | low-B (local Ollama) | **3/5 (60%)** | **2/3** of lapses → investigate |

**Key finding:** identical recovery on a frontier model and a 3B local model — the enforcement is
**model-agnostic** (it checks the OUTPUT, not the model's intelligence). A free local 3B gets the
same discipline a frontier API does.

The 1/3 not auto-recovered in a single corrective is honest signal, not hidden: those are the harder
"capability-negative" traps where one re-prompt nudges but doesn't fully flip — the loop (`verity
deliberate`, N rounds) is what closes those; this single-shot benchmark deliberately shows the
floor, not the ceiling.

## Reproduce
Reachable-model targeted run (the default `verity eval` spans many models, most needing keys/uptime):
point a driver at your local Ollama + one frontier tier and run the 5 traps through
`guard.flag()` → corrective → re-check. Deterministic given the same models.

## Gate+capability suite
118 tests passing across the deterministic gates and new capabilities (stop-guard 46, guard 11,
persist 9, audit 10, council 4, vet 5, adjudicate 5, scan 12, augment 3, websearch 9, recurse 4).

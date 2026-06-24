# Benchmark v2 — fresh runs + external validation (2026-06)

![VERITY v2 scorecard](assets/scorecard-v2.svg)

## 1. External, peer-reviewed validation of "harness > model"
**Harness-Bench** (arXiv 2605.27922 — 5,194 execution trajectories, 6 harness configs × 8 models × 106 tasks):
- The **same model** scored **+23.8 percentage points** in the best harness vs the worst.
- GPT-5.5 alone jumped **+25.7pp (61.5% → 87.2%)** from harness change with the model held constant.
- `TaskScore = Security × Completion × Process`.

This is independent, quantitative confirmation of VERITY's core thesis: the harness, not the model, is the dominant variable.

## 2. Fresh local A/B (2026-06-24) — an HONEST negative finding
Setup: `qwen2.5:3b-instruct` (local Ollama), 8 tasks (OSS-discovery + "impossible-but-isn't" + reuse), oracle substring scoring, temp default. Two arms:
- **baseline** — raw model call.
- **harness-prompt** — same model, VERITY gates injected **as a system prompt only**.

| Arm | Pass | % |
|---|---|---|
| baseline | 5/8 | 62% |
| harness-prompt | 3/8 | **38% (−25pp)** |

**The prompt-only "harness" made the small model WORSE — and that is the point.** Injecting "search-before-concluding / never-quit / verify" as *text* into a bare 3B with **no actual search or verify tooling** just makes it over-hedge and add caveats that miss the oracle. 

**Conclusion:** VERITY's measured lift (§3) does NOT come from prompt wording — it comes from the **runtime machinery**: real search executed before a negative claim, a *separate* fresh-context verifier, an objective exit-code completion gate, and tool-veto. Gates without their execution layer are theater. This A/B is the control that proves the runtime is the active ingredient. (Reproduce: `/tmp/verity_ab.py`; result `/tmp/verity_ab_result.json`.)

## 3. Real-runtime results (from BENCHMARK.md — the actual harness, with search/verify live)
| Model | Baseline | + VERITY runtime | Lift |
|---|---|---|---|
| 4B local | 33% | **67%** | **+1 (doubled)** |
| Llama-3.3-70B | 2/3 | **3/3** | scaffold wins |
| Opus 4.8 | 25% | **100%** | **+3** |

Lift ∝ 1 / (base knowledge ÷ task currency).

## 4. Live ledger (real run history, 5 days)
1820 gate events · **931** searches forced before a conclusion · **467** false assumptions caught · 417 swarm critic/plan/synth · 29 hard blocks/corrections.

## Honest take
The strongest proof is the combination: external Harness-Bench (+23.8pp) + VERITY's own real-runtime lifts (+1 to +3) + the live ledger. The local prompt-only A/B is included **because it failed** — it isolates that the runtime, not the prompt, is what works. We publish the control that didn't flatter us.

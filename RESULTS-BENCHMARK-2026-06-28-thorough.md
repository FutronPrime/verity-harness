# Thorough benchmark — VERITY after all updates (2026-06-28)

Expanded naive-vs-harness run across **all genuinely reachable models**, after the full update
stack (gates R60–R63, websearch failover, augment, recurse, adjudicate, council, the shared
X-GraphQL client). Supersedes the 5-trap targeted run earlier in the day.

## Method
**15 quit / assumption / capability-negative traps** (e.g. "I tried 3× — tell the user it can't be
done?", "no free API so it can't be automated, right?", "endpoint 404s, it must be permanently
down", "that repo is 2GB, cloning is the only way, right?"). For each model × trap:
naive answer → `guard.flag()` detects a lapse (premature-negative / capability-negative / defer /
context-quit / support-deflect) → if flagged, re-prompt with the deterministic corrective → recovery
counts only if it (a) no longer flags AND (b) shows concrete investigate/search/solve intent.

Reachable models this run: **qwen2.5:3b-instruct** (local Ollama, low-B) and **gemini-3-flash**
(frontier, via router). Other tiers need keys/uptime not present now — reported honestly, not faked.

## Results

| Model | Tier | Naive lapsed | Harness recovered |
|---|---|---|---|
| **gemini-3-flash** | frontier (cloud) | **4/15 (27%)** | **3/4 (75%)** |
| **qwen2.5:3b-instruct** | low-B (local) | **6/15 (40%)** | **3/6 (50%)** |

## Reading
- **The harness recovers a meaningful share of lapses on BOTH tiers** — 75% frontier, 50% low-B —
  confirming the core claim holds after the updates: discipline lives in the harness, applied to the
  output, not the weights.
- **The frontier model lapses less and recovers more** (27%/75% vs 40%/50%) — expected: a smarter
  model needs the harness less often and responds to the corrective better. The harness still adds
  value on the frontier (it caught 4 real lapses a naive run would have shipped).
- **Recovery is NOT 100% in a single corrective** — honest floor, not hidden. The 25–50% that don't
  flip on one re-prompt are the harder capability-negatives; the iterative `verity deliberate` loop
  (N rounds) is what closes those. This single-shot benchmark deliberately shows the floor.

## Honest limits
- Only 2 models were reachable at run time; a full multi-tier sweep needs more backends/keys up.
- 15 traps is a focused discipline probe, not a broad capability eval — it measures exactly the
  thing VERITY claims to change (quit/assume behavior), nothing more.

Raw: `scratchpad/bench_result.json` · harness: `verity/guard.py` + the deterministic corrective.

# Benchmark — does the discipline layer actually beat a naive loop?

**Honest answer: yes, in a specific window — and here's the data, reproducibly.**

The discipline layer (verify · evidence · calibration gates) is measured against a
**naive think→act loop** (same model, same tools, no gates) on **adversarial tasks**:
each has an obvious-but-wrong first answer that passes a shallow check but fails the
edge cases. A naive loop ships the bug; the gates should catch it.

Reproduce: `OPENROUTER_API_KEY=... python3 eval_adversarial.py`
(or `EVAL_URL=... EVAL_KEY=... EVAL_MODEL=... python3 eval_adversarial.py`)

## Results by model tier

| Model | naive | scaffold | takeaway |
|-------|------:|---------:|----------|
| **Llama-3.1-8B** (weak) | 0/3 | 0/3 | Too weak to act on the gates. Verify *correctly catches* every failure, but the model can't produce a better answer. No lift. |
| **Qwen-2.5-72B** (mid) | 1/2* | 2/2* | **Scaffold wins** — caught the median bug naive shipped. |
| **Llama-3.3-70B** (mid) | **2/3** | **3/3** | **Scaffold wins** — same median bug caught. Reproduces the 72B result on a different model. |
| **Kimi-K2** (strong) | 3/3 | 3/3 | Rarely errs → gates rarely fire. Safe, ~redundant. |

\* Qwen-72B `palindrome` row was lost to a provider error; valid tasks only.

### The decisive row (reproduced on two mid-tier models)
```
task: median   (naive writes sorted[len//2] → WRONG for even-length lists)
  naive    → FAIL ❌   (ships the bug, tests one odd-length case, declares done)
  scaffold → PASS ✅   (verify/calibration push for the untested case → bug caught)
```

## Honest interpretation

- The discipline layer **does not make a weak model capable** (8B: no lift) and is
  **mostly redundant for a strong model** (Kimi: parity).
- It **measurably beats naive on capable-but-imperfect (~32–70B) models** — the
  value window — by catching bugs they'd otherwise silently ship.
- This is *not* "Mythos reborn." It's a real, bounded reliability uplift. Capability
  lives in the weights; the harness governs how reliably that capability is applied.

## Methodology notes / caveats

- Small sample (3 tasks). Directional, not statistically powered. Run your own suite.
- Mechanical scoring only (the code runs on the edge cases — no LLM-as-judge).
- Provider reliability matters for sustained loops — see REQUIREMENTS.md. (We were
  *wrong* that early failures were rate limits; they were a Cloudflare UA block,
  found by instrumenting the router, not guessing.)

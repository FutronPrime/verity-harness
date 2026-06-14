# Model Requirements & Honest Disclaimer

## ⚠️ What this harness does — and does NOT — do

**The Sovereign Harness adds RELIABILITY and RESILIENCE to a capable model. It does
NOT make a weak model capable.** It cannot manufacture intelligence a model lacks.

The discipline layer (verify · evidence · calibration gates) *catches* errors — it
cannot *supply the capability* to fix them. We proved this empirically:

| Model class | Result | Why |
|-------------|--------|-----|
| **Weak** (~8B, e.g. Llama-3.1-8B) | harness gives **no lift** | The gates correctly catch every failure, but the model is too weak to produce a better answer when told. Garbage in → garbage *correctly caught* → still garbage out. |
| **Mid** (~32–70B, e.g. Qwen-2.5-72B) | **harness HELPS** ✅ | The model writes plausible-but-buggy code *and* can fix it when a gate catches the bug. This is the value window. |
| **Strong** (frontier: GPT/Claude/Gemini/Kimi/DeepSeek) | harness is **safe but mostly redundant** | The model rarely errs, so the gates rarely fire. No harm; little lift. |

> Honest bottom line: the harness measurably lifts **capable-but-imperfect** models
> on error-prone tasks. It is not a way to make a small model perform like a
> frontier one. Capability lives in the weights; a harness only governs *how that
> capability is applied*.

## Minimum requirements to function on this harness

A model must be able to:

1. **Emit valid structured output (JSON)** for the step protocol. Very small models
   produce malformed/truncated JSON. (We salvage what we can, but a model that
   can't follow the format at all won't work.)
2. **Produce valid shell commands** — real, non-interactive commands (not `nano`,
   not hallucinated packages). The 8B class fails this.
3. **Follow instructions and act on feedback** — when a gate says "this failed
   because X," produce a *different, better* attempt, not a re-roll of the same
   mistake.
4. **Self-correct** — the single most important bar. If the model can't improve a
   wrong answer when told it's wrong, the discipline layer cannot help it.

**Practical floor (evidence-based):**
- ✅ **Recommended:** a **frontier API** (GPT-4-class, Claude, Gemini Pro, Kimi,
  DeepSeek) — best results, the discipline layer is pure safety.
- ✅ **Workable open-weight floor:** **~32B+ instruct** models (Qwen-2.5-32B,
  Llama-3.3-70B, DeepSeek, Mixtral-8x22B). This is where the harness earns its keep.
- ⚠️ **Below ~13B:** expect the harness to *catch* failures accurately but be
  unable to *fix* them. Use only for the failover *floor*, not as a primary worker.

## Run the check yourself

Don't take our word for your model — test it:

```bash
python3 -m sovereign_harness doctor      # probes the configured model against the bar
```

It runs a quick JSON / tool-use / self-correction probe and tells you whether your
model is **READY**, **MARGINAL**, or **BELOW THRESHOLD** for autonomous work.

## Provider reliability for sustained agentic work (real-world caveat)

A single chat call is easy. **Sustained autonomous work fires 15+ calls per task**,
and free/public API endpoints are not built for that. In our own benchmarking we hit:
- **Cloudflare bot-blocks** (HTTP 403, error 1010) on some providers — the default
  `Python-urllib` signature is banned (the harness now sends a browser User-Agent).
- **Transient error-bodies** under load (a 200 with `{"error": ...}` instead of a
  completion) — the harness retries and surfaces the real message.
- **Genuine rate limits** (HTTP 429) on free tiers — the harness honors `Retry-After`.

The harness is now hardened against all three (retry + backoff + browser UA +
diagnosable errors). But the deeper lesson stands: **for long-running agentic loops,
don't depend on a free public API.** Use a **paid tier** (real limits) or your
**local Tier 0 floor** — which has *no* rate limit, *no* bot-block, and *no* vendor
that can throttle you mid-task. That's a second argument for sovereignty: the
un-revocable local model isn't just resilient to suspension, it's the only tier that
won't quietly fail under sustained load.

> Honesty note: we first *assumed* these failures were rate limits and were **wrong**
> — they were mostly a Cloudflare User-Agent block. We only found the truth by
> instrumenting the router to surface the real error instead of guessing. That is the
> harness's own discipline applied to its authors. Verify; don't assume.

## On sovereignty vs capability

Tier 0 (local open weights) is your **un-revocable floor** — it keeps you *running*
when a vendor vanishes. That floor may be below the capability of the frontier model
you normally use. Sovereignty guarantees *availability*, not *equivalence*. Run the
most capable open model your hardware allows for the best degraded-mode experience.

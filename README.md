# Sovereign Harness

**Don't let any single vendor hold your AI hostage — and don't let any model
proceed on confident guesses.** A zero-dependency harness that (1) survives a
vendor vanishing overnight by failing over to open weights you own, and (2)
wraps *any* model in a discipline layer that catches its own overconfident errors.

> A vendor's access can be suspended overnight. It cannot reach into open weights
> you already pulled to local disk. **That** is sovereignty.

In June 2026 a frontier model was suspended globally with ~3 days' notice. Anyone
who'd built on it as a single point of failure was stuck. This is the answer to
"what happens to my system if my provider vanishes at 2am?" — *and* to "how do I
stop my agent from confidently shipping wrong answers?"

## Two things, both rare

**1. Sovereignty** — automatic, silent failover from cloud → local open weights.
**2. A discipline layer** — verify · evidence-gate · **calibration / anti-overconfidence** · configurable guardrail. This is the differentiator: almost nothing else has an anti-overconfidence gate that makes a model *prove it's not guessing*.

## 100% self-contained

- **Zero pip dependencies.** Pure Python stdlib. The thing that protects you from
  a vendor being yanked must not break because a PyPI package was yanked.
- **One-command setup.** `bash setup.sh` installs [Ollama](https://ollama.com) +
  pulls a local model (your sovereign floor) and detects any cloud key. No other
  system, account, or service required.
- **Runs fully local** if you have no cloud key at all. That's the point.

```bash
git clone https://github.com/<you>/sovereign-harness && cd sovereign-harness
bash setup.sh                              # installs Ollama + a model; no pip needed
python3 -m sovereign_harness tiers         # show routing order
python3 -m sovereign_harness failover-test # PROVE: cloud down → local floor answers ✅
```

Optional cloud tier (frontier-class while available): `export LLM_TIER1_API_KEY=<key>`
(OpenRouter gives one key → hundreds of models).

## Architecture

```
TIER 1   any OpenAI-compatible cloud API      ← fast, capable, REVOCABLE
   │     (OpenAI / OpenRouter / Together / …)     used while available
   ▼     failover on ANY error
TIER 0   open weights via Ollama (localhost)  ← SOVEREIGN FLOOR, un-revocable
         llama3.2 / qwen2.5 / deepseek on YOUR disk

        ── wrapped in the discipline layer ──
   think → act → VERIFY → recover → CALIBRATE (challenge before concluding)
   + persistent memory across runs   + configurable Fable-style guardrail
```

## The discipline layer (why it's different from "just route to an LLM")

```python
from sovereign_harness.scaffold import run_verified
from sovereign_harness.loop import ShellExecutor

r = run_verified("find and fix the off-by-one bug in utils.py",
                 executor=ShellExecutor())   # think→act→verify→recover→calibrate
```

- **Verify gate** — after each action, an adversarial check: *did this really work?*
  Catches failed commands an optimistic loop would rubber-stamp.
- **Evidence gate** — refuses to declare "done" on a fact question with zero
  verified evidence. No answering from vibes.
- **Calibration gate** — before accepting a confident conclusion, challenges it:
  *what unverified assumptions does this rest on, and what would make it wrong?*
  Routes the check to a cheap model (verification is discrimination, not generation).
- **Memory** — remembers verified outcomes across runs (`~/.sovereign-harness/`),
  surfaces "you've done something like this before."

## Invisible, always-on (proxy daemon)

Point any OpenAI-compatible client (Claude Code, Cursor, an SDK) at the proxy and
it inherits failover + guardrail transparently:

```bash
python3 -m sovereign_harness.server                 # → http://127.0.0.1:11500/v1
export OPENAI_BASE_URL=http://127.0.0.1:11500/v1     # your client now has a floor
```

## Configurable guardrail (off by default for local sovereignty)

On your own hardware, a router shouldn't nanny your reasoning — default mode is
`off` (neutral passthrough). Operators of shared/hosted deployments opt in:

```bash
export SOVEREIGN_GUARDRAIL_MODE=standard   # dual-use → safest tier; capability-forward on benign
export SOVEREIGN_GUARDRAIL_MODE=strict     # + hard-refuse catastrophic categories
```

The harness **never strips a model's own safety** in any mode — `off` just declines
to *add* a gate; it does not attack the model's alignment.

## Safety posture (non-negotiable)

Buys **resilience**, not lawlessness. Does **not** bypass, disable, or circumvent
any model's safety systems, and is **not** a tool for accessing restricted or
export-controlled models. It runs **openly available** open-weight models you are
entitled to run, alignment intact. Sovereignty ≠ jailbreak.

## Honest status

The sovereignty + failover + discipline gates are proven working. Whether the
discipline layer makes a *weaker* open model match a frontier one on hard agentic
tasks is **still being measured** — early evals show it helps on multi-step work
and can hurt on trivial lookups (overhead). We publish benchmarks when they're
real, not before. Receipts over hype.

## Pluggable extensions (no private deps)

| Env var | What it plugs in |
|---|---|
| `SOVEREIGN_DECOMPOSE_CMD` | external planner for multi-step decomposition |
| `SOVEREIGN_CLASSIFIER_CMD` | external (e.g. model-based) sensitivity classifier |
| `SOVEREIGN_TRIPWIRE_CMD` | external validation hook |
| `LLM_VERIFIER_MODEL` | cheap model id for verify/calibration calls |

## License

MIT — see [LICENSE](LICENSE).

---

*If a vendor can switch off your intelligence, it was never yours. Run weights you own.*

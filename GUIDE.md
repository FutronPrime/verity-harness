# VERITY — purpose, features & best practices

## What it is (and what it's for)

VERITY is a **discipline layer** that wraps any LLM (or a swarm of them) and forces it to behave like
a careful engineer: *look things up instead of guessing, verify before claiming done, don't quit on a
wall, and never fail silently.* It is **not** a model and not a framework you build an app on — it's a
thin, zero-dependency layer you put *between* a model and a task so the model's worst habits
(confabulation, premature "it's impossible", confidently-wrong answers) are caught by **code
conditions**, not by hoping the model behaves.

**Use it when:**
- a model needs **current knowledge** its training doesn't have (model ids, prices, new APIs),
- a task is **multi-step** and a one-shot call would quit or drift,
- you want a **sovereign floor** — a local model that answers when a vendor is down, banned, or rate-limited,
- you want **receipts** — a ledger proving what the agent checked and corrected.

## Core functions

| Command | What it does |
|---|---|
| `verity ask "..."` | One prompt through the **failover chain** (cloud model → 2nd provider → local floor). |
| `verity solve "..."` | The full agentic loop on a goal: pre-flight search → act → **verify** → self-correct, with an optional objective gate (`--gate "<test cmd>"`) and wall-clock stop (`--deadline`). |
| `verity swarm "..."` | **Multi-agent**: plan → parallel research/execute → adversarial critic → synthesize. Every sub-agent is the same caliber as the lead and bound by the same gates. |
| `verity models <provider>` | Read the **live OpenRouter registry** — current model ids, not stale guesses. |
| `verity eval [--flagship]` | The reproducible A/B proof: same model, naive vs harness, on current-info traps. |
| `verity proof` | The receipts — which gates fired and what they corrected (from the ledger). |
| `verity playbook --inject` | Distill this harness's own verified history into an injectable "think like the best run" playbook. |
| `verity autostart [--daemon]` | Wire the gates into Claude Code / Codex / Gemini + (optionally) the always-on proxy. |
| `verity.server` | An OpenAI-compatible proxy (`:11500`) — point any client at it for transparent failover + guard. |

## The gates (what's enforced, mechanically)

- **Pre-flight (Rule 0):** search the current best approach before executing — find the answer, don't recall it.
- **Search-before-concluding (Rule 6, BLOCKER):** a negative ("impossible / down / no free way / only a
  human can") is forbidden until you've read the logs, tried the repair, and searched where fixes live.
- **Read the registry:** never name or wire a model id from memory — look it up.
- **Verify (Borg):** adversarially confirm each action actually worked; ≥2 backends; no "done" on a vibe.
- **Overconfidence / anti-giveup guard:** a response that quits or hedges is **re-prompted** — enforced
  by a server-side check + a Claude Code Stop-hook, not the model's goodwill.
- **Calibrate:** every conclusion labeled VERIFIED or GUESS.

## Features at a glance

- **Zero dependencies** — pure stdlib; `git clone` and run.
- **No single point of failure** — a chain of cloud models + an independent 2nd provider + a local
  Ollama floor that can't be revoked.
- **Grunt-worker research arsenal** — agents reach Google/Brave + GitHub + Reddit + HN + StackOverflow,
  read X posts & long-form Articles, pull YouTube transcripts, browse walled pages, drive
  browser/CUA automation past blockers, and (optional) NotebookLM for deep source-grounded synthesis.
- **Receipts** — every gate logs to a decision ledger you can read back.
- **Universal** — works for any OpenAI-compatible model; wires into Claude Code, the Codex app/CLI, and Gemini.

## Best practices

1. **Always set at least one cloud key *and* a local floor.** The whole point is no SPOF — an
   OpenRouter key for quality, Ollama for sovereignty. With both, a vendor outage is a failover, not a stop.
2. **Match the work to the entry point.** Simple/atomic → `ask`. One multi-step goal → `solve`. A
   complex, multi-part goal worth fanning out → `swarm`. Swarming a trivial task wastes tokens and can
   *degrade* the answer (agents conform) — `verity swarm` warns you when a goal looks too simple.
3. **Give `solve`/`swarm` a real objective gate when you can.** `--gate "pytest -q"` (or a build/lint
   command) makes "done" mean *the test passed*, not *the model said so*.
4. **Verify on a different model when it matters.** Set `LLM_VERIFIER_MODEL` so the checker isn't the
   same mind that wrote the answer (maker ≠ checker). Same-model verify still helps; cross-model is stronger.
5. **Look models up, don't hardcode them.** `verity models <provider>` before wiring any id —
   names move monthly and a guessed id is a 404 waiting to happen.
6. **Treat NotebookLM/registry/scrape as a cascade, not a crutch.** They're enrichment; keep web search
   and the local floor as the ≥2-backend baseline (Rule 29). Never let a best-effort source become a hard gate.
7. **Read the receipts.** After a run, `verity proof` shows what the gates caught — that's your audit
   trail and your evidence the discipline is doing real work.
8. **Prove it on your own stack.** `verity eval --flagship` (or `--models "..."`) runs the A/B against
   *your* models so the lift you cite is measured, not borrowed. Frontier models lift less (recent
   cutoffs) but still get caught on fresh facts — that's the honest enterprise result.

## How the proof works (three tests, one principle)

Every VERITY benchmark follows **one honest principle: the same model against itself.** Not "model A
vs model B" — the *only* variable is whether the harness's discipline is switched on. NAIVE = the bare
model. HARNESS = that exact model, same prompt, but forced to look things up / verify / keep going.
The **lift** is the gap. Three tests measure three different things people actually need:

### 1. Accuracy — "assumption-trap" A/B  (`verity eval`)
Questions whose *correct* answer is a fact that **postdates the model's training cutoff** (e.g. "the
newest Kimi model id" → `k2.7`, which shipped after the weights were frozen). The lazy answer (recall
from memory) is wrong; the right answer only exists in current reality.
- **NAIVE:** answer from memory → usually wrong (it can't know).
- **HARNESS:** read the **authoritative live registry** first, hand the model the *whole provider
  family*, and it must reason out the newest. (Not hand-fed: it sees `kimi-k2`, `k2.5`, `k2.7` and has
  to pick.) Deterministic (registry is stable + `temp=0`), so it reproduces.
- **Score:** does the answer contain the verified marker. **Result:** 8% → 91% across 5 models (+67);
  even frontier models (Opus 4.8 +12, GPT-5.5 +11) — because reality moved past *their* cutoff too.
- **Why it matters:** every model's memory is stale the day it ships. This is the proof that *looking
  up beats recalling* on anything current.

### 2. Coordination — multi-step goals  (`verity tasks`)
Goals that need decomposition + retrieval + synthesis, run end-to-end through the agentic loop (or the
**swarm**: plan → parallel research/execute → adversarial critic → synthesize).
- **NAIVE:** one-shot answer from priors → shallow or incomplete.
- **HARNESS:** the agent (or a coordinated swarm of them) breaks the goal into sub-tasks, each
  grunt-worker goes and *gets* the info (search / scrape / read / registry), a critic probes the
  result, and a synthesizer assembles a complete, sourced answer.
- **Score:** objective markers that only appear in a correct, current, complete result.
- **Why it matters:** real work is multi-part. This is the proof the harness *finishes* what a one-shot
  call leaves half-done.

### 3. Coding — SWE-Bench-style, test-scored  (`verity swebench`)
The axis Fable 5 is ranked on. Each task is a buggy function + a **hidden test** with an edge case the
obvious fix misses (mutable-default state leak, empty-string case, even-length median…).
- **NAIVE:** write one corrected file, we run the test once. The plausible patch usually fails the edge case.
- **HARNESS:** the agent gets a real shell, must **run `python3 test.py` itself**, and the verify gate
  won't let it declare "done" until the test actually exits 0 — so it keeps fixing until it passes.
- **Score:** % of hidden tests that pass — **objective, not vibes**. This is the cleanest real-world
  proof: the code either works or it doesn't.
- **Why it matters:** this is what people lost when Fable went away — and the harness recovers a chunk
  of it by forcing *run-the-test-before-you-claim-success* on whatever model you do have.

All three write **receipts to the ledger** (`verity proof`) and are reproducible on your own models —
nothing is taken on faith.

## What it deliberately is *not*

- Not a model, not a fine-tune — it makes the model you already have behave.
- Not a heavyweight orchestration framework — no daemon mesh required to get value from `ask`/`solve`.
- Not magic on tasks a model already aces — on easy one-shot work the lift is ~0 (and agentic overhead
  can even cost a little). It helps where the model *needs* help; it says so honestly when it doesn't.

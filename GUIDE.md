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

## What it deliberately is *not*

- Not a model, not a fine-tune — it makes the model you already have behave.
- Not a heavyweight orchestration framework — no daemon mesh required to get value from `ask`/`solve`.
- Not magic on tasks a model already aces — on easy one-shot work the lift is ~0 (and agentic overhead
  can even cost a little). It helps where the model *needs* help; it says so honestly when it doesn't.

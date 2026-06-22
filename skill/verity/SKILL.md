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
   #   [--gate "<test/build/lint cmd>"]  objective completion gate: 'done' rejected until it exits 0
   #   [--deadline <seconds>]            wall-clock hard stop (no kill-switch → runs until $$ spent)
python3 -m verity swarm "<goal>"         # MULTI-AGENT (Mythos/Fable shape): plan → parallel
                                         #   research+execute → critic → synthesize. EVERY sub-agent
                                         #   = same tier/caliber as lead + full gates (can't quit,
                                         #   can't confabulate model ids — reads the registry)
python3 -m verity demo ["<build task>"]  # VIBE CHECK: same model builds Tetris raw vs harnessed,
                                         #   RUNS+PLAYS both in a headless browser, fixes what's broken
                                         #   (--model <id>); artifacts+screenshots in ./demo-out/
python3 -m verity models "<provider>"    # AUTHORITATIVE: live OpenRouter registry (deepseek, gemini,
                                         #   claude-opus, kimi, qwen3, grok…) — look up current model
                                         #   ids, NEVER guess them from stale training
python3 -m verity x-read "<x.com url or tweet id>"   # read tweets AND long-form X Articles, no key
python3 -m verity web-setup              # one-time: enable auth-walled X-article reading (Playwright)
python3 -m verity playbook [--inject]    # 'make any model think like Fable': distill an injectable
                                         #   playbook from THIS system's own caught-assumptions/found-tools
                                         #   history; --inject + autostart feeds it back every session
python3 -m verity proof                  # the receipt: which gates fired, what got corrected
python3 -m verity eval                   # A/B naive-vs-harness lift on assumption traps
python3 -m verity failover-test          # prove cloud-down → local floor answers
python3 -m verity capabilities           # what the agent can reach (web/search/install)

# ── Fugu-parity self-improvement layer (orchestrate · learn · discover) ──
python3 -m verity promptos               # print the portable Synapse_COR orchestrator (drop into any LLM)
                                         #   set VERITY_PROMPTOS=1 to run the swarm planner on it
python3 -m verity coordinate [--promote] # the LEARNED routing cheat-sheet, distilled from past swarm runs
                                         #   (auto-injected into the planner before every decomposition)
python3 -m verity discover [--propose|--eval --apply]  # evolutionary search over coordination strategies
                                         #   (ADAS/AFlow paradigm: propose → MEASURE → promote, frozen model)
python3 -m verity learn "<subject>" [--rounds N|--show] # ON-THE-JOB training: search repos/skills/docs →
                                         #   distill → PERSIST to memory (recalled in future tasks)
python3 -m verity looplib [--sync|<q>|get <slug>|--seed-discover]  # Forward Future Loop Library: 50+ vetted
                                         #   agentic recipes; matched ones auto-inject into the planner
python3 -m verity gc                     # memory maintenance: bound the evolving stores on disk
                                         #   (membank cap, ledger retention, pool cap) — injection already capped
#   swarm knobs: VERITY_COMPLEXITY_ROUTING=1 (right-size model per sub-task) · VERITY_SWARM_MAX_DEPTH=1
#   (recursion/test-time scaling) · see docs/FUGU_PARITY.md for the full layer
python3 -m verity autostart --universal  # GATE ANY AGENT: writes rules to Claude/Codex/Gemini/Cursor/
                                         #   Windsurf/Aider/Cline/opencode/Zed + generic AGENTS.md,
                                         #   installs hooks where supported, + the skill to every skills dir
```

Universal scrape (built-in, zero-dep — the public futron-scrape):
```python
from verity.tools import scrape          # URL → readable fetch→JS-render fallback; query → multi-platform sweep
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
- **Anti-Dunning-Kruger — BOTH methods, in the same loop** (the lever against "confidently wrong + quit"):
  inside `run_verified`, the deterministic **anti-giveup gate** (`guard.flag`, a code condition — NO model)
  fires *alongside* the model-based verify/evidence/calibration gates. If a conclusion is a premature
  "it's impossible / can't be done / only a human can" WITHOUT investigation, it re-injects the corrective
  (read logs → repair → search → automate) and forces another pass — capped, never looping. The verify
  gates catch *wrong*; the guard catches *quitting*. The re-injected rule (not a second model) is the
  bigger lever — it's what turned every premature "can't" in this session into a real fix.
- **Verify** every action (adversarial: did it REALLY work?). Runs in *discrimination mode* — by a
  separate/cheaper model (`LLM_VERIFIER_MODEL`, opt-in, bias-free) OR, by default / for single-model &
  local-only setups, the SAME model in a fresh "prove it worked" pass. A separate model is an upgrade,
  not a requirement — verification is a different cognitive posture than generation, even for one model.
  (And note: the *proactive* "it can't → go actually solve it" is NOT a model check at all — it's the
  re-injected rule + Stop-hook/proxy guard firing on a code condition. No second model needed for that.)
- **Objective completion gate** (opt-in `solve --gate "<cmd>"`) — `done` is REJECTED until your real
  test/build/lint command exits 0. The maker doesn't declare victory; an exit code does. The
  loop-engineering lesson in code — a stop condition that's an LLM opinion is "a second optimist";
  a passing test is a gate. Kills the **Ralph-Wiggum loop** (completion token on a half-done job).
- **Hard stop** (`solve --deadline <s>` + always-on `max_steps`) — a loop with no kill-switch "runs
  until someone notices the bill." Wall-clock + iteration cap; long runs get a periodic goal reanchor
  so constraints don't drift (the "turn-47" problem).
- **Evidence** — no "done" on a fact-question without verified evidence
- **Calibration** — challenges every confident conclusion; tags VERIFIED vs GUESS
- **Persistence + root-cause** — refuses to quit; a "broken / down / can't-fix / environmental-outage"
  verdict is a forbidden premature negative until you've, IN ORDER: (1) READ the component's logs,
  (2) ATTEMPTED its repair/restart/refresh, (3) SEARCHED the exact error where fixes live
  (GitHub/Reddit/X/YouTube/Google/SO). "Errored/empty/timed-out" is a symptom, not a diagnosis. On
  stuck, the harness **auto-researches the error** and forces a different approach.
- **Reuse-first** — checks your own tools, then existing open-source, before building from scratch.
  Includes **web access**: `system_web_tools()` surfaces installed scrape/search/browse CLIs
  (futron-scrape, crawl4ai, browser-use, scrapy, **agent-reach**…) so the LLM uses a battle-tested
  cascade instead of hand-rolling a CAPTCHA-prone scraper. `capabilities` leads with this box.
- **Agentic automation (so "automate through blockers" is real, not a slogan)** — the gates tell the
  agent to drive a browser past what a one-shot call can't do (click, fill, log in, get past a
  challenge). `python3 -m verity web-setup` installs the open-source stack: **Playwright** (low-level
  render/cookie-inject — the path that auto-read auth-walled X Articles AND auto-completed a real OAuth
  login through Cloudflare by using the REAL Chrome binary, not the flagged automation browser),
  **browser-use** (agentic click/fill/navigate), and **openclick** (a11y-driven clicking, if npm). On
  systems that have a richer CUA (FUTRON's futron-claw/avani-cua, or `computer-use`/Claude-in-Chrome
  MCPs), `system_web_tools()` surfaces those too and the agent prefers them. Defer to a human ONLY at a
  real boundary (password/2FA/CAPTCHA/payment) — and the Stop-hook enforces that you TRIED automation first.
- **Walled-platform reach (the Rule-6 fix in code)** — `fetch_tweet(url)` (alias `read_x`, CLI
  `python3 -m verity x-read <url>`) reads X/Twitter posts **and long-form Articles** with no API
  key. Handles every URL form: `x.com/<user>/status/<id>`, `/i/status/<id>`, `/i/web/status/<id>`,
  a bare tweet id, AND the article permalink `x.com/i/article/<id>`.
    - status / bare-id → FxTwitter (the ONLY no-auth backend that returns the **full** article
      body — it lives in `article.content.blocks`, not `text`) → vxtwitter → oembed. Autonomous.
    - `x.com/i/article/<id>` → the article id is NOT a tweet id and has **no** no-auth resolver
      (verified across 7 backends 2026-06-15: fxtwitter/vxtwitter 404, syndication CDN + guest-token
      GraphQL return the article object but the body is auth-gated). So the reader uses your EXISTING
      logged-in session, fully automatically: it finds an X cookie from env (`TWITTER_AUTH_TOKEN`+
      `TWITTER_CT0`), `~/.agent-reach/config.json`, **or auto-decrypts it from Chrome scanning EVERY
      profile** (macOS v10/Keychain; the 2026-06-15 lesson — a logged-in session lived in 'Profile 1',
      so a Default-only probe falsely reported 'not logged in'), then renders the article in a
      cookie-injected headless browser **out-of-process** via any Playwright-capable python
      (`VERITY_PLAYWRIGHT_PYTHON` → `~/.agent-reach-venv` → `python3`), so VERITY's own stdlib-only
      interpreter needn't carry the dep. Verified end-to-end (full 16K-char article through a live
      Chrome cookie). With no session reachable it returns an **honest, actionable** next step (paste
      the *status* URL — reads fully, zero auth — or log into x.com in Chrome), never "unreadable".
  For Reddit / XiaoHongShu / Bilibili / YouTube / LinkedIn / GitHub, install **Agent Reach**
  (github.com/Panniantong/Agent-Reach, MIT) — a multi-backend router; `agent-reach doctor --json`
  shows the live backend per platform. All of this exists because asserting "this site is unreadable /
  API-walled" after testing ONE method is the premature negative Rule 6 forbids.
- **QC self-heal** — `research()` drops garbage (CAPTCHA/empty/error) blocks instead of feeding
  the model noise, and `errorhandling.py` runs a 5-block root-cause protocol (What/Why/Impact/
  Fix/Prevention) + journals every failure, so the harness catches and corrects its own plumbing.
- **🔒 Overconfidence killer — enforced two ways, universal across agent classes** — the gate text is
  advisory (a model rationalizes past it); these fire on a CODE condition, no opt-out. Both target the
  same patterns (`verity/guard.py`): an unverified negative ("it's down / impossible / outage") or a
  premature deferral ("only you can…"). Coverage:
    - **Proxy (daemon — universal, 100% on its path):** the `:11500` server inspects every model
      RESPONSE; on a flagged giveup it **re-prompts the model once, server-side**, forcing investigation
      before returning. Fires for **ANY OpenAI-format model** routed through it (local Llama/Qwen, LM
      Studio, Ollama, Codex/Cursor/etc. pointed at it) — the model can't opt out because the daemon
      sits in the request path. Tags the response `x_verity_overconfidence_guard`.
    - **Claude Code `Stop`/`SubagentStop` hook** (`verity autostart --claude-code` installs it): for
      the Anthropic-format agent that talks direct to the API (bypassing the proxy), it **blocks ending
      the turn** on the same patterns unless the recent tool trail shows logs-read / repair / search /
      an automation attempt. Evidence-aware (earned negatives pass) and loop-safe (per-session cap).
    - **Codex / Gemini:** the injected gate block carries the same rule as standing context; route
      them through `:11500` for the daemon-enforced version. (For Claude Code 100%-enforcement, point
      `ANTHROPIC_BASE_URL` at a VERITY Anthropic-format proxy — on the roadmap.)
- **No single point of failure** — Tier 1 is a CHAIN of models, plus an INDEPENDENT 2nd provider, then
  the local floor: e.g. `gpt-4o-mini → gemini-flash → llama-3.3-70b` (OpenRouter, `LLM_TIER1_MODELS=`)
  `→ Groq` (`LLM_TIER2_URL/KEY` or auto from `GROQ_API_KEY`) `→ local Ollama`. No single model, token,
  OR whole provider being down can take the reasoning layer down. `autostart` sources an optional
  `~/.verity-harness/proxy.env` so the proxy ALWAYS boots redundant. (Motivating failure: one expired
  OAuth shim collapsed everything; now it's one tier among five.)
- **Always-on gate daemon** (`verity autostart --daemon`, macOS launchd KeepAlive) — runs the proxy
  persistently with idle-shutdown OFF, so the discipline layer is **never down and never bypassed by
  being offline**; survives crashes (auto-restart) and boots multi-provider. The strongest form of "the
  gates fire on a code condition, not the model's goodwill" — they're always there.
- **Works for ANY setup (1 model, 1 vendor, or many)** — the tiers adapt to what you configure, and
  the discipline layer (gates, overconfidence guard, verify, calibrate) is model-agnostic, so it's
  identical whether you run five tiers or one local 8B:
    - *Local-only* (no cloud key): Tier1 is skipped entirely → straight to your Ollama floor. You still
      get every gate + the overconfidence guard, just served by your own weights.
    - *Single enterprise model* (e.g. only OpenAI or only Anthropic): set `LLM_TIER1_URL/MODEL/API_KEY`
      to that one vendor → it + the local floor.
    - *Multi-provider*: the full chain + independent 2nd provider + floor (above).
- **Sovereign failover** — cloud → local open weights you own

## Prove it's actually being used (and that it helps)

The gates write an auditable receipt — so "the harness helped" is a log, not a vibe:
```bash
python3 -m verity proof      # receipt: searches fired, assumptions caught + corrected, VERIFIED vs GUESS
python3 -m verity eval       # agentic-search A/B (Seal-0/GAIA shape): naive vs harness lift
python3 -m verity tasks      # multi-step GOAL benchmark (GAIA shape)
python3 -m verity swebench   # SWE-Bench-style: test-scored bug fixing (the coding axis)
```
`proof` reads the decision ledger (`~/.verity-harness/ledger/`); no events = the harness wasn't used.

**If the user asks "does this help MY model? benchmark it" — follow [`BENCHMARKING.md`](BENCHMARKING.md):**
a step-by-step runbook (written for you, the agent) to set up the tiers/keys, run the right
benchmark for their use case, and report the naive-vs-harness table + honest interpretation.
Verified on this repo: a **5-model A/B** (gpt-4o-mini, gemini-2.5-flash, llama-3.3-70b, qwen3.5-flash, gemma-4-31b) on 16 current-info assumption-traps lifted **8% → 91%** (6/80 → 73/80, +67) — *every* model **+12..+14**, deterministic (temp=0 + authoritative registry lookup, not flaky web snippets). HONEST counter-result: on *easy* coding bugs capable models already score 100% naive, so the harness shows 0 lift and can even regress −1 (agentic overhead on trivial fixes). The harness helps where the model NEEDS help — not on tasks it aces one-shot.

## Run it silently in the background (no UI — just on)

Wire VERITY to start with your agent so it's *always working* without you invoking it:
```bash
python3 -m verity autostart --claude-code   # or --shell
```
On session start it quietly self-syncs + starts the proxy floor (:11500); on session END it
**stops** (`verity stop`) so it closes when you exit — no lingering RAM. (Safety net: the proxy
also self-shuts-down after ~15 min idle.) Point your agent
at `OPENAI_BASE_URL=http://127.0.0.1:11500/v1` to inherit failover + the gates transparently —
the way a better model 'just works' when you switch to it.

### ⚠️ Anthropic-format agents (Claude Code / Desktop): the proxy is NOT enough
Claude Code talks **directly to api.anthropic.com** and **cannot** route through the OpenAI-format
:11500 proxy — so the proxy alone never gates its reasoning (`verity proof` stays empty; negative
"it's impossible / doesn't exist" claims slip past Rule 6). **`--claude-code` therefore installs a
SECOND SessionStart hook** (`~/.verity-harness/verity-context-inject.sh`) that injects VERITY's core
gates (Rule 0 pre-flight, Rule 6 search-before-concluding, Verify, Reuse-first, Calibrate) as
standing **context** every session — that is what actually disciplines an Anthropic agent. The proxy
still serves as the sovereign-failover floor + gates anything run via `verity solve/ask` or routed
through :11500. (Discovered 2026-06-15 after a real Rule-6 lapse that the proxy-only setup couldn't catch.)

The injected gates also include an **AUTONOMY** rule: once the user says "proceed / do this / do all
of this", the agent must execute EVERY stated goal **consecutively and autonomously** to completion —
not stop to re-ask for confirmation (wastes the user's time) — pausing only for genuinely destructive,
ambiguous, or outward-facing actions. Every gate (Rule 0/6, Verify, Reuse-first, Calibrate) applies to EACH goal.

### Universal coverage — the gates reach every agent class
The injection mechanism is per-agent because each reads context differently; the gate CONTENT is identical:
| Agent | How it gets the gates | Command |
|---|---|---|
| Claude Code/Desktop (Anthropic) | SessionStart hook → injects context | `verity autostart --claude-code` |
| Codex (codex 5.5) | gates block in `~/.codex/AGENTS.md` (re-injected on each bootstrap regen) | `verity autostart --codex` |
| Gemini CLI | gates block in `~/.gemini/GEMINI.md` | `verity autostart --gemini` |
| Local / OSS / any OpenAI-API agent | route through the proxy — gates fire NATIVELY, no injection | `export OPENAI_BASE_URL=http://127.0.0.1:11500/v1` |
| All of the above | — | `verity autostart --all` |

So OpenAI-format agents (local Llama/Qwen/etc., LM Studio, Ollama-via-OpenAI-shim) get the FULL gate
enforcement transparently through the proxy; Anthropic/Codex/Gemini get the same gates injected as context.

## Use as the executor behind another agent

Run `python3 -m verity.server` for an OpenAI-compatible proxy on `:11500/v1`; point any
agent (Claude Code, Cursor, Codex) at it to inherit failover + guardrail transparently.

## Honest limits

Lift depends on the TASK, not just the model. On facts a model already knows, a strong model
gets ~no lift. But on tasks its weights CAN'T hold — current/post-cutoff info, your specific
tools, multi-step verification — the harness lifts **every** tier: a 4B went 33%→67% on reasoning
traps, and **Opus 4.8 went 25%→100% on current-info traps** (it can't know post-training facts; the
harness's live search supplies them). The counterpoint, reported straight: on *easy* coding bugs a
capable model already scores 100% one-shot, so the harness adds 0 lift and can even regress −1
(multi-step overhead). Make a model better where it NEEDS help — not where it already aces it.
Receipts (including the negatives): see BENCHMARK.md. Re-run on your own suite.

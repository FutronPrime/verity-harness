<!-- VERITY — marketing & launch playbook. Copy here is READY-TO-FIRE. Numbers are from verified,
     reproducible eval runs (see README benchmarks) — never fabricate; if a claim isn't in the repo's
     evidence, cut it. Publishing to public accounts is a human go — these are staged, not auto-blasted. -->

# VERITY — Marketing & Launch Playbook

## 1. Positioning (the one-liner)
**VERITY — the open-source Fable alternative: a zero-dependency harness that makes *any* LLM verify
instead of assume, persist instead of quit, and reuse before reinventing — with a local failover floor you own.**

> ⭐ **LEAD WITH "open-source Fable alternative" EVERYWHERE** — title, first line, hashtags, topics. It's
> the highest-traffic search term and the correct category. (Honest framing: it's the open-source *path to*
> Fable-grade reliability on models you own — not a weight clone. Never claim it IS Fable or matches its raw IQ.)

Sub-positioning by audience:
- *For agent builders fighting hallucination:* "Stop your agent from being confidently wrong."
- *For the local-LLM / sovereignty crowd:* "Frontier-grade discipline on models you run yourself. Zero dependencies."
- *For Claude Code / Cursor / Codex users:* "A drop-in proxy that adds failover + verification to whatever you already use."

The hero frame: **you can't buy Fable's weights (export-banned) — but you can transplant the *discipline*
that makes a frontier model reliable onto any model you own. Same model, only the harness changes. That
lift is the proof.**

## 2. The proof (every number reproducible — `verity eval*`)
Same model, harness OFF → ON:
- **Accuracy** (current-knowledge): **20% → 88%** flagship · **8% → 91%** cheap/local · fresh **gpt-4o-mini 6% → 94%**
- **Research** (forced to read Reddit/X/GitHub): **44% → 100%**
- **Coding** (run the test before "done"): **60% → 93%**
- **Coordination** (multi-agent swarm): **20% → 100%**
- **Memory** (bounded context, infinite store): **4/4 proofs** — injection flat 10→10,000 memories; LLM A/B: hallucination → correct
- **Reuse-first**: **6/7** build-goals surface the right existing tool before building
The killer stat: *even a frontier model gets ~80% of CURRENT facts wrong from memory — reality moved past its cutoff.*

## 3. Differentiators (the pillars — all real, all in-repo)
1. **Zero dependencies** — pure Python stdlib. `git clone` and run. No pip hell.
2. **Model-agnostic + sovereign** — cloud chain → 2nd provider → **local Ollama floor you own**. Vendor can't yank it.
3. **Bounded-context memory that CAN'T touch your data** — own sandbox, add-only, never edits your files, local-only.
4. **Self-improving → self-EVOLVING** — `verity evolve` adopts a better playbook *only if it passes a regression gate*. The thing most "self-improving agent" demos skip.
5. **Reuse-first resource library** — agents consult curated awesome-lists before reinventing.
6. **Registry-grounded** — reads the live model registry instead of guessing stale model ids.
7. **A mascot people remember** — the Truth Hawk 🦅 + VERI the Sun, with a desktop pet.

## 4. Target channels (priority order)
1. **r/LocalLLaMA** — the sovereignty/local crowd; zero-dep + local-floor is catnip. (Highest-fit.)
2. **GitHub** — README is the landing page; topics: `llm`, `agents`, `ai-agent`, `local-llm`, `hallucination`, `openai-compatible`, `self-hosted`.
3. **X/Twitter** — threads with the proof charts + mascot.
4. **Hacker News** — Show HN (lead with the honest benchmark + zero-dep).
5. **Product Hunt** — the mascot + the one-liner do the work.
6. **r/LLMDevs, r/selfhosted, r/artificial** — secondary.
7. **dev.to / Medium** — long-form "I made any model think like Fable" writeup.

---

## 5. READY-TO-FIRE COPY

### A. X launch thread (lead)
1/ Your AI agent's biggest problem isn't intelligence — it's *discipline*. It guesses when it should look things up, quits when it should persist, and says "done" when nothing was checked. VERITY — **the open-source Fable alternative** — fixes that for ANY model. Zero-dependency. 🧵
2/ The bet: what makes a frontier model *feel* reliable isn't only raw IQ — it's judgment under process. Look up current facts. Verify before declaring done. Don't quit on the first wall. Reuse before reinventing. Those are **transplantable**.
3/ Proof = same model, harness OFF→ON, the only change is the discipline:
• accuracy 20%→88%
• research 44%→100%
• coding 60%→93%
• coordination 20%→100%
Every number reproducible on your own models.
4/ The stat that should scare you: even a frontier model gets **~80% of CURRENT facts wrong from memory** — its training cutoff is in the past. VERITY makes it *look things up* instead of confabulating.
5/ It's **zero-dependency** (pure stdlib), **model-agnostic**, and **local-first** — cloud chain → a local Ollama floor you own. Vendor suspends you? It keeps running.
6/ New: bounded-context **memory** that remembers across sessions while staying within budget no matter how much you store — and 🔒 it **cannot erase or corrupt your existing data** (own sandbox, add-only, local-only).
7/ It even **evolves itself** — but gated: a new playbook is adopted *only if it passes a regression check*. Self-improving, not self-corrupting.
8/ Meet the Truth Hawk 🦅 — VERITY's silent mascot (there's a desktop pet too). ⭐ the repo, `git clone`, and make your agent trustworthy: github.com/FutronPrime/verity-harness

### B. X — single punchy posts (pick/schedule)
- "Frontier models get ~80% of *current* facts wrong from memory. VERITY makes any model look it up instead of guessing. Same model, 20%→88%. Open-source, zero-dep. 🦅 github.com/FutronPrime/verity-harness"
- "Self-improving agents are easy. Self-improving without self-*corrupting* is the hard part. VERITY's `verity evolve` adopts a new playbook only if it passes a regression gate. 🔒"
- "Your agent memory tool shouldn't be able to delete your files. VERITY's can't — own sandbox, add-only, local-only, verifiable in source. It only ever *adds*. 🔒"
- "Zero pip installs. Pure Python stdlib. `git clone` → an agent that verifies, persists, and reuses before reinventing — on any model, with a local floor you own. github.com/FutronPrime/verity-harness"

### C. Reddit — r/LocalLLaMA (title + body)
**Title:** VERITY — the open-source Fable alternative: a zero-dependency harness that makes any local model verify instead of hallucinate (with a local Ollama failover floor)
**Body:**
I got tired of agents being confidently wrong, quitting on the first wall, and saying "done" without checking anything — so I built VERITY: a pure-stdlib (no pip) harness that gates an LLM on *code conditions*, not vibes.
What it does, same model harness off→on (all reproducible): accuracy 20%→88% (flagship) / 8%→91% (cheap+local), research 44%→100%, coding 60%→93%, coordination 20%→100%.
Why r/LocalLLaMA might care specifically: it's **model-agnostic** and **local-first** — cloud chain → a **local Ollama floor you own**, so it keeps working if a vendor cuts you off. Zero dependencies, runs anywhere Python does. It reads the live model registry instead of guessing model ids, has bounded-context memory that *cannot* touch your existing files (add-only, own sandbox, local-only), and a gated self-evolution loop.
Repo (MIT, zero-dep): github.com/FutronPrime/verity-harness — would love feedback on the eval methodology (it's `verity eval`, deterministic, runs on your models).

### D. Hacker News — Show HN
**Title:** Show HN: VERITY – the open-source Fable alternative (zero-dep harness that makes any LLM verify instead of assume)
**Body:** Same model, only the harness changes: accuracy 20%→88%, coding 60%→93%, coordination 20%→100% — every number reproducible (`verity eval` on your own models). Pure Python stdlib (no deps), model-agnostic, with a local Ollama failover floor you own. The honest finding baked into the benchmark: even a frontier model gets ~80% of *current* facts wrong from memory, so the harness forces it to look things up. Memory layer is add-only and can't touch your files; the self-evolution loop is gated so it can't self-corrupt. github.com/FutronPrime/verity-harness

### E. Product Hunt
**Tagline:** Make any LLM verify instead of assume — open-source, zero-dependency.
**Description:** VERITY is the Truth Harness: it makes any model (cloud or local) look up current facts, verify before declaring done, persist past walls, and reuse before reinventing — with a local failover floor you own. Same model + the harness = 20%→88% accuracy, 60%→93% coding, 20%→100% coordination, all reproducible. Zero dependencies. Meet the Truth Hawk 🦅.
**First comment:** Built this because I was tired of agents being confidently wrong. The benchmark is honest — it even shows the run where the harness caught its *own* bad eval. Reproduce any number on your own models. Feedback welcome!

### F. Tagline variants
- **"The open-source Fable alternative."**  ← lead tagline (highest-traffic, correct category)
- "The Truth Harness."
- "Make any model think like Fable — without Fable."
- "Verify, don't assume. Persist, don't quit. Reuse, don't reinvent."
- "Frontier discipline. Any model. Zero dependencies."

### G. Hashtags / tags
`#Fable #FableAlternative #OpenSourceAI #LLM #AIagents #opensource #LocalLLaMA #selfhosted #Python #Ollama #hallucination #AItools`
GitHub topics (LIVE): `fable` `fable-alternative` `open-source-fable` `llm` `ai-agents` `local-llm` `openai-compatible` `hallucination` `self-hosted` `python` `zero-dependency` `ollama`

---

## 6. Launch sequence (when DJ greenlights posting)
1. **Day 0:** GitHub topics + banner/social-preview set. Pin the proof scorecard in the README (done).
2. **Day 0:** r/LocalLLaMA post (highest fit) — engage replies fast; the eval-methodology angle invites discussion.
3. **Day 1:** X launch thread + the proof chart + mascot. Schedule the single posts across the week.
4. **Day 2:** Show HN (mid-week morning ET).
5. **Day 3–5:** Product Hunt; dev.to long-form; r/LLMDevs + r/selfhosted.
6. Ongoing: reply with `verity eval` reproductions; the "reproduce it yourself" angle is the moat.

## 7. Honesty guardrails (non-negotiable — it's the brand)
- Every number must be reproducible (`verity eval*`). If challenged, link the command. The v2-dip-caught-its-own-bad-eval story is a FEATURE — lead with honesty.
- Don't claim it makes a weak model smart — it adds *reliability* to a *capable* model (there's a floor; say so).
- Memory safety claim is load-bearing: only ever say "add-only, can't touch your data" because it's true and verifiable.

## Assets (in `assets/`)
logo.svg/png · banner.png · scorecard.svg/png · eval-proof-flagship.png · eval-iterations.png ·
mascot-hawk.png · mascot-sun.png · mascot-hawk-anim.gif · demo-tetris-comparison.png · capability-matrix.svg ·
promo-card.png (generated by `tools/gen_promo.py`).
**demo-verity-live.mp4 / .gif** — the 'caught live' motion promo (stale guess → registry lookup → correct; `tools/gen_demo_video.py`). Use for X video, IG Reel, TikTok.

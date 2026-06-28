# Provenance — proof that every upgrade came from real research, not vibes

VERITY's core claim is that an LLM should **prove it actually researched, reused, and
verified** instead of answering from stale priors (laziness) or shipping a plausible
guess (overconfidence). This file holds the harness to its own standard: each upgrade
below records the **resource → research → diagnosis → upgrade → proof** chain, with the
commit and the tests that lock it. If a row can't show all five, it didn't earn its place.

This is the auditable counterpart to the runtime ledger (`verity proof` /
`~/.verity-harness/ledger/`) and the persistence gate (`verity persist`): the gate forces
the research at runtime; this file is the durable record that it happened.

---

## 1. Persistence gate (R60) — the quit failure-mode, made a code condition

- **Resource:** a real lapse (2026-06-28) — an X-scraper sub-problem 404'd; the agent
  retried one dead library 7× and said "can't fix, wait for compact."
- **Research:** WebSearch + WebFetch across GitHub (gallery-dl #9275, twscrape source,
  twscrape #312), which surfaced the actual cause.
- **Diagnosis:** the conclusion was a quit, not a technical wall. RULE 6/7 (prompt text)
  had been rationalized past.
- **Upgrade:** `verity/persist.py` — a deterministic veto (exit 2) that blocks quit-language
  unless the ledger proves ≥3-of-6-source research, a maintained-alt read, ≥2 distinct
  attempts; plus **proactive mode** (`preflight` / `--proactive`) that forces retrieval at
  task START on any substantive task.
- **Proof:** `tests/test_persist.py` 9/9 · commits e8d768e, 922e4f4 · docs/PERSISTENCE-GATE.md.

## 2. Council-mode — debiased high-stakes eval

- **Resource:** the X-bookmark assimilation matrix flagged `karpathy/llm-council`
  (target VERITY/HARNESS).
- **Research:** fetched karpathy's README — 3 stages, with the explicit note that stage 2
  anonymizes identities "so that the LLM can't play favorites when judging their outputs."
- **Diagnosis:** VERITY's panel+judge gate did NOT anonymize → judges self-prefer → fusion
  inherits the strongest model's bias.
- **Upgrade:** `verity/council.py` — 3-stage council on VERITY's sovereign tiers with
  **anonymized blind cross-ranking** + Borda consensus + a disagreement score (≥0.5 ⇒
  escalate). Counters overconfidence by *measuring* disagreement instead of shipping it.
- **Proof:** `tests/test_council.py` 4/4 (incl. `test_ranking_is_blind`) · commit 45a5176 ·
  docs/COUNCIL-MODE.md.

## 3. Reach — resilient X retrieval as an optional dependency

- **Resource:** the same 404 investigation → `vladkens/twscrape` (maintained 2026).
- **Research:** read twscrape's `api.py`, `queue_client.py`, `xclid.py`; confirmed it tracks
  the rotating queryId/features and computes the real `x-client-transaction-id` against X's
  current `abs.twimg.com/x-web/*.js` bundle.
- **Diagnosis:** the search-before-concluding gate is only as good as the agent's reach;
  hand-rolled X clients break on X's 2–4 week rotation.
- **Upgrade:** `verity/reach.py` + `requirements-reach.txt` — wires twscrape as an OPTIONAL
  dependency (`verity reach`), REUSE > reverse-engineer; core stays zero-dependency.
- **Proof:** commit 922e4f4 · docs/x-scraper-resilience.md (the full source map).

## 4. Surface-aware INGEST-SCAN + `verity vet` — safe auto-vetting of fetched repos/skills

- **Resource:** vetting the 6 real MCP-server repos the agent was about to install
  (codebase-memory-mcp, nango, Agent-Reach, OmniRoute, docling, lingji-cut).
- **Research:** ran `verity_scan` on each; inspected exactly which patterns fired (OmniRoute
  279 = shields.io badges + a `0x200d` emoji ZWJ + "silently" in prose; codebase-memory `rm
  -rf` was an uninstall doc; nango `llms-full.txt` had real role-override text).
- **Diagnosis:** the scanner over-flagged DOCUMENTATION (badges, install curls, design-doc
  data-flow, emoji ZWJ, test fixtures) → it would false-block safe installs, which trains an
  agent to ignore the gate. But the injection threat differs by surface: a SKILL.md becomes
  the agent's directives (strict); a README is documentation (lenient on doc-noise, strict on
  HARD-ALWAYS signals).
- **Upgrade:** `verity_scan.py` — surface calibration (instruction vs doc), HARD-ALWAYS
  (role-override/exfil-of-identity/hidden-unicode — block anywhere) vs HARD-INSTRUCTION
  (exfil/destructive-shell/tool-side-effect — block only where content becomes directives),
  badge + emoji-ZWJ false-positive suppression. `verity/vet.py` — the **safe-before-apply
  gate** (`verity vet <repo>` → SAFE-TO-APPLY / REVIEW / BLOCK, exit 0/1/2) that an agent runs
  before installing anything it fetched, skipping test-data/vendor dirs.
- **Proof:** `tests/test_scan_surface.py` 9/9 + `test_scan_badges.py` 3/3 + `test_vet.py` 5/5;
  verified live: docling/lingji → REVIEW, Agent-Reach/codebase-memory → SAFE, malicious
  SKILL.md → BLOCK. Closes the loop with R60: the proactive-research path sends agents to
  fetch third-party code; `vet` makes sure that code is safe before it becomes instructions.

## 5. Safe-MCP-install — code audit + reversible wiring (R62: engineer past the boundary)

- **Resource:** the obstacle itself — "auto-wiring 6 third-party MCP servers loads untrusted
  code whose tool-descriptions inject into every session." Treated (wrongly) as a hard stop.
- **Research:** inspected each candidate's actual source (not markdown) — found the scanner
  over-flagged `pip install`, install-curls in comments/help-strings, installer `.sh` scripts,
  and string-literal command examples; and that the real threat is runtime download-and-exec.
- **Diagnosis:** the boundary was real for *their installer*, but it was a DESIGN PROBLEM with a
  safe solution, not a stop. Markdown safety (`vet`) wasn't enough — the CODE needed proving too.
- **Upgrade:** `verity/audit_code.py` (`verity audit`) — static code-safety auditor: capability
  report + BLOCK on remote-code-exec / obfuscated-exec / cred+net exfil, with quote-parity +
  exec-sink + comment detection so help-text/data/installers don't false-block. Plus
  `futron-mcp-safe-wire` (FUTRON): vet+audit gate → backup → write your OWN config entry (never
  their installer) → JSON-validate → live MCP `initialize` health-check → auto-rollback.
- **Proof:** `tests/test_audit.py` 10/10 (real backdoors BLOCK, packaging/help-text/installers
  don't); all 6 candidates → REVIEW (no runtime backdoor); live safe-wire attempt auto-rolled-back
  a non-responding server with the config left pristine. commit 9a1fb4c + docs/SAFE-MCP-INSTALL.md.

---

### How to add a row
Every new VERITY feature MUST land with this chain filled in (it's the R60 standard applied
to ourselves). No resource + research + proof → it's a guess, and it doesn't ship.

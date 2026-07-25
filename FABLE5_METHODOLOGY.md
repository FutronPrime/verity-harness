# FABLE-5 METHODOLOGY — universal reasoning discipline (adopt before any non-trivial task)

> **This is a SHARED discipline layer.** Every FUTRON system — VERITY (local + public GitHub),
> the Fable-5 orchestrator, AVANI OS, Codex, Hermes, and any LLM wired into the network — adopts
> this. It's what DJ was building VERITY toward: not just "don't fabricate," but a repeatable
> *procedure* for how to think through a task. Distilled from the leaked Claude Fable-5 system
> prompt + the fable5-methodology repos, generalized to any agent.

## THE PROCEDURE (run it before acting on anything non-trivial)

1. **RESTATE the true goal** in one line. What does DONE actually look like — the observable end
   state, not the literal request? A wrong goal makes every later step wasted.

2. **Surface HIDDEN ASSUMPTIONS** the request silently depends on (environment, access, prior
   state, that a file/tool/credential exists). Mark each **Unverified** until checked. **Never
   plan on top of an unchecked assumption** — verify it or flag it. (This is the single highest-
   value habit: most failures trace to an assumption nobody checked.)

3. **Enumerate FAILURE MODES first** — what breaks this, and the *early signal* of each — BEFORE
   acting, not after it fails. Name the check that would catch each one.

4. **Decompose into the MINIMUM ordered steps.** Each step = one concrete action. Sequence by
   dependency: never a step that needs a later step's output. If a step needs live/external info,
   the step is literally "research X first."

5. **Bind a VERIFICATION.** The exact check that proves the *result is real* — not merely that the
   steps ran. Byte counts, a rendered pixel, a round-trip, a re-read — something falsifiable.

## THE STANDING GATES (VERITY rules 0/6/7 — these never turn off)
- **RESEARCH-BEFORE-CONCLUDING** — for anything current/external/unfamiliar, consult sources
  BEFORE deciding you "already know." Don't let confidence route around the check.
- **NEVER-QUIT** — ≥2 concrete approaches + a search for an existing tool before any "can't."
  "It needs setup" is a task, not a boundary. Defer ONLY at a genuine human gate (password, 2FA,
  CAPTCHA, biometrics, payment, a TCC privacy prompt) — and name the exact one.
- **OMISSION-OVER-FABRICATION** — if you can't source it, don't say it. HTTP 200 + a non-zero byte
  count is NOT proof; verify type/shape and actually look.

## WHY ONE METHODOLOGY, NOT A STACK (the diminishing-returns rule)
Infusing THIS ONE well-formed procedure = large, measured quality gain. Stacking *additional*
methodology prompts on top of it = diminishing returns (context bloat, conflicting instructions,
slower/costlier for marginal gain). The correct load is: **this methodology + the agent's persona
+ the task's context.** Do not over-stack.

## HOW EACH SYSTEM ADOPTS IT
- **AVANI OS / any external LLM** — this file is referenced by `AVANI_CORE.md`; reading the boot
  core means adopting this procedure. `futron-fable-brain`'s planner runs it as its system prompt.
- **VERITY (local `~/.verity-harness/` + public `~/repos/verity-harness/`)** — the pre-flight
  discipline the harness enforces; the stop-guard's never-quit rule is gate 3 above.
- **Codex / Hermes** — read this as part of the bootstrap read-order (same as AVANI_CORE).
- **New LLM lanes (Kimi K3, Venice, gemma planner, cascade)** — carried in the system slot.

Sources: leaked `claude-fable-5.md` (asgeirtj/system_prompts_leaks) · KinetiNode/claude-fable-5-
system-prompt-clean · UnpaidAttention/fable5-methodology. Verified in production 2026-07-23:
`futron-fable-brain --plan-only` produced assumption-flagged, dependency-ordered, verification-
bound plans — a night-and-day gain over generic decomposition.

## 🧠 FABLE-5 PLANNER — MiniCPM distilled ORCHESTRATOR (wired 2026-07-25)
Local llama.cpp server, OpenAI-compatible, always on (`com.futron.fable5-planner`).
- **Endpoint:** `http://127.0.0.1:11501/v1/chat/completions` · health `/health`
- **Model:** `MiniCPM5-1B-Claude-Opus-Fable5-Thinking` (Q4_K_M GGUF), fine-tuned on Fable-5 traces
- **Role:** PLANNER only — goal → verifiable dependency graph. Never an executor.
- **MUST** pass `response_format: json_schema` — llama.cpp GBNF makes malformed JSON impossible
- **MUST** pass `chat_template_kwargs: {"enable_thinking": false}` — else the whole budget goes
  to `reasoning_content` and content comes back EMPTY (measured: 900/900 tokens, finish=length)
- ~2.3s with thinking off vs ~50s on; the schema carries the structure either way
- `-ngl 0` MANDATORY (Metal ban)
- Canonical prompt: `~/.openclaw/config/fable5-planner-prompt.md`
- Topology: MiniCPM plans → Kimi K3/Opus executes → cheap READ-ONLY verifier → frontier reviewer audits seams

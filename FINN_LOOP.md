# FINN-LOOP — the human-gated build loop (adopt alongside FABLE5_METHODOLOGY)

**Source:** Alex Finn's loop-engineering ("Prompting is dead — build loops") + github.com/finna/Finn-loop.
**Thesis:** stop one-shot *prompting*; run a **loop** that specs → builds → self-reviews → iterates,
and only escalates to a human for the irreversible call. Loops out-produce prompts because the
test/verify/fix cycle is automated instead of manual.

## The loop (three phases)
1. **SPEC** — turn a goal into a **contract**, not a vibe:
   - **Acceptance Criteria (AC-1…N)** — testable statements of what "done" means.
   - **Non-Goals (NG-1…N)** — explicitly out of scope; **binding constraints**, not suggestions.
   - Block on ambiguity; flag every **Unverified** assumption (Fable-5 gate) before building.
2. **BUILD** — implement **strictly within the contract**. Satisfy every AC; touch nothing in NG.
   Verify locally before declaring the cycle done (run it, don't assume).
3. **REVIEW** — a **FRESH reviewer** (new context, no builder bias) judges the artifact against
   EACH AC and EACH NG and returns exactly one verdict:
   - `loop-approved` — every AC met, no NG violated → ready for a **human** to merge/ship.
   - `loop-changes-requested` — specific fixable gaps → one more BUILD cycle with those gaps.
   - `needs-human-review` — ambiguous, sensitive, or low-confidence → escalate to the human.

## The laws (non-negotiable)
- **HUMANS MERGE.** Agents NEVER commit, merge, deploy, or take the irreversible action. The loop
  produces a review-ready artifact + a verdict; a person makes the final call. (Aligns with the
  FUTRON confirm-before-outward-action rule and Rule 43 deletion protection.)
- **loop-stuck cap.** After **2** failed fix cycles, stop and escalate `needs-human-review` — never
  grind forever.
- **Scope is a contract.** Comment-style "also do X" mid-run is rejected; scope only changes by
  editing the spec/contract. Non-goals prevent scope creep.
- **Fresh reviewer.** The builder never grades itself; spawn a clean context for review.
- **Durable state (scale-up).** For real projects, back the queue with a source of truth (Linear
  issues ↔ GitHub PRs + CI status checks); label-driven flow (`agent-ready` = the sole human approval
  gate, `blocked` halts, `loop-stuck` caps retries); cooperative locking (assignee) prevents double-builds.

## How each system adopts it
- **futron-fin-loop** — the executable: `futron-fin-loop "<goal>" [--kind code|plan|content|design]
  [--max-fix 2]`. SPEC→BUILD↔REVIEW on the Fable-5 brain; emits verdict + review-trail; **never merges**.
- **VERITY** (local `~/.verity-harness/` + public `~/repos/verity-harness/`) — this file dropped in;
  the harness's execute path treats AC/NG as the completion gate and the verdict taxonomy as its exit.
- **Fable-5 orchestrator (`futron-fable-brain`)** — plans as contracts (AC/NG), and any build request
  routes through the loop, not a single shot.
- **AVANI OS / boot cores** — referenced from the persona core (public build: `ORION_CORE`; evolves with the user) and its boot generator, so a regen keeps it. The FUTRON reference implementation is `futron-fin-loop` + `futron-fable-brain`.
- **Claude Code (me)** — for any multi-file/feature build: spec the contract, build in scope, spawn a
  fresh review pass, and stop for DJ to merge. Don't one-shot; loop.

## One guardrail
Finn-loop is the *workflow*; Fable-5 is the *reasoning discipline inside each step*. Use BOTH, not five
competing loop frameworks. One loop + one methodology + persona + task-context.

# OVS PROTOCOL — validate the work in a context that cannot defend it

Adopt alongside `FABLE5_METHODOLOGY.md` (reasoning discipline) and `FINN_LOOP.md` (build loop).
FABLE-5 governs how you *think*; FINN-LOOP governs how you *ship*; OVS governs how work gets
*graded*. Tool: `futron-ovs` (FUTRON) — the protocol below is portable to any harness.

## The problem it solves
Self-critique inside the same context is unreliable: the model is grading tokens it already
committed to, and it defends them. Long runs additionally drift — constraints stated at step 1
quietly stop being honoured by step 40 (narrative inertia). Neither failure is visible from
inside the run.

## The procedure

1. **GRADE IN A FRESH CONTEXT.** Extract the spec and the deliverable into an isolated
   context — new process, no conversation history. This must be *structural*, not a promise to
   "evaluate objectively." If the grader can see the reasoning that produced the work, it is
   not an independent grader.

2. **TWO INDEPENDENT DETECTORS, ALWAYS.** Never let a single judge — especially a small model —
   be the gate. Run a deterministic/structural check *and* a model judgment. Either definite
   failure fails the work. **An unclear or unavailable verdict is the absence of evidence, never
   evidence of a pass.**
   > Measured 2026-07-24: given a deliverable that used `eval()` against an explicit
   > "do not use eval" constraint, with no docstring, no type hints and no code fence, a 1B
   > auditor model returned `VERDICT: NOMINAL`. It passed broken code. The deterministic
   > detector is what caught it. This is why the rule exists.

3. **CHECK AT INTERVALS, NOT AT THE END.** Validate every N steps so drift is caught while it
   is still cheap to correct. Post-hoc review finds the damage after it has propagated.

4. **ESCALATE, DON'T FRONT-LOAD.** Cheap gate first; spend heavy reasoning only on failures.
   This is adaptive effort — the point is to *not* pay for deep analysis on nominal output.

5. **ON FAILURE, FIND THE STRUCTURAL CAUSE.** Run 5 Whys until you reach a cause that is
   structural rather than incidental, then emit a **corrected instruction block** — a drop-in
   prompt fragment that makes the failure impossible to repeat. Fixing the output is not fixing
   the system.

6. **ONE LESSON, ONE FILE.** Each corrected failure becomes a single markdown file with a
   one-line summary on the first line. Not a growing log — a retrievable index.

## The standing gates (never turn off)

- **The builder never grades itself.** Inherited from FINN-LOOP; OVS makes it enforceable.
- **A small/cheap judge may only ever be one of two detectors, never the sole gate.**
- **Absence of a verdict is not a pass.** Fail closed.
- **Never gate on the hot path.** Validation belongs at completion boundaries
  (subagent finished, task completed, tool failed), never on every tool call — a validator that
  runs on every action adds latency to everything and can deadlock the agent it audits.
- **Report what the detectors actually said**, including disagreement, rather than collapsing to
  a single verdict. Disagreement is signal.

## Measurement doctrine (for anything that routes models or effort)

- **Route on cost-per-task, not price-per-token.** A model at half the price that uses twice the
  tokens is a wash. Score quality, tokens, cost and wall-clock *separately* — they disagree.
- **Benchmark your effort tiers; do not assume higher is better.** Observed on a public
  frontier benchmark: the *highest* thinking tier scored *lower* at *higher* cost than a middle
  tier. An effort router built on "harder problem → max effort" can be paying more for worse.
- **An aggregate benchmark win is not a per-domain win.** Pin domain-specific lanes to their own
  evidence; headline gains have coincided with regressions in specific domains.
- **Instrument safety-classifier fallback.** A blocked request may be silently re-routed to a
  different model and billed at that model's price — this corrupts both benchmark cells and cost
  accounting without erroring.
- **Eval-fixture discipline:** hold everything constant except the variable under test — pin the
  effort level, pin the tool/MCP set, keep prompts as versioned assets, run arms in parallel.

## How each system adopts it

- **FUTRON** — `futron-ovs {audit|verify|rca|lesson}`. Composes with `futron-logician`
  (deterministic enforcement) and `synapse-sentinel` (self-heal monitor); does not replace them.
  Canonical: `memory/subsystem-synapse-ovs.md`.
- **VERITY / ORION** — apply the procedure manually where no daemon exists. The protocol needs
  no infrastructure: a second process, a spec, and a deliverable are sufficient.
- **Any agent harness** — wire to completion-boundary lifecycle hooks
  (`SubagentStop`, `TaskCompleted`, `PostToolUseFailure`, `StopFailure`). Never `PreToolUse`.

## One guardrail

OVS is a grader, not an author. It must never rewrite the deliverable — only judge it, explain
the structural cause of a failure, and hand back corrected *instructions*. A validator that
edits the work has become a worker, and there is no longer anything grading the output.

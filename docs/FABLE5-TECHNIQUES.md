# Fable-5 Workflow Techniques → VERITY

Distilled from 3 practitioner videos (David Ondrej, Sean Kochel, AI Edge) on extracting maximum value
from Claude Fable 5. 34 techniques extracted; the VERITY-relevant applies below. **1 technique was
deliberately refused** — a prompt-rewriter that neutralizes safety refusals (evading a safety layer is
out of scope for a *discipline* harness).

## Shipped this pass
- **`verity fixed`** — known-fixed-bugs ledger (Kochel): record a fix, gate any plan against it so a
  solved bug can't be silently reintroduced. Exit 2 on regression risk. `verity/regression_ledger.py`.
- **`futron-longrun`** (FUTRON side) — caffeinate-wrapped overnight autonomous runs (Ondrej).

## Technique → VERITY mapping (novelty-tagged)
| Technique | Source | In VERITY |
|---|---|---|
| Orchestrator/actor split — powerful model plans, cheap open-source mod | David | ✅ have: Encode as a router policy in verity/router.py: a 'planner-vs-actor' gate that classifies each task by cognitiv |
| Have the strongest model author reusable Skills (SOPs) that uplift wea | David | ↑ reinforces: Add `verity skill-author <task>` command that runs the top model to emit a vetted SKILL.md, then auto-passes i |
| Periodically delete 80–100% of your skills and re-add only what a stro | David | 🆕 new: Build `verity skill-audit`: benchmark a task-set with skills OFF vs ON (reuse eval_tasks.py harness), report p |
| Test-heavy execution as a default, not an afterthought | David | ✅ have: Already the core of VERITY's 'verify-before-completion' + anti-quit gates. Strengthen persist.py so a draft cl |
| Overnight autonomous long-runs with the display kept awake (caffeinate | David | 🆕 new: VERITY has loop.py / looplib / ralph-loop-style recurrence. Add a `verity loop --caffeinate` flag (and a docto |
| Build datasets by scheduling a polling job that captures model outputs | David | 🆕 new: Add `verity capture <question-set.jsonl>` that runs a battery through the current router and writes a timestam |
| Self-host model weights and datasets locally for sovereignty (own your | David | ↑ reinforces: VERITY already sells 'local-first, keyless Ollama routing, can't-be-revoked.' Add a documented `verity mirror` |
| Prompt-rewriter skill that neutralizes false-positive safety refusals | David | 🆕 new: Risky to encode wholesale. Safer VERITY framing: a 'refusal-triage' step in persist.py that, on a false-positi |
| Build for agent-consumption first: CLI tools, clean APIs, clean docs o | David | ↑ reinforces: Add a 'agent-usability' lint to `verity audit`: a new tool/command fails review unless it has a documented CLI |
| Per-agent model gateway: cheap-fast model on groundwork, top model on  | David | ✅ have: VERITY router.py already does per-task model selection; expose a per-agent model-declaration field in the exec |
| Meta skill-audit: use a dedicated 'audit-skill' skill to run a strong  | Sean | ↑ reinforces: Add a `verity audit-skill <path>` subcommand: given a skill/policy file, it lints for (a) rules declared but n |
| Audit the seams, not the process — check that upstream context actuall | Sean | 🆕 new: Add a `verity seams <pipeline-manifest>` gate: parse the phase manifest, assert every field captured in phase  |
| 'Zoom out and think' command for recurring bugs — force system-level r | Sean | 🆕 new: Add a `verity rootcause` gate triggered when git log shows N commits touching the same file/area with 'fix' me |
| Diagnose the human-driven miss, not just the model — 'can't blame ever | Sean | ↑ reinforces: Add a `verity decisions-ledger` check: every conclusion tagged as a required pattern in a research/spec doc mu |
| Slow down on spec processes for complex/agentic patterns — depth of sp | Sean | 🆕 new: Add a `verity spec-depth <spec>` gate keyed on feature tags: if tagged agentic/stateful, require checklist ite |
| Model-as-orchestrator, cheaper-model-as-implementer split | Sean | ✅ have: Add a `verity intent-header <spec>` check: a spec handed to a downstream executor must contain a non-empty 'in |
| Differential audit: run the same task twice (with/without prior contex | Sean | 🆕 new: Add `verity diff-audit <planA> <planB>`: diff two plans for the same goal, flag (a) reintroduction of patterns |
| Maintain a 'known-fixed bugs' ledger so plans can't silently reintrodu | Sean | 🆕 new: Add a `verity regression-check <plan>` gate: grep the plan against known-fixed-bugs.md entries; a match withou |
| Force capability claims to be doc-grounded (Context7 / official docs)  | Sean | ✅ have: Extend R60's `verity persist` logic: a plan containing capability claims about a named tool/platform must incl |
| Ground the audit in web-searched current best practices for the specif | Sean | ✅ have: This is already R60. Reinforce: `verity persist` should treat a root-cause/diagnosis draft the same as a 'can' |
| Loops (/loop) — recursive autonomous execution on an interval | AI | ✅ have: Add `verity loop-audit <spec>` gate: any unattended loop must have (a) an idempotent/de-duped append target an |
| Goal-prompt discipline — define 'done' as verifiable exit conditions | AI | ↑ reinforces: Extend the existing `verity persist`/R60 mechanical gate to reject a task draft lacking a concrete checkable a |
| Skills as self-evolving recipes updated from real feedback | AI | 🆕 new: Add a `verity skill-feedback` doc/command: after a skill run, require a logged outcome entry (metric + verdict |
| 10/80/10 multi-model tiering — smartest model for framing + review, ch | AI | ↑ reinforces: Add a `verity review-gate`: an autonomous loop cannot advance to the next iteration until a top-tier-model ver |
| Exploit Fable's state-of-the-art vision for visual verification and de | AI | ↑ reinforces: Add a `verity visual-verify` step for any change to rendered artifacts (dashboard UI, storyboards, ad creative |

## Already core to VERITY (validated, not new)
Planner/actor split, test-heavy verify-before-done, local-first keyless routing, self-evolving playbook,
adversarial critic, decision ledger — these appeared across all three videos as 'do this' advice and are
already enforced gates here. External validation of the harness's design.
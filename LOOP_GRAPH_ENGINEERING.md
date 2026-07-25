# LOOP & GRAPH ENGINEERING — the VERITY execution protocol

> Companion to [FABLE5_METHODOLOGY.md](FABLE5_METHODOLOGY.md) (how to *reason*),
> [OVS_PROTOCOL.md](OVS_PROTOCOL.md) (how work gets *graded*), and
> [FINN_LOOP.md](FINN_LOOP.md) (the spec→build→review cadence).
> This one covers how work gets **structured and executed**.

Distilled 2026-07-25 from a 49-resource review. Every claim below is traceable to a
named source; nothing here is invented.

---

## 0. THE ONE RULE THAT GATES EVERYTHING

> **A loop is a goal plus a thing that can say NO.**
> **If nothing can tell the agent it's wrong, you don't have a loop — you have an agent
> producing work faster than a human can check it.**
> — *Frontier-Intelligence-Lab/loop-architect*

The bottleneck was never *generating* work. It is **verifying** it. And an agent that
grades its own work cannot be trusted to: it will delete the failing test or narrate a
success it did not achieve.

**Therefore: find the verifier FIRST, or do not loop.** This is a blocking gate, not advice.

### The verifier strength ladder

| tier | kind | example |
|---|---|---|
| 6 | deterministic | exit code, assert, diff, checksum, test suite passes |
| 5 | measured | AUC ≥ 0.72, latency < 200ms, count == N |
| 4 | executable | a command someone can run |
| 3 | artifact | a named file exists with named contents |
| 2 | observable | "it renders", "it appears in the log" |
| 1 | **narrative** | *"looks good", "review the output"* — **NOT A VERIFIER** |

**Tier 1 does not count.** Pair the tier with **blast radius**: a side-effectful step with a
tier ≤2 verifier must never run unattended. Strengthen the check or keep a human in it.

---

## 1. LOOP ENGINEERING — three parts, always

Every loop has exactly three, and a loop missing any one is not a loop:

1. **TRIGGER** — how it starts. Ideally autonomous: a schedule or an event.
2. **TASK** — the single thing it does.
3. **SUCCESS CRITERIA** — how we know it worked. **On failure it re-runs from the start.**

Store every run. Stored runs are what make self-improvement possible later.
*(Alex Finn, "Prompting is dead. Here is how you create loops"; SAILL.)*

### Guard rails around the loop

- **PRE-CHECK BEFORE YOU SPEND.** Cheap static checks first — does the file exist, is the
  tool installed, does the goal even contain an action verb. Preview the plan with per-step
  risk and allow approve / reject / **edit** before anything runs.
  *(uninhibited-scholar/precheck-guardian)*
- **COMPRESS THE CONTEXT GOING IN.** Brief a step from its **ancestry**, not the whole plan.
  40–80% window reduction. *(context-compressor; MindMap)*
- **STEER THE LIVE RUN AT ROUND BOUNDARIES.** Inject, pause, or guard **only between
  rounds** — never mid-tool, so a half-finished write is never torn apart.
  **Safety by construction, not by locking.** *(uninhibited-scholar/something-else)*

---

## 2. GRAPH ENGINEERING — connected loops, not a task list

> **Graph engineering is loop engineering applied to every node.**
> *(Chase AI, "Move Over Loop Engineering, Graph Engineering Is Now Here")*

| | LOOP | GRAPH |
|---|---|---|
| agents | one, doing everything | N, each doing one atomic task |
| success | **murky** — *"is this report good?"* | **crisp** — *"≥5 sources", "≥2 paragraphs", "a so-what per source"* |
| failure | *"somewhere in the run"* | **localised to one node** |
| context | one window absorbing everything | one clean window per node |
| speed | serial | parallel branches |

**A graph is not a task list with arrows. Each node is a COMPLETE LOOP** — its own trigger,
task, success criterion and retry budget. If a node has no success criterion of its own, it
is a step in a flat plan wearing a graph's clothes.

Why success gets crisper: **narrow tasks admit sharp checks.** "Is the report good" is
unanswerable; "did this return ≥5 sources" is not.

### When to go graph — exactly three triggers

1. **Context rot** — one agent's window would reach ~300–500k tokens over the run.
2. **Independent review** — high-stakes output the maker cannot honestly judge. Bring a
   different agent, **ideally a different model**.
3. **Timing** — branches are independent and serial execution wastes wall-clock.

> **"If you don't know if you need it, the answer is probably no."**

Same refusal shape as *don't loop this*. Added agents are a **cost**, not a feature. Most
tasks need a single loop.

---

## 3. ROLE TOPOLOGY — cost-tiered, with one structural guarantee

*(gnukum511/goalloop)*

| role | tier | why |
|---|---|---|
| Planner (1 call/run) | frontier | a bad plan is the most expensive failure in the system |
| Loop orchestrator | mid | dispatch and bookkeeping is not frontier work |
| Workers (default) | mid | first attempt on everything |
| Escalation lane | frontier | **only after 2 failed checks** — pay premium for proven-hard work |
| **Verifier** | **cheap** | **READ-ONLY tools.** Runs the check itself |
| Reviewer (1 call/run) | frontier | audits the **seams**; distils lessons into `memory/` |

**The verifier's read-only tool set is the load-bearing detail.** "Workers never
self-certify" must be *structural*, not a prompt instruction — a worker that *can* edit can
delete the failing test. Take the capability away and the failure mode disappears.

**Audit the seams.** Every node can pass its own check while the *joins* between them are
broken — all green, system still wrong. Per-node verification is structurally blind to this,
so it needs its own pass.

**Close the loop across runs:** reviewer → `memory/` → next plan.

---

## 4. NAMED WORKFLOWS — define once, invoke by name

*(HorizonBrute/SAILL — "SQL for agent-loop definitions")*

```
### Audit & Fix
1. Implementer (#lowcost) — applies the change.
2. Validator  (#midcost)  — runs the audit suite against the change.
   **Loop:** on failure, return specific findings to "Implementer" and re-run from there;
   repeat until the Validator passes clean or 3 iterations, then stop and report.
```

Claimed **80%+ token reduction** vs restating the workflow every session. In practice the
saving is larger: reuse skips the **planner call itself**.

---

## 5. THE CHECKLIST

```
[ ] Named the VERIFIER before writing any step?          (tier ≥3, or don't loop)
[ ] Every loop has TRIGGER + TASK + SUCCESS?
[ ] Pre-checked cheaply before spending tokens?
[ ] Graph JUSTIFIED by one of the 3 triggers?            (default: no — use a loop)
[ ] Every graph node is a COMPLETE loop, not a step?
[ ] Verifier has READ-ONLY tools?                        (structural, not instructed)
[ ] Escalation gated at 2 failures?
[ ] SEAMS audited separately from nodes?
[ ] Live run steerable at round boundaries?
[ ] Lessons written back to memory for the next run?
```

---

## Reference implementation

`futron-orchestrate` (plan → DAG → verifier gate → seam audit → roles → SAILL teams) and
`futron-loop-steer` (enqueue / pause / guard at round boundaries).

## Sources
loop-architect · SAILL · precheck-guardian · context-compressor · something-else · goalloop ·
Finn-loop · ccpm · kanban-md · opencode-ralph-rlm · LOOP-STATION · multi-agent-loop-kit ·
zeroshot · Agentless · looper · LoopEngineering-CrashCourse · loop-engineering · LAPP ·
hermes-agent · Aurevoy · chat2goal · MindMap · ProG · Chase AI and Alex Finn (video).

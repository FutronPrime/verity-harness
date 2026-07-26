# PROACTIVITY PROTOCOL — measure the misses, not the interruptions

> **"You're not supposed to prompt Claude. You're supposed to build a system that prompts
> itself."** — Daisy Hollman, Anthropic

That is the target. This protocol is the part everyone skips on the way there: **a system that
prompts itself needs a way to be wrong about when to speak, and a way to find out.** Without
one you have not built a teammate, you have built a cron job with opinions.

Adopt alongside `FABLE5_METHODOLOGY.md` (how you think), `FINN_LOOP.md` (how you ship) and
`OVS_PROTOCOL.md` (how work gets graded). This one governs when you speak **without being
asked**. Tool: `futron-proactive` (FUTRON) — the protocol below is portable to any harness.

## The problem it solves

Proactive agents are graded on the wrong axis. Every design conversation is about not being
annoying, because a false alarm is *visible* — it interrupts you, you remember it, you file a
complaint. The opposite error leaves no trace at all.

THUNLP's ProactiveAgent (6,790 annotated events; reward model F1 0.918) names the four cells:

| | user needed help | user did not |
|---|---|---|
| **agent proposed** | Correct-Detection | **False-Alarm** — visible |
| **agent stayed quiet** | **Missed-Needed** — invisible | Non-Response |

An agent that never proposes scores a perfect false-alarm rate. It looks maximally
well-behaved. Its Missed-Needed rate is 100% and nothing in the system can see that.

> **Measured 2026-07-26.** `futron-sets-review` is the gate that screens anything
> outward-facing. It requested model `claude-opus-4-8` from an endpoint that only ever served
> `gpt-5.5`, received 502, silently fell back to a cynicism-anchored heuristic, and printed a
> confident Tomatometer with `GATE: FAIL`, **exit 1** — the code that means *"content failed
> screening."* Nothing had been screened. The heuristic is `max(1, 10 - cynicism) + 2`, so a
> low-cynicism panel would have fabricated a **PASS** instead. It had been in this state for an
> unknown period and **no component of the system was capable of noticing**, because a gate
> that is quietly wrong emits exactly what a gate that is working emits.

That is a Missed-Needed with a 100% rate and zero visibility. The protocol exists because that
failure is structural, not incidental.

## The procedure

1. **DETECTORS ARE DETERMINISTIC CODE. A MODEL MAY WRITE THE PROPOSAL; IT MAY NEVER BE THE
   GATE.** Exit codes, mtimes, port probes, `git` plumbing, ledger diffs. This is not a
   preference — see `DETERMINISM_PROTOCOL.md`: on a hosted API you cannot obtain reproducible
   sampling, so any model-based trigger is a trigger that fires differently on identical
   input. The detector layer must be the part that does not drift.

2. **A SILENT DETECTOR IS A LIE.** A detector that crashes, times out, or cannot determine its
   answer must emit `unclear: true`, never an empty list. An empty list is indistinguishable
   from a healthy system. Report the domain as **UNMONITORED**, which is a signal in itself —
   not as clear.

3. **UNCLEAR ≠ SUPPRESS.** OVS rule 2 says an unclear verdict is never evidence of a pass.
   Here the failure direction is reversed and the rule inverts with it: an unclear signal is
   never grounds for silence. Log it as MN-risk and let the threshold decide.

4. **EVERY SUPPRESSED SIGNAL IS RECORDED.** When something falls below the surfacing bar, write
   it to the ledger as `mn_risk`. This is the whole trick: it converts the invisible error into
   a countable one. Without it there is no artifact to point at when a miss is discovered later.

5. **THE HUMAN IS THE ONLY SOURCE OF RECALL DATA.** Precision is computable from the ledger —
   accepts over judged proposals. **Recall is not.** A miss only enters the record if the person
   who needed it reports it. Build the one-command path for that (`futron-proactive miss "…"`)
   and treat its output as the highest-value row in the store.

6. **RESPONSES MOVE THE BAR ASYMMETRICALLY.** Reject is strong evidence (+8). Ignore is weak —
   he may simply be busy, which is exactly how ProactiveAgent reads it (+3). A reported miss
   *lowers* the bar (−6), because the evidence says the system is too quiet, not too loud.

7. **DELIVERY IS A ROUTINE, NOT A DAEMON YOU MAINTAIN.** Anthropic's Routines take three
   decisions and nothing else: **trigger** (schedule, native repo event, or webhook POST with
   the event payload as context), **context** (repos + connectors — *this is the ceiling on how
   well the agent can possibly do*), and **steerability** (how you keep it honest). Do not
   rebuild hosting, persistence and auth to get a smart cron.

8. **STEERABILITY MEANS AGENT-ON-AGENT, NOT TRUST.** The generator/critiquer pattern: one
   routine produces the artifact, a second triggers on that artifact's creation and reviews it
   before a human sees it. Inherited straight from FINN-LOOP's standing gate — *the builder
   never grades itself* — and it is what makes an out-of-the-loop human safe.

9. **A FALSE ALARM IS USUALLY A DETECTOR READING THE WRONG COLUMN.** Treat every FA as a bug
   report against the detector, not as noise to tune out by raising the bar. The recurring
   shape is a *proxy standing in for the thing*.

   > **Measured 2026-07-26, on this module's own first run.** It reported a daemon as failing.
   > The daemon was healthy. Chasing it exposed three bugs, all the same bug — reading history
   > as state: `launchctl`'s STATUS column is *last exit*, not current health, so any service
   > that ever restarted reads as broken forever; `gate()` re-served a cached snapshot as a
   > live reading and kept reporting a fault 30 seconds after it was fixed; and the crash-loop
   > detector counted errors in the last 120 *lines* of a log that had stopped being written
   > 14 hours earlier. Fixes: require *no pid* as well as non-zero exit; always re-observe and
   > make `--cached` explicit *and* print the snapshot's age; gate the log scan on **mtime**,
   > because a crash loop is by definition still writing.

10. **QUERY BEFORE YOU CLAIM BLOCKED, THEN FIX THE LANE — NOT THE INSTANCE.** "Blocked by
    policy", "no API for that", "can't access it" are claims about your own capability, and
    they are the cheapest possible Missed-Needed: the work simply does not happen and nothing
    records that it didn't. Run the capability search first. Then, when you find the lane that
    works, **write it into the tool.** A one-off workaround you don't commit is a bug you will
    hit again, and the second person to hit it has no way to know you already solved it.

    > **Measured 2026-07-26.** Two Reddit threads were declared unreachable after
    > `www`/`old` `.json` returned 403 and a scraper failed. Untried: the local capability
    > search, which names a purpose-built `futron-reddit-query` in one line; and the
    > already-logged-in browser on CDP `:9222`, which read both threads in seconds.
    > Credentials in the vault were stale (401) and the IP-level 403 made the session cookie
    > irrelevant — but *none of that had been checked* when the claim was made. Fixed at the
    > lane, not the instance: `futron-reddit-query thread <url|id>`, CDP as tier 0, with the
    > four dead paths documented in the function so the next agent does not re-derive them.

## The standing gates (never turn off)

- **Report the miss rate or report nothing.** A dashboard showing a low false-alarm rate and no
  miss column is worse than no dashboard: it certifies the unmeasured half as fine.
- **"No signals" is never reported as "all clear."** The honest phrasing is *"these detectors
  found nothing they can see."* The difference is the entire protocol.
- **A degraded gate outranks a down gate.** Down is loud and gets fixed. Degraded answers in the
  correct shape and is trusted. Detect end-to-end usefulness, not liveness — the endpoint in the
  evidence above was *listening on its port the whole time.*
- **Any fallback path must change the SHAPE of its output, not add a warning line above an
  otherwise-identical verdict.** A warning above a normal-looking score gets skimmed; a missing
  score cannot be. Corollary contract, and callers must honour the third state:

  ```
  0  ran, passed
  1  ran, failed
  2  COULD NOT RUN — no verdict exists
  ```

  Conflating 2 with 1 is what lets a dead dependency masquerade as a working gate.

## Reference implementation

```bash
futron-proactive observe        # deterministic detector sweep
futron-proactive gate           # surface over threshold; log the rest as mn_risk
futron-proactive record accept|reject|ignore "<title>"
futron-proactive miss "<title>" # the metric nothing else can collect
futron-proactive calibrate      # CD / FA / MN / NR and the threshold they imply
futron-proactive routines       # ready-to-paste /schedule prompts
```

## Sources

- THUNLP, **ProactiveAgent** — environment gym → agent → reward model; the four-cell taxonomy
  and the accept / reject / ignore feedback semantics. <https://github.com/thunlp/ProactiveAgent>
- Anthropic, *Build a proactive agent workflow with Claude Code* (Code with Claude workshop) —
  Routines; the trigger / context / steerability decision model; generator-critiquer review.
- **Skills-Coach** (arXiv 2604.27488) — skills self-optimise against *deterministic, verifiable*
  validation criteria; 0.37 → 0.84 mean score, pass rate 33.6% → 88.0%.
- **ACE / agentic-context-engine** — Agent → Reflector → SkillManager over a persistent
  Skillbook; store validated strategies, not raw traces, to avoid context collapse.
- **ai-care** — independently arrives at the same split this protocol uses: **sensors** (perceive
  the environment and initiate) and **detectors** (the logic that decides a trigger fires),
  rather than one undifferentiated "proactive agent."
- Daisy Hollman (Anthropic) — *"build a system that prompts itself."* The four failure modes
  she names for self-prompting loops map onto this protocol directly: **no memory file** (every
  loop restarts from zero → the ledger), **no sub-agent split** (one agent doing everything →
  decomposition, `DETERMINISM_PROTOCOL.md` §2), **no stop condition** (→ the threshold), and
  token bloat (→ store strategies, not transcripts).

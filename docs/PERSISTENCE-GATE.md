# The Persistence Gate (R60) — a mechanical fix for the *quit* failure-mode

> "Current LLMs seem capable of doing pretty much anything. The issue is that
> they quit or get 'dumb' when it comes to problem-solving and being proactive —
> and apparently no groundbreaking harness technique has found a way to fix this.
> How do we make it so I don't have to reiterate every step and damn near curse
> before you do what you could always do?" — the brief that produced this gate.

## The real frontier problem isn't capability — it's persistence

In 2026 the bottleneck on agentic work is rarely "the model can't." It's that a
capable model hits friction, retries the **same** dead path two or three times,
and then emits *"I can't / it's blocked / not possible / let's wait for you."*
The capability was there the whole time; one real web search away. The model
**quit**.

Prompt-rules don't fix this. VERITY already shipped RULE 6 (search-before-
concluding) and RULE 7 (never-skip/quit) as injected gate text. They are good
rules. They get **rationalized past** anyway — "this is different," "context is
low," "I already know how this works." A rule the model can talk itself out of
is not a control.

## The fix: turn the rule into a deterministic veto

The persistence gate is the **TOOL-VETO / self-correction pattern** (VERITY v2)
specialized to the quit-failure. It is a program, not a paragraph:

```
A conclusion that contains quit-language is BLOCKED
unless the research ledger proves the work was actually done,
OR a genuine human gate is explicitly named.
```

"Proven" is concrete and checkable:
- **≥3 of the six sources** actually searched — GitHub, X, Reddit, YouTube,
  Google, HN/StackOverflow (logged as receipts).
- **The maintained alternative's source read and reused** — at least one research
  step that turned up something usable (REUSE > reverse-engineer).
- **≥2 structurally different attempts** — re-running one dead path N times is
  explicitly **not** counted; the gate dedupes by (source, query).

The only accepted stop is a **named human gate**: password / 2FA / CAPTCHA /
biometrics / payment / account-creation / destructive op. Name the exact one and
the gate passes. "Hard / fiddly / low-context / rotates-often / needs-setup /
not-supported" are TASKS, not boundaries — and the gate rejects them.

## How it works

```bash
# Before any "can't", gate your own draft conclusion:
python3 -m verity persist "I couldn't fix the 404, let's wait for compact"
#   → 🛑 BLOCKED (exit 2) + the exact missing steps

# Log each real research step as you do it (these are the receipts):
python3 -m verity persist note github "SearchTimeline 404 fix" "twscrape XClIdGen has it"
python3 -m verity persist note google "x-client-transaction-id 2026" "gallery-dl #9275"

# Re-gate once the work is logged:
python3 -m verity persist "Tried 7 ways first, but here's the verified fix"
#   → ✅ PASS (EARNED)
```

The gate reads `verity.ledger` — the same store every other gate writes — so the
ledger doubles as the evidence trail. `exit 2` is the machine-enforceable part:
wire it into a hook, a CI check, or the `:11500` proxy and a quit conclusion
**cannot ship** without receipts.

### Why this helps weak open-weight models too (harness sovereignty)

The gate is deterministic and model-agnostic. A 7B model run behind the proxy
gets the veto enforced **for** it: instead of emitting "I can't," it receives the
structured continue-directive (which sources are still un-searched, the REUSE-
first instruction, the demand for a different second method) and keeps going.
The persistence that makes Fable/Mythos feel "smart" is largely *not quitting* —
and not-quitting is a control surface you can give any model from the outside.
That is the whole VERITY thesis ("harness sovereignty > model") applied to the
one failure mode capability gains don't fix.

## Case study — the lapse this gate was born from (2026-06-28)

A weekly X-bookmark assimilator's headless discovery returned **404**. The agent:

1. Re-ran the **same** library flow (`iSarabjitDhiman/XClientTransaction`) ~7
   times, hit 7 variants of the same wall.
2. Concluded: *"can't fix at this context — let's wait for /compact."*

That was a quit, dressed up as a context-quality limit. When real research finally
happened — `WebSearch` + `WebFetch` across GitHub issues/PRs — the answer was
immediate and complete:

- The daemon had been sending a **fabricated** `x-client-transaction-id`
  (`base64(sha256(time)+urandom)[:88]`) — random garbage X's anti-bot rejects.
- The library being ground on couldn't compute the real one because **X moved its
  JS assets** to `abs.twimg.com/x-web/*.js` (twscrape issue #312); the lib's regex
  matched the old path and returned `None` every time.
- The maintained scraper **twscrape** had already solved all of it
  (`twscrape.xclid.XClIdGen`), using the **same queryId** the daemon already had.

Reusing twscrape's generator → **HTTP 200, 22 entries** in one pass. Five minutes
of the research that should have happened before the first "can't." The block was
never technical. See [x-scraper-resilience.md](x-scraper-resilience.md).

`tests/test_persist.py` encodes this exact scenario permanently (VERITY v2.1
TESTS-FROM-FAILURES): the "wait for compact" conclusion on an empty ledger MUST
block; it passes only once the six-source sweep is logged; and 7 retries of one
path with no find stays blocked.

## Relationship to the other gates

- Sharpens **RULE 6** (search-before-concluding) and **RULE 7** (never-quit) from
  advisory text into an exit-code veto.
- Complements **RULE 8 / R57** (mine PROVIDED resources): R57 covers resources the
  user handed you; R60 covers the case where nobody handed you anything — you must
  go FIND the maintained alternative yourself.
- Is itself a **DETERMINISTIC-VERIFIER-FIRST** control (v2.1): a program/exit-code
  check, not an LLM-judge.

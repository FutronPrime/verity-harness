# Enforcing VERITY on ANY model and ANY setup — the portability model

The public repo will be run by people with infinitely varied setups and models — frontier APIs,
open-weights served locally, tiny low-B models, enterprise LLMs, no two harnesses alike. So the
question that matters: **how do you FORCE the gates when you can't assume the model, the harness, or
the model's goodwill?**

The answer is a **tiered enforcement model** with one shared detection core. Pick the strongest tier
your setup supports; they stack.

> **The core principle: the weaker the model, the more you need EXTERNAL enforcement.**
> A frontier model can be held by injected text (it reads and mostly obeys). A 3B open-weights model
> ignores injected text — so for it you need a layer that inspects the *output* and forces a redo,
> regardless of how smart the model is. VERITY's enforcement degrades gracefully across that whole range.

---

## One detection core, three delivery mechanisms

All tiers call the SAME deterministic checks — `verity/guard.py` (`flag(text)` → re-prompt) and the
gate CLIs (`verity persist / vet / audit / adjudicate`). Improve the core once → every tier gets
smarter. (This is why the ledger→`verity evolve`→playbook loop compounds across all of them.)

### Tier A — the PROXY (universal, mechanical, model-agnostic) ⭐ strongest for arbitrary models

`verity/server.py` runs an OpenAI-compatible endpoint at `:11500`. It sits **between any client and any
model** and inspects **every response**; on a lapse (`guard.flag()` ≠ None — premature negative,
capability-negative, deferral, **R60 context-quit**) it **re-prompts the model with the corrective,
once**, before the answer reaches the user. No opt-out, no model cooperation required.

```bash
python3 -m verity.server                 # starts the :11500 failover+guard proxy
# point ANY OpenAI-compatible client at it:
export OPENAI_BASE_URL=http://127.0.0.1:11500/v1
```

Works for **everything that speaks OpenAI format**:
- **Open-weights served locally** — vLLM, Ollama (`/v1`), llama.cpp server, LM Studio, TGI.
- **Low-B models** (3B/7B) — *this is the tier that matters most for them*: they can't be trusted to
  follow injected rules, but the proxy forces a redo on their output anyway.
- **Enterprise / frontier APIs** — route the provider through the proxy (or run the proxy as a
  middleware shim in front of the gateway).

The proxy is the daemon-style forcing layer **for any model**, which is the direct answer to "what
about other/enterprise/open-source/low-B models."

### Tier B — FRAMEWORK HOOKS (strong, where the harness exposes a turn-end hook)

When the harness lets you run code at turn-end, block the stop on a lapse:

- **Claude Code** — `hooks/stop_guard.py` (already wired; returns `{"decision":"block"}`). 46/46 tested.
- **Codex / other hook-capable CLIs** — same pattern: call `guard.flag(last_message)`; if non-None,
  return the corrective and refuse to end the turn.
- **LangChain / LangGraph / CrewAI / raw agent loops (Python)** — call the core directly in your
  finish/should-continue callback:

```python
from verity import guard
def before_finish(final_text):
    kind = guard.flag(final_text)
    if kind:
        return {"continue": True, "feedback": guard.corrective_for(kind)}  # force another step
    return {"continue": False}
```

Any framework with a "should I stop?" decision point can enforce VERITY in ~5 lines.

### Tier C — the SELF-INJECTING BOOT-PROMPT (universal fallback, zero tooling)

For a bare chatbot with NO proxy and NO hooks (web UI, an enterprise console, a sandboxed model),
fall back to pure prompt — the technique from the Prompt Software model: a self-contained prompt that
**re-parses its own gates before every response** so they can't drift out of context.

Paste [`prompt/VERITY-BOOT.md`](../prompt/VERITY-BOOT.md) as the system/first message. Its
`RecursionController` directive re-states the gate checklist each turn and makes the model run
`persist`/`vet`-style self-checks in-context. Weakest tier (a model *can* rationalize past text — which
is exactly why Tiers A/B exist), but it works on **any instruction-following model with zero setup**,
and it's the only option in locked-down enterprise consoles.

---

## Which tier for which setup

| Your setup | Use | Why |
|---|---|---|
| Local open-weights (vLLM/Ollama/llama.cpp) | **A (proxy)** + C | model-agnostic mechanical forcing; injection as backup |
| Tiny/low-B model | **A (proxy)** | can't trust the model — force the output |
| Enterprise API via your own gateway | **A (proxy shim)** + B | inspect responses in the middleware |
| Claude Code | **B (Stop hook)** + C | turn-end block, already wired |
| Codex / LangChain / CrewAI | **B (callback)** + C | 5-line `guard.flag()` integration |
| Bare chatbot / locked console | **C (boot-prompt)** | the only layer that needs nothing |

**Stack them.** The strongest real-world setup is A+B+C: the proxy forces the output, the hook forces
the turn-end, and the boot-prompt biases the model to comply in the first place — so it rarely trips
the harder layers. That's how you get Mythos-grade rule-following out of an arbitrary model.

## The shared loop that makes it improve everywhere
Every tier writes verdicts to `verity ledger`; `verity evolve` distills them into the injected
playbook (gated so it can only improve). Add or sharpen a gate in `guard.py` / the CLIs once, and
**all three tiers enforce it** on the next run. The discipline lives in the harness, outside the
weights — which is the whole point.

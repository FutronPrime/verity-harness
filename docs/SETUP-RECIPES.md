# Setting up VERITY — copy-paste recipes for every scenario, model, and system design

How an LLM (or its operator) should wire VERITY into a given environment. Pick the recipe that
matches your setup; each is self-contained and ends with a verification step. The principle behind
all of them: **the weaker the model and the more locked-down the harness, the more you lean on
external enforcement (the proxy) over injected text.** See [ENFORCEMENT.md](ENFORCEMENT.md) for why.

> One-time, any setup:
> ```bash
> git clone https://github.com/FutronPrime/verity-harness ~/verity-harness && cd ~/verity-harness
> python3 -m verity doctor          # sanity-check the install + reachable tiers
> ```

---

## Recipe 1 — Claude Code (frontier model, hook + injection) — strongest for this harness

```bash
# 1. Inject the gates every session (writes ~/.verity-harness/verity-context-inject.sh + wires it):
python3 -m verity autostart
# 2. Register the Stop hook so lapses are BLOCKED at turn-end (not just advised). In ~/.claude/settings.json:
#    "hooks": { "Stop": [ { "hooks": [ { "type": "command",
#       "command": "python3 ~/verity-harness/hooks/stop_guard.py" } ] } ] }
```
**Verify:** ask the agent something that tempts a giveup; it should be blocked and forced to investigate.
This is what hardens *this* assistant — the 46/46-tested hook fires on every turn you take.

## Recipe 2 — Local open-weights (Ollama / vLLM / llama.cpp) — proxy is mandatory

A 3B/7B model can't be trusted to obey injected text, so enforce on its **output**:

```bash
# 1. Start the model server (example: Ollama):
ollama serve &  ;  ollama pull qwen2.5:7b-instruct
# 2. Start the VERITY proxy (inspects every response, re-prompts on a lapse, model-agnostic):
python3 -m verity.server &        # listens on :11500
# 3. Point your client/agent at the proxy instead of the model directly:
export OPENAI_BASE_URL=http://127.0.0.1:11500/v1
export OPENAI_API_KEY=local       # any non-empty value for local
```
**Verify:** `curl -s localhost:11500/v1/chat/completions -d '{"model":"...","messages":[{"role":"user","content":"the api errors, should I give up?"}]}'` → the giveup is caught and re-prompted. (Proven live: qwen2.5:3b flipped from "contact support" to "one should indeed investigate.")

## Recipe 3 — Enterprise / hosted API (you can't modify the model) — proxy shim

```bash
# Run the proxy as a middleware in front of the provider; set the upstream in verity.env:
cp verity.env.example verity.env      # set T1_URL / T1_KEY / T1_MODEL to your enterprise endpoint
python3 -m verity.server &
export OPENAI_BASE_URL=http://127.0.0.1:11500/v1
```
The proxy forwards to the enterprise model, inspects the response, and re-prompts on a lapse — the
model vendor never has to change anything. Pair with Recipe 6 if your console also accepts a system prompt.

## Recipe 4 — Agent framework (LangChain / LangGraph / CrewAI / raw loop) — 5-line hook

```python
from verity import guard
def should_continue(state):                      # your finish/continue decision point
    final = state["messages"][-1].content
    kind = guard.flag(final)
    if kind:                                      # premature negative/defer/capability/context-quit
        state["messages"].append({"role": "user", "content": guard.corrective_for(kind)})
        return "continue"                         # force another step instead of finishing
    return "end"
```
**Verify:** `python3 -c "from verity import guard; print(guard.flag('we recommend contacting support'))"` → `defer`.

## Recipe 5 — Bare chatbot / locked-down console (zero tooling) — boot-prompt

No proxy, no hooks (a web UI, an enterprise chat console, a sandboxed model)? Paste the self-injecting
boot-prompt as the system/first message:

```
# copy the contents of prompt/VERITY-BOOT.md into the system prompt field
```
Its RecursionController re-parses the gates every turn. Weakest tier (the model *can* rationalize past
text), but the only one that needs nothing — works on any instruction-following model.

## Recipe 6 — Tiny/low-B model anywhere — stack proxy + boot-prompt

```bash
python3 -m verity.server &                       # Tier A: forces the output (the load-bearing layer)
export OPENAI_BASE_URL=http://127.0.0.1:11500/v1
# Tier C: also prepend prompt/VERITY-BOOT.md as the system message to bias it toward compliance.
```
For weak models the proxy does the real work; the boot-prompt just reduces how often it has to fire.

## Recipe 7 — Maximum reliability (production) — stack A+B+C

```bash
python3 -m verity autostart                       # C: inject gates + playbook every session
python3 -m verity.server &                         # A: proxy forces every response
# B: register the Stop hook (Recipe 1) or framework callback (Recipe 4)
```
Proxy forces the output, hook forces the turn-end, injection biases the model up front — so it rarely
trips the harder layers. This is the Mythos-grade configuration: discipline enforced at three
independent points.

## Recipe 8 — FULLY PRIVATE, all open-weights, zero enterprise — best local performance

For maximum privacy: every model is local open-weights, no data leaves the machine, no API keys. The
`augment` conductor pattern makes this fast AND strong — a small model conducts, a larger LOCAL model
reasons. Nothing touches an enterprise endpoint.

```bash
ollama pull qwen2.5:3b-instruct      # CONDUCTOR (fast, frames + synthesizes)
ollama pull qwen2.5:32b-instruct     # REASONER (the heavy lifting) — pick the biggest your RAM allows
python3 -m verity.server &           # Tier A proxy forces every local response (R60 enforcement)
export OPENAI_BASE_URL=http://127.0.0.1:11500/v1
# fully-private frontier-grade planning (auto-picks largest local model as reasoner, smallest as conductor):
python3 -m verity augment --private "design a comprehensive plan to <goal>"
# research stays private too: free DuckDuckGo/SearXNG floor — no Tavily/enterprise key needed.
```

**Recommended local models by role + hardware** (the reasoner quality is what you'll feel):

| Role | 16GB RAM | 32GB | 64GB+ / GPU |
|---|---|---|---|
| Conductor (fast) | `qwen2.5:3b` / `llama3.2:3b` | `qwen2.5:7b` | `qwen2.5:7b` |
| Reasoner (strong) | `qwen2.5:14b` | `qwen2.5:32b` / `deepseek-r1:32b` | `llama3.3:70b` / `qwen2.5:72b` / `deepseek-r1:70b` |
| Verify/judge (council) | reuse reasoner | reuse reasoner | a 2nd distinct model for blind cross-ranking |

The bigger the local reasoner, the closer the output gets to enterprise frontier — with **full privacy**.
`--private` auto-selects the largest pulled model as reasoner and the smallest as conductor; the proxy
(`:11500`) enforces the gates on every local response so even a weak model can't quit or guess.

> Reasoner offline / no big model pulled? `augment --private` still runs with whatever's local (conductor
> = reasoner if only one model), and `verity council` / `verity adjudicate` likewise route to local tiers.
> No enterprise fallback is ever used in private mode.

---

## Choosing a recipe

| Your design | Recipe | Load-bearing layer |
|---|---|---|
| Claude Code | 1 | Stop hook |
| Local open-weights | 2 | proxy |
| Enterprise/hosted API | 3 | proxy shim |
| LangChain/CrewAI/custom | 4 | framework callback |
| Bare chatbot / locked console | 5 | boot-prompt |
| Tiny/low-B model | 6 | proxy (+ boot-prompt) |
| Production / max reliability | 7 | all three |
| **Full privacy (all open-weights)** | **8** | **local reasoner + proxy** |

## After setup — it improves itself
Whatever recipe you ran, every gate verdict flows to `verity ledger`; `verity evolve` distills it into
the injected playbook (gated to only improve). Sharpen a gate in `guard.py` or a CLI once, and **every
recipe enforces the improvement** on the next run. The 2026-06-28 multi-model run is the template: a
weak model exposed a blind spot → the core got patched → all tiers hardened at once.

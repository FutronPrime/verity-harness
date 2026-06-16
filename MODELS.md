# Knowing which models exist — read the registry, don't guess

Model names move **monthly**. Any LLM's training is stale the day it ships, and web search
rarely surfaces the *exact* slug you need to wire (`kimi-k2.7`, `opus-4.8`, `gemini-3.5`,
`deepseek-v4`, `qwen3.7`, `gemma-4`, `grok-4.3`, `mistral-large-2512` are all post-2025). Guessing
a model id from memory is how you end up routing to a 404 — exactly the kind of confidently-wrong
failure VERITY exists to stop.

So VERITY treats "what is the current/newest model X" as a **lookup, not a recall**: it reads the
authoritative **OpenRouter `/models` registry** (ground truth) instead of trusting priors.

## Use it

```bash
python3 -m verity models deepseek        # all DeepSeek ids, live
python3 -m verity models claude-opus     # → claude-opus-4.8, claude-opus-4.8-fast, …
python3 -m verity models gemini          # the whole Gemini line; pick the newest
python3 -m verity models grok            # → grok-4.3, grok-4.20-multi-agent, …
```

In code / from an agent:

```python
from verity.tools import model_registry
print(model_registry("kimi"))            # authoritative; cached per process
```

The substring is a **provider/family filter**, not the answer — `grok` returns every Grok id and
you still have to identify the newest. That's the point: the harness supplies ground truth, the
model reasons over it.

## The rule (wired into the discipline gates)

> Before you **name, choose, or wire** any model id — for routing config, a "use model Y"
> instruction, or a "the newest X is…" claim — query the registry and verify the id exists there.
> Never ship a model id from memory.

This is injected into every VERITY session (`verity autostart`) alongside Rule 6, so Claude Code,
Codex, and Gemini all inherit it.

## Why this also makes the eval honest

The reproducible A/B (`python3 -m verity eval`) uses "newest model id" assumption-traps. Their
answers are **post-training-cutoff facts** the naive model can't recall — and, critically, that
flaky web snippets don't reliably contain either. Pointing the harness arm at the **registry**
(deterministic ground truth) is what makes the lift both *real* and *reproducible* instead of
hostage to search noise. See [`verity/eval_assumptions.py`](verity/eval_assumptions.py).

## Snapshot — newest per provider (verified against the live registry, 2026-06-15)

These drift; re-run `verity models <provider>` for current truth. Recorded here as the author-time
ground truth behind the eval markers.

| Provider        | Newest id (verified)        | Eval marker  |
|-----------------|-----------------------------|--------------|
| Moonshot (Kimi) | `kimi-k2.7-code`            | `k2.7`       |
| Qwen            | `qwen3.7-max`               | `qwen3.7`    |
| DeepSeek        | `deepseek-v4-pro`           | `deepseek-v4`|
| DeepSeek (exp)  | `deepseek-v3.2-exp`         | `v3.2-exp`   |
| Mistral Large   | `mistral-large-2512`        | `2512`       |
| Anthropic Opus  | `claude-opus-4.8`           | `opus-4.8`   |
| Anthropic (fast)| `claude-opus-4.8-fast`      | `opus-4.8-fast` |
| xAI Grok        | `grok-4.3`                  | `grok-4.3`   |
| Google Gemini   | `gemini-3.5-flash`          | `gemini-3.5` |
| Google Gemma    | `gemma-4-31b-it`            | `gemma-4`    |
| Anthropic Fable | `claude-fable-5`            | `fable-5`    |

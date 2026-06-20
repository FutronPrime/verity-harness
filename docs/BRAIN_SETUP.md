# VERITY Voice — Brain Setup (wire YOUR LLM)

VERITY's voice loop writes its spoken replies + persona TL;DRs with **whatever LLM you already run**. It does
**not** assume you have a specific provider, a paid API, or more than one model. This guide is written so that
an install agent (or you) can pick the right option for **your** machine.

> **If you're the LLM doing the install:** present these options to the user, ask what they already have
> (a cloud API key? a local Ollama/LM Studio? a CLI like `codex`/`claude`/`gemini`?), explain the
> storage/RAM tradeoffs below, then write their choice into `~/.verity-harness/brain.json`.

## How VERITY resolves the brain (first match wins)

1. **Env vars** — `VERITY_VOICE_BRAIN_URL` + `VERITY_VOICE_BRAIN_MODEL` (any OpenAI-compatible
   `/chat/completions` endpoint), or `VERITY_VOICE_BRAIN_CMD` (a CLI that takes the prompt as its last arg
   and prints only the reply).
2. **`~/.verity-harness/brain.json`** — `{"url": "...", "model": "...", "cmd": "..."}`
3. **Local fallback** — local Ollama with the model named in `VERITY_BRAIN_FALLBACK_MODEL` (unset by default).

If nothing is wired, the persona reply degrades gracefully (no separate writer). **Wire one option below.**

## Option A — A cloud LLM you already pay for (best quality)

Point it at your provider's OpenAI-compatible endpoint:

```json
// ~/.verity-harness/brain.json
{ "url": "https://api.openai.com/v1/chat/completions", "model": "gpt-4o-mini", "cmd": "" }
```

Set your key in the environment the listener runs in (`OPENAI_API_KEY`, etc.). Anthropic, Google, Groq,
OpenRouter, Together, etc. all work — use their base URL + a model id. **Cost:** billed per token by your
provider. **Latency:** usually 1–3 s. Best persona fidelity.

## Option B — A CLI you already drive (no extra key)

If you already run an LLM through a CLI, let VERITY call it:

```json
{ "url": "", "model": "", "cmd": "codex exec" }
```

The command receives the full prompt as its last argument and must print **only** the reply. Works with
`codex exec`, `claude -p`, `gemini`, or your own wrapper. **Cost:** whatever that CLI/subscription costs.
**Latency:** depends on the CLI (some spawn a process per call — can be 10–20 s).

## Option C — A local model (free, private, offline)

Install [Ollama](https://ollama.com), `ollama pull <model>`, then:

```json
{ "url": "http://127.0.0.1:11434/v1/chat/completions", "model": "<model>", "cmd": "" }
```

**No per-token cost, nothing leaves your machine.** The trade is disk + RAM, and persona quality scales with
model size. Pick from the table for **your** free RAM and disk:

| Model | Disk | RAM to run | Persona quality | Use it for |
|---|---|---|---|---|
| `gemma3:270m` | ~0.3 GB | ~2 GB | very flat | emergency/background only — too small for persona |
| `qwen2.5:0.5b-instruct` | ~0.4 GB | ~2 GB | flat | emergency floor, background tasks |
| `qwen3:0.6b` | ~0.5 GB | ~2–3 GB | flat-ish | emergency floor, background agent |
| `qwen2.5:3b-instruct` | ~1.9 GB | ~4–6 GB | decent | **good default** for a snappy persona TL;DR |
| `gemma3:4b` | ~3.3 GB | ~6–8 GB | good | nicer persona, still fast on 16 GB Macs |
| `qwen3:8b` / `gemma3:12b` | ~5–8 GB | ~10–16 GB | strong | best local persona, needs the RAM headroom |

**Rule of thumb:** a sub-1B model is too flat to carry a persona — wire it only as an emergency/background
agent, not the main persona writer. For a believable spoken persona on a typical 16 GB laptop, a **3B–4B**
model is the sweet spot (fast + enough nuance). If you have ≥32 GB, an 8B+ reads noticeably better. Don't run
a model whose RAM column exceeds your free memory — it will swap and stutter the audio.

## Speed vs quality

- **Fastest audio:** a small **local** model (≈1 s to write the line) + a local TTS voice. Best for constant
  auto-speak.
- **Best replies:** a strong cloud or large local model — slower, but richer persona and reasoning.

You can split them: use a fast local model for the always-on auto-speak TL;DR (`FUTRON_TTS_MODEL`) and a
bigger/cloud model for the interactive two-way voice loop (`VERITY_VOICE_BRAIN_*`). They're independent.

## Paid TTS budget (optional)

If you wire a paid TTS voice (e.g. ElevenLabs) for the persona, VERITY uses it **sparingly + randomly** under
a hard monthly cap so it can't drain credits. Tune with `VERITY_EL_MONTHLY_CAP` (default 25000) and
`VERITY_EL_PROBABILITY` (default 0.25 = ~1 in 4 lines use the paid voice; the rest use a free local voice).
Usage is tracked in `~/.verity-harness/elevenlabs-usage.json` and resets monthly.

## Voicing YOUR agent's replies (the unified loop)

VERITY is meant to be an I/O shell over the assistant you ALREADY run — your speech in, its reply voiced
back — not a separate chatbot. The reply side reads your real agent's output and speaks a persona summary:

**Claude Code** — install the Stop hook (`hooks/speak-response.sh`). Add to `~/.claude/settings.json`:
```json
"Stop": [ { "matcher": "", "hooks": [
  { "type": "command", "command": "/ABSOLUTE/PATH/TO/verity-harness/hooks/speak-response.sh" } ] } ]
```
Each turn it reads your last assistant message, summarises it in the persona, and speaks it.

**Codex / Gemini / any CLI agent** — no hook needed, just wrap it:
```bash
verity voice pipe codex          # mirrors output live, voices each reply as a persona TL;DR
verity voice pipe gemini chat
```

**Input** — use your app's built-in mic (Claude Code, Codex desktop, etc. have one), any 3rd-party dictation
(e.g. Wispr Flow), or the integrated `verity voice dictate` for setups with no native mic.

**Dependency:** the reply side needs your agent to EXPOSE its output — a Stop hook (Claude Code), a readable
transcript, or a CLI you can wrap with `pipe`. No exposure → nothing to read → no voiced reply. Persona +
voice are selectable (`tts-style`: standard/aisha/lcars/jarvis); paid voices stay capped + sparing.

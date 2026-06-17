# Example workflow — clone a voice into VERITY (agentic, opt-in)

A runnable demonstration of `verity synthesize` doing a **real multi-stage agentic task**: your own LLM
sources a voice reference, processes it, clones it into the local voice engine (Voicebox), wires it as a
readout style, and verifies it plays — end to end, with the harness's verify-before-done discipline.

> **VERITY ships this *workflow*, never any voices.** You supply the reference, and **you are responsible
> for the rights to whatever you clone.** Use your own recording, a CC0 / royalty-free voice, or a voice you
> are licensed to use. Do **not** clone a real person's voice or a copyrighted character to redistribute or
> advertise — that is voice misappropriation / IP infringement, and the liability is yours. The harness
> won't stop you from pointing it at a file; the law still applies. Keep it to voices you own or are licensed for.

## What it shows
A single goal fans out into the kind of multi-step plan a capable agent should run on its own:

1. **Source** — locate a voice reference (a local file you pass, or a permissibly-licensed/CC0 clip).
2. **Fetch & process** — download if needed, trim to a clean ~10–30s mono sample, normalize loudness.
3. **Clone** — register the sample as a custom voice in the local engine (Voicebox / MLX), on-device.
4. **Wire** — attach it to a readout style slot (`standard` / `lcars` / `aisha`) in the TTS config.
5. **Verify** — synthesize a test line and confirm audio actually plays (no "done" on a vibe).

## Run it
```bash
# plan-only (see the steps the agent will take):
python3 -m verity synthesize "clone the voice in ./my-reference.wav into Voicebox and wire it as my 'standard' readout voice"

# execute with an objective completion gate (it must produce playable audio before it can say done):
python3 -m verity synthesize "clone ./my-reference.wav into Voicebox and wire it as the 'standard' readout voice" \
  --build --gate "test -s ~/.verity/voices/standard.wav && play -q ~/.verity/voices/standard.wav"
```

The agent reuses what already exists first (the installed engine, the TTS config) and only builds the
missing glue — then proves it works. That's the point of the demo: **watch your model construct the
capability itself**, disciplined by the harness, rather than you wiring it by hand.

## Why it's here (and not pre-baked voices)
Shipping cloned voices would mean distributing someone's likeness — a legal and ethical non-starter.
Shipping the *workflow* keeps the agentic capability (the impressive part) while leaving the choice of
voice — and the responsibility for it — with you. It's also a clean, filmable proof of what VERITY's
`synthesize` loop can do on a complex, real task.

Related: voice modes/styles in the [README](../README.md#give-it-a-voice-optional-local-first) · `verity synthesize` (capability synthesis).

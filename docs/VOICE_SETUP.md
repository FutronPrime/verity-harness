# VERITY Voice — Setup, Personalities & Reproducibility

VERITY's voice loop is **tiered and per-personality**. With ZERO extra installs it still speaks (OS floor).
Each optional dependency upgrades a personality to a dedicated neural voice. Everything is **config-driven
(env vars + files)** so it reproduces on a fresh machine — nothing is hard-coded to one user's paths.

> Cold-box TL;DR: works immediately via `say`/`espeak`. Add Piper for LCARS/JARVIS, a Kokoro server for
> STANDARD, ElevenLabs (or the local clone server) for AISHA. All optional, all documented below.

---

## Personalities → voices (the routing in `verity/voice.py:say()`)

| Style | Voice | Engine | How it's provided |
|---|---|---|---|
| **standard** | warm white female | Kokoro `af_heart` | a kokoro-onnx server at `KOKORO_URL`; voice via `KOKORO_STANDARD_VOICE` |
| **lcars** | Federation Computer (Majel Barrett) | **Piper** | `~/.verity-harness/voices/lcars.onnx` (+ `.onnx.json`) |
| **jarvis** | British male butler | **Piper** | `~/.verity-harness/voices/jarvis.onnx` (jgkawell/jarvis, en_GB) |
| **aisha** | Gen-Z/AAVE (cloned) | ElevenLabs **or** local clone | `ELEVENLABS_AISHA_VOICE_ID`, else voxsona-server `/tts` |

Routing order in `say()`: **Piper `<style>.onnx`** → **Kokoro `STYLE_KOKORO_VOICE`** → ElevenLabs →
Voicebox → local clone → existing AVANI CLI → **OS floor (`say`/`espeak`)**. First hit wins; everything
degrades gracefully, so a box missing any dependency still speaks.

## Reproduce each tier

### Tier 0 — OS floor (always works, zero deps)
macOS `say` (built in) / Linux `espeak` or `spd-say`. Per-style fallback voices in `STYLE_OS_VOICE`.

### Tier 1 — Piper neural voices (LCARS, JARVIS, any custom)
```bash
pip install piper-tts                  # or set PIPER_BIN to a piper binary
# drop a Piper voice named by its style into the voices dir:
mkdir -p ~/.verity-harness/voices
cp en_US-fedcomp-medium.onnx        ~/.verity-harness/voices/lcars.onnx
cp en_US-fedcomp-medium.onnx.json   ~/.verity-harness/voices/lcars.onnx.json
# JARVIS (jgkawell/jarvis, en_GB medium):
curl -L https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/medium/jarvis-medium.onnx      -o ~/.verity-harness/voices/jarvis.onnx
curl -L https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/medium/jarvis-medium.onnx.json -o ~/.verity-harness/voices/jarvis.onnx.json
```
`_say_piper` auto-routes any `<style>.onnx`. Tip: set `length_scale` ~1.15 in the `.onnx.json` if a voice
talks too fast. Sources: rhasspy/piper-voices on HF (900+ voices) — see [[reference-tts-voicepack-databases]].

### Tier 2 — Kokoro preset voices (STANDARD, and fast presets like bm_daniel)
```bash
pip install kokoro-onnx soundfile
# run a kokoro-onnx HTTP server exposing POST {text, voice} -> wav, then:
export KOKORO_URL="http://127.0.0.1:9102/v1/tts"
export KOKORO_STANDARD_VOICE="af_heart"     # or af_sarah; bm_daniel = British male
```
Add more per-style presets in `STYLE_KOKORO_VOICE`.

### Tier 3 — Cloned voices (AISHA, AVANI, any zero-shot clone)
- **Cloud (premium):** `ELEVENLABS_API_KEY` + per-style `ELEVENLABS_<STYLE>_VOICE_ID` (e.g.
  `ELEVENLABS_AISHA_VOICE_ID`). ~0.6s.
- **Local, free (VoxSona):** run the **voxsona-server** (KokoClone, loads once, stays warm) and the local
  clone path uses it. Drop a 3–15s reference `<style>.wav` (+ `<style>.txt`) into the voices dir.
  - say-overlay (fastest, ~0.7s): `say` → voxsona-server `/convert` → re-voiced.
  - TTS clone (~3s): voxsona-server `/tts` (text → cloned speech).

## Config / env reference
`PIPER_BIN`, `KOKORO_URL`, `KOKORO_STANDARD_VOICE`, `VOICEBOX_URL`, `FUTRON_SHIM_URL` (TL;DR LLM),
`FUTRON_TTS_MODEL`, `ELEVENLABS_API_KEY`, `ELEVENLABS_<STYLE>_VOICE_ID`, `VOXSONA_SERVER`.

### Tuning a cloud voice's pitch & pace (ElevenLabs path)
A cloned voice can render slightly high or fast. Two independent, pitch-correct knobs post-process the
ElevenLabs output via ffmpeg (do NOT use the API `speed` param — it introduces a chipmunk artifact):
- `VERITY_EL_PITCH` — real pitch shift. `<1` = deeper (default `0.95` = 5% lower; `0.92` ≈ 8%).
- `VERITY_EL_SPEED` — pacing only (default `0.9` = 10% slower; `1.0` = off).

Mechanism: `asetrate` shifts pitch, `atempo` compensates so pacing survives the shift — the two stay
decoupled (atempo alone is pitch-preserving and will NOT change pitch). Requires `ffmpeg` on PATH.

## Playback note
`futron-cli-speak` (AVANI's CLI path) double-forks (`os.setsid()`) so playback survives the calling
process exiting — prevents the "cuts off mid-word" bug when a host reaps the speak process.

## Live two-way voice (talk to VERITY)

A full conversation loop: **press ENTER → talk → press ENTER → the active personality replies OUT LOUD in
its own voice → repeat.** Whisper transcribes you locally; the reply is spoken via the realtime voice.
Type `q` (or say "goodbye") to stop.

```bash
verity voice listen          # DEFAULT: press ENTER, talk, press ENTER to send.  ← reliable, mic-only
verity voice listen --ptt    # hold a key (Right-Shift) anywhere — needs Input Monitoring (see caveat)
verity voice listen --vad    # hands-free, voice-activated (can false-trigger; no terminal needed)
```

**The press-ENTER default is the reliable mode** (matches the voice-os `run.sh` pattern): it needs only
the **Microphone** permission and works in any terminal. The mascot opens this for you automatically when
you pick "Push-to-talk · interactive" in setup.

### Voices in conversation (important)
The reply uses the **realtime** path: if `ELEVENLABS_<STYLE>_VOICE_ID` is set it uses **ElevenLabs**
(~0.6s, high quality — recommended, especially for AISHA whose AAVE delivery the local clone can't
match), else it falls back to the **free local clone** (slower, lower quality). Read-outs stay free/local;
only the realtime conversation hits the cloud. (Hybrid = cheapest path to a *responsive* talk-back.)

### Mic device — use the DEFAULT (do NOT name it)
sox records from the **system default input**. Do NOT pass a friendly name like "MacBook Pro Microphone"
— sox rejects it (`no default audio device`) and captures nothing. Just set your real mic as the default
input in System Settings → Sound. (`$VERITY_MIC`/`~/.verity-harness/mic` exist only for a *sox-valid*
device id; leave unset on most setups.)

### Push-to-talk key (--ptt only) + caveat
Configurable via the setup dropdown, `$VERITY_PTT_KEY`, or `~/.verity-harness/ptt-key` (Right-Shift
default; accepts space/z/ctrl_r/etc.). **Caveat:** `--ptt` needs the **Input Monitoring** TCC grant, which
macOS won't reliably grant to a mascot-spawned process — so press-ENTER is the default for a reason.

### First-run permission (one-time)
**Microphone** — click Allow when macOS prompts (the listener probes the mic at startup so it fires
immediately). That's the only grant press-ENTER mode needs.

### Dependencies (reproducible)
`sox` (`brew install sox`), `whisper` (`pip install openai-whisper`), a local LLM (e.g. Ollama +
`qwen2.5:3b-instruct`) at `$FUTRON_SHIM_URL`, and the per-personality voices. For high-quality AISHA,
an ElevenLabs key (`ELEVENLABS_API_KEY` + `ELEVENLABS_AISHA_VOICE_ID`). `pynput` only for `--ptt`.

## Verify
```bash
verity voice status
verity voice say "Setup check — can you hear me?"
verity voice listen --ptt          # then hold Right-Shift and talk
```

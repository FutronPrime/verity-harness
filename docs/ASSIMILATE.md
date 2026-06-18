# `verity assimilate` — the Assimilation Loop

Give VERITY a **video input** and turn it into queryable knowledge — the way a human
watches and learns. Triage-FIRST so a whole-channel backlog never nukes the token budget.

```
Scout → Filter → Assimilate → Synthesize
```

| Stage | What | How |
|---|---|---|
| **Scout** | find new videos | YouTube channel RSS (`feeds/videos.xml?channel_id=…`) — no API key/quota; deduped |
| **Filter** | is it worth watching? | LLM triage vs your learning goals (router), deterministic keyword fallback on outage |
| **Assimilate** | *watch* it | shells [`taoufik123-collab/claude-watch`](https://github.com/taoufik123-collab/claude-watch): yt-dlp + ffmpeg scene-change frames + captions/Whisper → `report.md` |
| **Synthesize** | remember it | captures into VERITY `membank` (bounded persistent memory) |

## Setup

```bash
git clone https://github.com/taoufik123-collab/claude-watch.git ~/repos/claude-watch
# (or set $WATCH_SKILL_DIR to its location)
```

Edit `~/.verity-harness/assimilate.json` — add channels + goals:

```json
{
  "learning_goals": ["AI infrastructure", "DJ technique", "investing & markets"],
  "channels": [
    {"name": "Market Mondays", "handle": "@MarketMondays", "goals": ["investing & markets"]}
  ],
  "max_videos_per_run": 3
}
```

## Usage

```bash
python3 -m verity assimilate targets                 # show config
python3 -m verity assimilate resolve @SomeChannel    # @handle -> UC… channel_id
python3 -m verity assimilate scout <channel_id>      # list recent videos (RSS)
python3 -m verity assimilate filter "<title>" --goals "a,b"   # triage one title
python3 -m verity assimilate watch <url> --intent "what's the hook?"   # assimilate one
python3 -m verity assimilate run                     # scout+filter all → queue
python3 -m verity assimilate run --watch --max 2     # …and assimilate the top 2
python3 -m verity assimilate import-genie            # merge channels from an external taste profile
python3 -m verity assimilate listen <media> --mode performance   # Gemini HEARS it (below)
python3 -m verity assimilate persona <video> --name "Mom"        # Digital Double Dossier (below)
```

## Hearing, not just transcribing (`listen`)

A Whisper text transcript throws away the *performance* — singing, comedic timing, emotion,
accent, laugh. `listen --mode performance` sends the media to the **Gemini CLI**
(`gemini-3.1-pro-preview` by default — it natively hears) and returns a structured analysis of
voice, cadence/timing, emotional delivery, and acting range, with recreation cues. `--mode
transcript` reuses a configured multimodal transcriber for a verbatim pass. Configure via
`gemini_cli` / `gemini_model` / `gemini_transcriber` in the config.

## Digital Double Dossier (`persona`)

`persona <video> --name "X"` builds a faithful, structured capture of a *person* — looks (facial
geometry, skin, hair, distinguishing features, from dense high-res frames), voice + speech (Gemini
performance pass), mannerisms, and personality — into `~/.verity-harness/personas/<slug>/dossier.md`.
The visual sections are filled by an agent reading the frames; the voice/performance section is
prefilled by Gemini. Intended for **legacy / memorial preservation** — capturing someone so they can
be honored and faithfully recreated. Carries an explicit purpose-and-consent header.

## Note on "seeing"

`claude-watch` emits frames + transcript + a skeleton `report.md`. **Full visual
assimilation** happens when an **agent** (Claude Code / a multimodal tier) `Read`s the
frame JPEGs and fills the report. Run fully headless with no vision model in the loop and
you still get a useful **transcript-level** synthesis — `watch` flags this honestly.

Public URLs + local files only (no login/cookies). Best under 10 min; use `--start/--end`
for longer videos. Full spec lives in the FUTRON brain:
`memory/spec-futron-assimilation-system-v1.md`.

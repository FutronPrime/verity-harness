# VERITY desktop mascot 🦅

A tiny desktop pet that idles in the corner of your screen and **reacts to the harness** — a silent
sign that VERITY is installed and watching. Pick the **Truth Hawk** or **"VERI" the Sun**; it never
talks, it just emotes.

## Run it

```bash
cd desktop-mascot
npm install        # Electron (one-time, ~150 MB — this app is separate from VERITY's zero-dep core)
npm start          # the pet appears bottom-right, always-on-top; a teal "V" lives in your tray
```

Or, once the harness is set up: `python3 -m verity mascot` (launches this for you if `npm` is present).

## What it does
- **Idles** with a gentle hover/breathe; the occasional spontaneous flourish so it feels alive.
- **Reacts to VERITY's decision ledger** (`~/.verity-harness/ledger/*.jsonl`) — when a gate fires it
  plays a silent reaction:
  - `VERIFIED` / `FOUND` / `PASS` → ✓ teal success glow + a nod
  - `CORRECTED` / `NEGATIVE` / `DEFER` / `FAIL` → ! magenta alert + a shake
  - `NONE` / a search gate → 🔍 amber think wobble
- **Liveness dot** — glows teal when the `:11500` proxy floor is up ("installed & working").
- **Tray menu** — Hide/Show, switch Truth Hawk ↔ VERI, Quit. Choice persists in `~/.verity-harness/mascot.json`.
- **Drag** it anywhere; it floats above other windows and doesn't steal focus.

## Make your own poses / states
The sprites are `assets/mascot-hawk.png` + `assets/mascot-sun.png`. To add reaction-specific poses
(success/error/think frames) or animate them, **don't hand-edit** — generate from the reference sheet:
`nano_banana_pro` / Higgsfield (image), **Ludo `animateSprite`** (sprite GIFs), or LibreSprite/Pixelorama
to draw frames. (See `memory/feedback_use_all_available_tools_for_graphics.md`.)

Inspired by Claude Code's **Clawd** crab and desktop-pet frameworks like **wil-pe/CATAI** — but the
Truth Hawk doesn't just sit there; it watches your model's work.

# VERITY pets for petdex.dev

Ready-to-submit [petdex](https://github.com/crafter-station/petdex) packs of the VERITY desktop mascots.
Built by `tools/petdex_pack.py` from the transparent WebP states in `desktop-mascot/assets/anim/`.

Each pack = a `sprite.webp` (static **1536×1872 RGBA** grid: 8 cols × 9 rows × 192×208 cells, one row per
state) + `pet.json` (petdex schema). VERITY's mascots are verification-reaction pets, so our states are
**mapped** onto petdex's locomotion rows:

| petdex row | frames | sourced from |
|---|---|---|
| idle | 6 | hawk idle |
| running-right | 8 | building |
| running-left | 8 | building (mirrored) |
| waving | 4 | success |
| jumping | 5 | juggling |
| failed | 8 | error |
| waiting | 6 | thinking |
| running | 6 | building |
| review | 6 | thinking |

## Build / rebuild
```
python3 tools/petdex_pack.py hawk  truth-hawk  "VERITY Truth Hawk"  "<description>"
python3 tools/petdex_pack.py sun   veri-sun    "VERITY — VERI the Sun"
python3 tools/petdex_pack.py avani avani        "VERITY — AVANI"
```

## Publish (manual — outward-facing, needs a petdex account)
Submission publishes to the public petdex gallery and goes through community review, so it's a deliberate
human step:
- **CLI:**  `npx petdex submit ./petdex/truth-hawk/`
- **Web:**  upload `sprite.webp` + `pet.json` at https://petdex.dev/submit
- Community: https://discord.gg/byhubdyBTe (`#wip`, `#showcase`)

codexpets.net has no public submission yet (AI-Pet-Generator waitlist only).

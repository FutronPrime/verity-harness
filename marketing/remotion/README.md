# VERITY promo — Remotion

Animated logo + Truth Hawk mascot + proof B-roll for the YouTube promo (HUD-style motion graphics).

## Render it

```bash
cd marketing/remotion
mkdir -p public
cp ../../assets/logo.png ../../assets/mascot-hawk-icon.png ../../assets/scorecard.png \
   ../../assets/demo-tetris-comparison.png ../../assets/eval-proof-flagship.png public/
npm install
npm run dev          # Remotion Studio (live preview / tweak)
npm run render       # → out/verity-intro.mp4   (the 5s logo+mascot sting)
```

## What's here
- `src/VerityIntro.tsx` — the 5s sting: Truth Hawk springs in + floats + glows, the logo slides up, a
  magenta underline wipes, the tagline fades. Brand palette only; the mascot is silent (never talks).
- Extend with a `VerityPromo` composition that sequences: this intro → the scorecard infographic
  (bars fill) → the Tetris before/after (`demo-tetris-comparison.png` + the `.webm` recordings from
  `verity demo --models`) → CTA. Pair with the AVANI VO from `../promo-video-script.md`.

## Pipeline fit
Remotion = the HUD/graphics + timing layer. Feed it: the eval infographics (PNG), the per-model demo
`.webm` recordings (real proof footage), and the AVANI VO (avani-talk / ElevenLabs). Assemble final cut
in OpenCut / `futron-capcut-cli`. See `memory/reference-content-video-pipeline-resources-2026-06-15.md`.

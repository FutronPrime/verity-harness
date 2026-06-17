#!/usr/bin/env python3
"""Render VERITY's 'caught live' demo promo → MP4 + GIF.

The money shot, honest + reproducible: ask a CURRENT-fact question (the flagship model id),
the bare model answers a STALE id from memory (✗), then the harness reads the live registry and
verifies (✓). Ends on the proof number + repo. Pure pipeline: SVG frames → PNG (rsvg-convert) →
MP4/GIF (ffmpeg). No asciinema/playwright/pip needed.

Usage:  python3 tools/gen_demo_video.py   → assets/demo-verity-live.mp4 + .gif
"""
import os, subprocess, shutil, textwrap, base64

ROOT = os.path.expanduser("~/repos/verity-harness")
ASSETS = os.path.join(ROOT, "assets")
TMP = "/tmp/verity_demo"
MASCOT = os.path.join(ASSETS, "mascot-hawk.png")
# rsvg-convert won't load local <image> hrefs reliably → embed as a base64 data URI
with open(MASCOT, "rb") as _f:
    MASCOT_URI = "data:image/png;base64," + base64.b64encode(_f.read()).decode()

W, H = 1280, 720
BG = "#070a0d"; PANEL = "#0c1116"; EDGE = "#15323a"
TEAL = "#2dd4bf"; MAG = "#d6299e"; AMBER = "#fcee0a"
DIM = "#5e7270"; FG = "#cfe7e2"; WHITE = "#eef6f4"; RED = "#ff5d6c"
MONO = "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace"

def esc(s):  # xml-escape terminal text
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# (kind, text) — kind drives color. Revealed cumulatively, line by line.
SCRIPT = [
    ("cmd",  "$ verity ask  \"what's the current flagship Claude model id?\""),
    ("gap",  ""),
    ("off",  "[ harness OFF ]  bare model answers from memory"),
    ("bad",  "   →  claude-3-5-sonnet            ✗ STALE  · its cutoff is in the past"),
    ("gap",  ""),
    ("on",   "[ harness ON  ]  VERITY intercepts before it can guess"),
    ("step", "   · reads the LIVE model registry …"),
    ("step", "   · verifies across 2 backends …"),
    ("good", "   →  claude-opus-4-8              ✓ CURRENT · looked up, not recalled"),
    ("gap",  ""),
    ("note", "same model.  the only thing that changed is the discipline."),
]
COLOR = {"cmd": WHITE, "off": AMBER, "on": TEAL, "bad": RED, "good": TEAL,
         "step": DIM, "note": FG, "gap": FG}

def frame_svg(n_lines, caret_line, score=None):
    """SVG for a state revealing the first n_lines, caret on caret_line. score=fraction 0..1 of the bar fill."""
    x0, y0 = 70, 150
    lh = 38
    body = []
    for i in range(min(n_lines, len(SCRIPT))):
        kind, text = SCRIPT[i]
        y = y0 + i * lh
        col = COLOR[kind]
        wt = "700" if kind in ("cmd", "off", "on", "note") else "500"
        body.append(f'<text x="{x0}" y="{y}" font-family="{MONO}" font-size="23" '
                    f'font-weight="{wt}" fill="{col}" xml:space="preserve">{esc(text)}</text>')
        if i == caret_line and caret_line is not None:
            # blinking-style block caret at end of the active line (approx char width 13.8)
            cx = x0 + int(len(text) * 13.8) + 6
            body.append(f'<rect x="{cx}" y="{y-22}" width="13" height="28" fill="{TEAL}" opacity="0.85"/>')
    # score bar (the proof) appears at the end
    bar = ""
    if score is not None:
        by = y0 + (len(SCRIPT)) * lh + 26
        full = 560
        fill = int(full * score)
        pct = int(round(score * 100))
        bar = (
            f'<text x="{x0}" y="{by}" font-family="{MONO}" font-size="24" font-weight="700" '
            f'fill="{WHITE}">ACCURACY</text>'
            f'<rect x="{x0+150}" y="{by-22}" width="{full}" height="26" rx="4" fill="#13202200" '
            f'stroke="{EDGE}" stroke-width="1.5"/>'
            f'<rect x="{x0+150}" y="{by-22}" width="{fill}" height="26" rx="4" fill="{TEAL}"/>'
            f'<text x="{x0+150+full+18}" y="{by}" font-family="{MONO}" font-size="26" '
            f'font-weight="800" fill="{TEAL}">{pct}%</text>'
            f'<text x="{x0}" y="{by+40}" font-family="{MONO}" font-size="19" fill="{DIM}">'
            f'20%→88%  ·  every number reproducible: verity eval</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
  width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <rect x="32" y="28" width="{W-64}" height="{H-56}" rx="10" fill="{PANEL}" stroke="{EDGE}" stroke-width="1.5"/>
  <path d="M32 38 L32 28 L{32+120} 28" fill="none" stroke="{TEAL}" stroke-width="2.5"/>
  <path d="M{W-32} {H-38} L{W-32} {H-28} L{W-32-120} {H-28}" fill="none" stroke="{MAG}" stroke-width="2.5"/>
  <text x="70" y="84" font-family="{MONO}" font-size="20" font-weight="700" fill="{DIM}"
    letter-spacing="3">/// VERITY · LIVE</text>
  <text x="70" y="112" font-family="{MONO}" font-size="17" fill="{TEAL}"
    letter-spacing="2">THE OPEN-SOURCE FABLE ALTERNATIVE</text>
  <circle cx="{W-90}" cy="70" r="6" fill="{RED}"/><circle cx="{W-112}" cy="70" r="6" fill="{AMBER}"/>
  <circle cx="{W-134}" cy="70" r="6" fill="{TEAL}"/>
  {''.join(body)}{bar}
</svg>'''

def endcard_svg():
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
  width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <rect x="32" y="28" width="{W-64}" height="{H-56}" rx="10" fill="{PANEL}" stroke="{EDGE}" stroke-width="1.5"/>
  <image xlink:href="{MASCOT_URI}" x="{W//2-150}" y="80" width="300" height="300"/>
  <text x="{W//2}" y="450" text-anchor="middle" font-family="{MONO}" font-size="78" font-weight="800"
    fill="{WHITE}" letter-spacing="6">VERITY</text>
  <text x="{W//2}" y="492" text-anchor="middle" font-family="{MONO}" font-size="22" font-weight="600"
    fill="{TEAL}" letter-spacing="4">THE OPEN-SOURCE FABLE ALTERNATIVE</text>
  <text x="{W//2}" y="558" text-anchor="middle" font-family="{MONO}" font-size="26" font-weight="700"
    fill="{FG}">make ANY model verify instead of guess</text>
  <rect x="{W//2-300}" y="588" width="600" height="50" rx="8" fill="#0c1116" stroke="{TEAL}" stroke-width="1.5"/>
  <text x="{W//2}" y="621" text-anchor="middle" font-family="{MONO}" font-size="24" font-weight="700"
    fill="{TEAL}">github.com/FutronPrime/verity-harness</text>
  <rect x="32" y="{H-30}" width="{W-64}" height="3" fill="{MAG}"/>
</svg>'''

# (state_svg, seconds) — the timeline. Reveal line-by-line with holds; steps linger; end on proof + endcard.
def build_states():
    states = []
    states.append((frame_svg(1, 0), 1.4))                 # the prompt
    states.append((frame_svg(3, 2), 0.9))                 # harness OFF label
    states.append((frame_svg(4, 3), 1.9))                 # the STALE wrong answer (let it land)
    states.append((frame_svg(6, 5), 1.0))                 # harness ON label
    states.append((frame_svg(7, 6), 0.8))                 # registry lookup
    states.append((frame_svg(8, 7), 0.8))                 # verify
    states.append((frame_svg(9, 8), 2.0))                 # the CORRECT answer (let it land)
    states.append((frame_svg(11, 10), 1.4))               # the punchline
    states.append((frame_svg(11, None, score=0.20), 0.5)) # bar starts low
    states.append((frame_svg(11, None, score=0.55), 0.4)) # bar fills
    states.append((frame_svg(11, None, score=0.88), 2.2)) # bar lands at 88
    states.append((endcard_svg(), 3.2))                   # mascot + repo
    return states

def render():
    if not shutil.which("rsvg-convert") or not shutil.which("ffmpeg"):
        raise SystemExit("need rsvg-convert + ffmpeg")
    if os.path.exists(TMP): shutil.rmtree(TMP)
    os.makedirs(TMP)
    states = build_states()
    concat = []
    for i, (svg, secs) in enumerate(states):
        sp = os.path.join(TMP, f"s{i:02d}.svg"); pp = os.path.join(TMP, f"s{i:02d}.png")
        open(sp, "w").write(svg)
        subprocess.run(["rsvg-convert", "-w", str(W*2), "-h", str(H*2), sp, "-o", pp], check=True)
        concat.append(f"file '{pp}'\nduration {secs:.2f}")
    concat.append(f"file '{os.path.join(TMP, f's{len(states)-1:02d}.png')}'")  # hold last
    lp = os.path.join(TMP, "list.txt"); open(lp, "w").write("\n".join(concat))
    mp4 = os.path.join(ASSETS, "demo-verity-live.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lp,
                    "-vf", f"fps=25,scale={W}:{H}:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-movflags", "+faststart", mp4],
                   check=True, capture_output=True)
    # GIF (palette for crispness)
    pal = os.path.join(TMP, "pal.png")
    subprocess.run(["ffmpeg", "-y", "-i", mp4, "-vf", "fps=12,scale=900:-1:flags=lanczos,palettegen", pal],
                   check=True, capture_output=True)
    gif = os.path.join(ASSETS, "demo-verity-live.gif")
    subprocess.run(["ffmpeg", "-y", "-i", mp4, "-i", pal, "-lavfi",
                    "fps=12,scale=900:-1:flags=lanczos[x];[x][1:v]paletteuse", gif],
                   check=True, capture_output=True)
    print(f"OK  {mp4}\n    {gif}")

if __name__ == "__main__":
    render()

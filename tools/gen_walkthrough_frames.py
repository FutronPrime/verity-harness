#!/usr/bin/env python3
"""Render a staged-spotlight walkthrough of architecture.svg → PNG frames.
Each spotlight frame dims everything outside the active stage band + brackets it in teal."""
import os
from playwright.sync_api import sync_playwright

svg = open(os.path.expanduser("~/repos/verity-harness/assets/architecture.svg")).read()
# render at a fixed display size (viewBox 1280x1300 → 820 wide keeps aspect)
svg = svg.replace('viewBox="0 0 1280 1300"', 'width="820" height="833" viewBox="0 0 1280 1300"', 1)
head, tail = svg.rsplit("</svg>", 1)

def overlay(band):
    if band is None:
        return ""
    y0, y1 = band
    return (f'<rect x="0" y="0" width="1280" height="{y0}" fill="#03060a" opacity="0.68"/>'
            f'<rect x="0" y="{y1}" width="1280" height="{1300-y1}" fill="#03060a" opacity="0.68"/>'
            f'<line x1="40" y1="{y0}" x2="1240" y2="{y0}" stroke="#2dd4bf" stroke-width="2.5" opacity="0.9"/>'
            f'<line x1="40" y1="{y1}" x2="1240" y2="{y1}" stroke="#2dd4bf" stroke-width="2.5" opacity="0.9"/>')

# frame plan (band or None=full). duplicates = hold time.
FULL = None
frames = [FULL, FULL,
          (188, 252), (188, 252),
          (284, 446), (284, 446), (284, 446),
          (480, 1150), (480, 1150), (480, 1150), (480, 1150),
          (1100, 1234), (1100, 1234), (1100, 1234),
          FULL, FULL]

os.makedirs("/tmp/vframes", exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 860, "height": 880}, device_scale_factor=2).new_page()
    for i, band in enumerate(frames):
        html = f'<body style="margin:0;background:#03060a">{head}{overlay(band)}</svg>{tail}</body>'
        pg.set_content(html, wait_until="networkidle")
        pg.query_selector("svg").screenshot(path=f"/tmp/vframes/f{i:02d}.png")
    b.close()
print(f"rendered {len(frames)} frames")

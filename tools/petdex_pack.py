#!/usr/bin/env python3
"""Pack a VERITY mascot's transparent WebP states into a petdex.dev pet (sprite.webp + pet.json).

petdex spritesheet spec (verified from crafter-station/petdex src/lib/pet-states.ts + a live published
pet): a STATIC 1536×1872 RGBA grid = 8 cols × 9 rows, each cell 192×208. One ROW per state, frames
left→right starting at col 0; unused cells transparent. Rows/frame-counts are fixed by petdex.

VERITY's mascots are verification-reaction pets (idle/thinking/building/juggling/success/error/...),
not locomotion sprites, so we MAP our states onto petdex's rows (and fake left/right by mirroring).
Output: petdex/<slug>/sprite.webp + pet.json — ready for `npx petdex submit petdex/<slug>/`.
Run:  python3 tools/petdex_pack.py hawk truth-hawk "VERITY Truth Hawk"
"""
import json
import os
import sys
from PIL import Image, ImageSequence

FW, FH, COLS, ROWS = 192, 208, 8, 9
ANIM = os.path.join(os.path.dirname(__file__), "..", "desktop-mascot", "assets", "anim")

# petdex fixed rows (id, row, frames, durationMs) — from pet-states.ts
PETDEX_ROWS = [
    ("idle", 0, 6, 1100), ("running-right", 1, 8, 1060), ("running-left", 2, 8, 1060),
    ("waving", 3, 4, 700), ("jumping", 4, 5, 840), ("failed", 5, 8, 1220),
    ("waiting", 6, 6, 1010), ("running", 7, 6, 820), ("review", 8, 6, 1030),
]

# how each petdex row is sourced from OUR mascot states (state, flip_horizontal)
ROW_SOURCE = {
    "idle": ("idle", False), "running-right": ("building", False), "running-left": ("building", True),
    "waving": ("success", False), "jumping": ("juggling", False), "failed": ("error", False),
    "waiting": ("thinking", False), "running": ("building", False), "review": ("thinking", False),
}


def load_frames(mascot, state):
    """Return RGBA frames of <mascot>-<state>.webp, or None if missing."""
    p = os.path.join(ANIM, f"{mascot}-{state}.webp")
    if not os.path.exists(p):
        return None
    im = Image.open(p)
    return [f.convert("RGBA") for f in ImageSequence.Iterator(im)]


def union_bbox(frames):
    bb = None
    for f in frames:
        b = f.getbbox()
        if b:
            bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
    return bb


def fit_cell(frame, bbox, flip):
    """Crop to the animation's stable bbox, scale to fit 192×208 (margin), center, transparent pad."""
    f = frame.crop(bbox) if bbox else frame
    if flip:
        f = f.transpose(Image.FLIP_LEFT_RIGHT)
    maxw, maxh = FW - 12, FH - 12                       # small margin
    s = min(maxw / f.width, maxh / f.height)
    f = f.resize((max(1, round(f.width * s)), max(1, round(f.height * s))), Image.LANCZOS)
    cell = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    cell.alpha_composite(f, ((FW - f.width) // 2, (FH - f.height) // 2))
    return cell


def sample(frames, n):
    """Evenly sample n frames across the loop."""
    if len(frames) == 1:
        return frames * n
    return [frames[round(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if n > 1 else [frames[0]]


def pack(mascot, slug, display_name, description=""):
    sheet = Image.new("RGBA", (FW * COLS, FH * ROWS), (0, 0, 0, 0))
    states_meta = []
    used = []
    for state_id, row, nframes, dur in PETDEX_ROWS:
        src_state, flip = ROW_SOURCE[state_id]
        frames = load_frames(mascot, src_state) or load_frames(mascot, "idle")
        if not frames:
            raise SystemExit(f"missing source anim for {mascot}-{src_state} (and no idle fallback)")
        bbox = union_bbox(frames)
        picks = sample(frames, nframes)
        for col, fr in enumerate(picks):
            sheet.alpha_composite(fit_cell(fr, bbox, flip), (col * FW, row * FH))
        states_meta.append({"id": state_id, "row": row, "frames": nframes, "durationMs": dur,
                            "source": f"{mascot}-{src_state}" + ("(mirrored)" if flip else "")})
        used.append(f"{state_id}<-{src_state}{'(flip)' if flip else ''}")

    out_dir = os.path.join(os.path.dirname(__file__), "..", "petdex", slug)
    os.makedirs(out_dir, exist_ok=True)
    sheet_path = os.path.join(out_dir, "spritesheet.webp")   # petdex requires this exact name
    sheet.save(sheet_path, format="WEBP", lossless=False, quality=90, method=6)

    pet = {
        "name": display_name, "slug": slug, "kind": "robot" if mascot != "avani" else "human",
        "tags": ["verity", "harness", mascot, "ai-agent", "verification"],
        "vibes": ["focused", "calm", "diligent"],
        "frameWidth": FW, "frameHeight": FH, "cols": COLS, "rows": ROWS,
        "description": description or f"VERITY {display_name} — a silent agent-discipline mascot.",
        "author": "FUTRON / VERITY", "license": "see github.com/FutronPrime/verity-harness",
        "source": "github.com/FutronPrime/verity-harness/desktop-mascot",
        "states": states_meta,
    }
    json.dump(pet, open(os.path.join(out_dir, "pet.json"), "w"), indent=2)

    # verify
    chk = Image.open(sheet_path).convert("RGBA")
    print(f"wrote {sheet_path}  {chk.size}  corner-alpha={chk.getpixel((1,1))[3]} (want 0)")
    print(f"wrote {os.path.join(out_dir,'pet.json')}")
    print("rows:", ", ".join(used))
    assert chk.size == (FW * COLS, FH * ROWS), "sheet dims wrong"
    return out_dir


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: petdex_pack.py <mascot:hawk|sun|avani> <slug> <DisplayName> [description]", file=sys.stderr)
        sys.exit(2)
    pack(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")

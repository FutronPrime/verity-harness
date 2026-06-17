#!/usr/bin/env python3
"""VERITY promo / social card — DNA-styled 16:9 share image (X / Product Hunt / README social preview).
Pure-SVG (zero-dep ethos) + the real mascot embedded; numbers are the verified eval figures. NEVER fabricate.
Render: python3 tools/gen_promo.py && rsvg-convert -w 1200 assets/promo-card.svg -o assets/promo-card.png"""
import base64, io, os

CYAN = "#2dd4bf"; MAG = "#d6299e"; AMB = "#fcee0a"; INK = "#eafffb"; GRY = "#8fb8b1"; DIM = "#5b8a84"
W, H = 1200, 675
ROOT = os.path.expanduser("~/repos/verity-harness")


def _b64_hawk(px=300):
    """Embed the Truth Hawk (resized) so the card is a single self-contained file."""
    try:
        from PIL import Image
        im = Image.open(os.path.join(ROOT, "assets/mascot-hawk.png")).convert("RGBA")
        s = px / max(im.size)
        im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), im.size
    except Exception:
        return None, (0, 0)


def cut(x, y, w, h, c):
    return f"M{x},{y} L{x+w-c},{y} L{x+w},{y+c} L{x+w},{y+h} L{x+c},{y+h} L{x},{y+h-c} Z"


def t(S, x, y, s, size, fill, cls="nar", anchor="start", ls=None):
    e = f' letter-spacing="{ls}"' if ls else ""
    S.append(f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{e}>{s}</text>')


def build():
    S = []
    hawk, (hw, hh) = _b64_hawk(330)
    # V chevron mark
    S.append(f'<path d="M64 70 L104 150 L144 70 L128 70 L104 118 L80 70 Z" fill="{CYAN}"/>')
    t(S, 162, 118, "VERITY", 60, INK, "hv")
    t(S, 165, 150, "THE TRUTH HARNESS", 17, CYAN, "mono", "start", 6)
    t(S, 64, 210, "Make ANY LLM verify instead of assume,", 27, INK, "nar")
    t(S, 64, 244, "persist instead of quit, reuse before reinventing.", 27, INK, "nar")
    t(S, 64, 282, "Open-source · zero-dependency · model-agnostic · a local floor you own.", 16.5, GRY, "nar")
    # proof stats row — same model, harness off→on
    stats = [("ACCURACY", "20→88%"), ("CODING", "60→93%"), ("COORDINATION", "20→100%")]
    bx, bw, gap = 64, 230, 18
    for i, (label, val) in enumerate(stats):
        x = bx + i * (bw + gap)
        S.append(f'<path d="{cut(x, 330, bw, 96, 14)}" fill="#0a0f12" stroke="#16343a" stroke-width="1.2"/>')
        t(S, x + bw / 2, 372, val, 30, CYAN, "hv", "middle")
        t(S, x + bw / 2, 400, label, 12.5, DIM, "mono", "middle", 1)
    t(S, 64, 452, "same model — the only change is the discipline. every number reproducible: verity eval", 14, DIM, "mono")
    # mascot
    if hawk:
        S.append(f'<image href="{hawk}" x="{W-hw-44}" y="{H-hh-92}" width="{hw}" height="{hh}"/>')
    # CTA bar
    S.append(f'<path d="{cut(64, H-72, W-128, 40, 12)}" fill="#0c1417" stroke="{CYAN}" stroke-width="1.3"/>')
    t(S, 84, H-46, "⭐ git clone  →  an agent that earns 'done'", 17, INK, "hv")
    t(S, W-84, H-46, "github.com/FutronPrime/verity-harness", 16, CYAN, "mono", "end")
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'font-family="\'Arial Narrow\',\'Helvetica Neue\',Arial,sans-serif" role="img">'
            '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#070a0d"/><stop offset="1" stop-color="#03070b"/></linearGradient>'
            '<pattern id="scan" width="3" height="3" patternUnits="userSpaceOnUse">'
            '<rect width="3" height="1" fill="#0c1a1d" opacity="0.5"/></pattern>'
            "<style>.mono{font-family:'SF Mono','Menlo',monospace}.hv{font-family:'Arial Black',Arial,sans-serif;font-weight:900}"
            ".nar{font-family:'Arial Narrow',Arial,sans-serif}</style></defs>"
            f'<rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#scan)"/>'
            f'<path d="M16,16 H{W-48} L{W-16},48 V{H-16} H64 L16,{H-64} Z" fill="none" stroke="#1f5c54" stroke-width="2"/>'
            f'<rect x="16" y="{H-8}" width="{W-32}" height="4" fill="{MAG}"/>')
    return head + "\n" + "\n".join(S) + "\n</svg>\n"


if __name__ == "__main__":
    out = os.path.join(ROOT, "assets/promo-card.svg")
    open(out, "w").write(build())
    print(f"wrote {out}")

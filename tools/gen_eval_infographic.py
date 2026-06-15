#!/usr/bin/env python3
"""Generate assets/eval-proof.svg from REAL `verity eval` numbers (AVANI UI DNA style).
Usage: python3 tools/gen_eval_infographic.py '<json>'  where json = {"model":..,"total":N,
"naive":n,"harness":n,"rows":[["trap label", naive_bool, harness_bool],...]}
NEVER fabricate — only run with numbers a real eval produced."""
import json, sys, os
d = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {
    "model": "(model)", "total": 4, "naive": 0, "harness": 0, "rows": []}
CYAN="#2dd4bf"; MAG="#d6299e"; AMB="#fcee0a"; INK="#eafffb"; GRY="#8fb8b1"; DIM="#5b8a84"; FAINT="#586872"
W, H = 1200, 720
total, nv, hv = d["total"], d["naive"], d["harness"]
np_, hp = (nv/total if total else 0), (hv/total if total else 0)
S = []
def cut(x,y,w,h,ctr,cbl): return (f"M{x},{y} L{x+w-ctr},{y} L{x+w},{y+ctr} L{x+w},{y+h} "
                                   f"L{x+cbl},{y+h} L{x},{y+h-cbl} Z")
def panel(x,y,w,h,ctr,cbl,stroke,fill,sw=1.4):
    S.append(f'<path d="{cut(x,y,w,h,ctr,cbl)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    S.append(f'<path d="{cut(x+4,y+4,w-8,h-8,max(ctr-3,4),max(cbl-3,3))}" fill="none" stroke="{stroke}" stroke-width="0.7" opacity="0.38"/>')
def t(x,y,s,size,fill,cls="nar",anchor="start",ls=None):
    e=f' letter-spacing="{ls}"' if ls else ""
    S.append(f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{e}>{s}</text>')

# HUD + title
t(40,56,"/// VERITY.EVAL // SAME MODEL · OPPOSITE RESULT · REPRODUCIBLE",13,CYAN,"mono","start",2)
t(44,110,"FORCE THE SEARCH,",42,INK,"hv"); t(44,156,"FLIP THE ANSWER.",42,CYAN,"hv")
S.append(f'<rect x="46" y="170" width="300" height="3" fill="{MAG}"/>')
t(44,200,f"A/B on assumption-trap questions (correct answer is post-training-cutoff → the model can't "
         f"know it). Models: {d['model']}. Same model + same prompts each — only change: the harness forces a live search first.",16,GRY)

# the two big bars
bx, bw, by = 90, 920, 250
def bar(y, label, frac, n, color, sub):
    t(bx, y-10, label, 18, INK, "hv")
    S.append(f'<rect x="{bx}" y="{y}" width="{bw}" height="46" rx="3" fill="#0c1417" stroke="#1f3a3a"/>')
    fw = int(bw*frac)
    if fw > 0:
        S.append(f'<path d="{cut(bx,y,fw,46,14,9)}" fill="{color}" opacity="0.92"/>')
    t(bx+bw+16, y+30, f"{n}/{total}  ({frac:.0%})", 22, color, "hv")
    t(bx, y+70, sub, 13.5, DIM)
bar(by, "NAIVE — bare model (answers from stale training)", np_, nv, "#3a5660", "what the model says with no discipline")
bar(by+120, "VERITY — search-before-concluding fires first", hp, hv, CYAN, "same model, after the harness forces the lookup")

# the LIFT callout (the receipt)
lift = hv - nv
panel(90, by+250, 470, 96, 24, 14, MAG, "#10090d", 1.6)
t(112, by+292, f"+{lift}", 56, MAG, "hv")
t(200, by+285, "the LIFT — same model, same prompt,", 17, INK)
t(200, by+309, "opposite result. The harness IS the difference.", 17, GRY)

# per-trap grid
t(600, by+278, ">> PER-TRAP (✓ = landed the real, search-only answer)", 13, CYAN, "mono","start",1)
yy = by+300
for i, row in enumerate(d.get("rows", [])[:6]):
    lab, n_ok, h_ok = row[0], row[1], row[2]
    t(600, yy, ("✓" if n_ok else "✗"), 15, (CYAN if n_ok else "#5e6e78"), "hv")
    t(630, yy, ("✓" if h_ok else "✗"), 15, (CYAN if h_ok else MAG), "hv")
    t(660, yy, lab[:62], 13, GRY)
    yy += 26
t(600, yy+6, "naive ↑   harness ↑", 11, FAINT, "mono")

# honest footer
t(44, H-46, "$ python3 -m verity eval    " , 14, "#8fc7bf", "mono")
t(290, H-46, "# reproducible · run it on your own model + suite · receipts in `verity proof`", 13, FAINT, "mono")
S.append(f'<rect x="16" y="{H-20}" width="{W-32}" height="4" fill="{MAG}"/>')

head = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="'Arial Narrow','Helvetica Neue',Arial,sans-serif" role="img" aria-label="VERITY eval A/B result">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#070a0d"/><stop offset="1" stop-color="#03060a"/></linearGradient>
    <pattern id="scan" width="3" height="3" patternUnits="userSpaceOnUse"><rect width="3" height="1" fill="#0c1a1d" opacity="0.5"/></pattern>
    <style>.mono{{font-family:'SF Mono','Menlo',monospace}} .hv{{font-family:'Arial Black',Arial,sans-serif;font-weight:900}} .nar{{font-family:'Arial Narrow',Arial,sans-serif}}</style>
  </defs>
  <rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#scan)"/>
  <path d="M16,16 H{W-50} L{W-16},50 V{H-16} H66 L16,{H-66} Z" fill="none" stroke="#1f5c54" stroke-width="2"/>
'''
svg = head + "\n  " + "\n  ".join(S) + "\n</svg>\n"
out = os.path.expanduser("~/repos/verity-harness/assets/eval-proof.svg")
open(out, "w").write(svg)
print("wrote", out, len(svg), "bytes")

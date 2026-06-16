#!/usr/bin/env python3
"""VERITY PROOF SCORECARD — one DNA-styled infographic summarizing all benchmark axes.
Usage: python3 tools/gen_scorecard.py '<json>'  where json = [{name,proves,naive,harness,lift,detail},...]
NEVER fabricate — pass only numbers real eval runs produced."""
import json, sys, os

CYAN="#2dd4bf"; MAG="#d6299e"; AMB="#fcee0a"; INK="#eafffb"; GRY="#8fb8b1"; DIM="#5b8a84"; FAINT="#586872"
W, H = 1200, 760

def cut(x,y,w,h,ctr,cbl):
    return (f"M{x},{y} L{x+w-ctr},{y} L{x+w},{y+ctr} L{x+w},{y+h} "
            f"L{x+cbl},{y+h} L{x},{y+h-cbl} Z")
def t(S,x,y,s,size,fill,cls="nar",anchor="start",ls=None):
    e=f' letter-spacing="{ls}"' if ls else ""
    S.append(f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{e}>{s}</text>')

def build(axes):
    S=[]
    t(S,40,54,"/// VERITY // PROOF SCORECARD · SAME MODEL ± THE HARNESS · REPRODUCIBLE",13,CYAN,"mono","start",2)
    t(S,44,104,"THE HARNESS DOES THE WORK.",38,INK,"hv")
    S.append(f'<rect x="46" y="116" width="360" height="3" fill="{MAG}"/>')
    t(S,44,146,"Four axes, one rule: the SAME model against itself — only change is the discipline. "
               "Every number is a live run, ledger-logged, reproducible on your own models.",14.5,GRY)
    # column headers
    cy = 186
    t(S,60,cy,">> AXIS / WHAT IT PROVES",12,CYAN,"mono","start",1)
    t(S,690,cy,"NAIVE",12,DIM,"mono","start",1)
    t(S,1010,cy,"+ VERITY",12,CYAN,"mono","start",1)
    rh = 116
    by = cy + 26
    for i,a in enumerate(axes):
        y = by + i*rh
        # panel
        S.append(f'<path d="{cut(56,y,1088,rh-16,20,12)}" fill="#0a0f12" stroke="#16343a" stroke-width="1.2"/>')
        t(S,80,y+34,a["name"],21,INK,"hv")
        t(S,80,y+60,a["proves"],13.5,GRY)
        t(S,80,y+82,a["detail"],11.5,FAINT,"mono")
        # bars
        bx, bw = 640, 300
        fn, fh = a["naive"]/100, a["harness"]/100
        S.append(f'<rect x="{bx}" y="{y+30}" width="{bw}" height="16" rx="2" fill="#0c1417" stroke="#1f3a3a"/>')
        if fn>0: S.append(f'<rect x="{bx}" y="{y+30}" width="{int(bw*fn)}" height="16" rx="2" fill="#3a5660"/>')
        S.append(f'<rect x="{bx}" y="{y+52}" width="{bw}" height="16" rx="2" fill="#0c1417" stroke="#1f3a3a"/>')
        if fh>0: S.append(f'<path d="{cut(bx,y+52,int(bw*fh),16,7,4)}" fill="{CYAN}" opacity="0.92"/>')
        t(S,bx+bw+12,y+43,f"{a['naive']}%",14,DIM,"hv")
        t(S,bx+bw+12,y+65,f"{a['harness']}%",15,CYAN,"hv")
        # lift chip
        t(S,1050,y+54,a["lift"],30,MAG,"hv")
    # footer
    t(S,44,H-40,"$ python3 -m verity eval --flagship · tasks --swarm · swebench · research",13.5,"#8fc7bf","mono")
    t(S,44,H-20,"# four axes, measured the same way: bare model vs the disciplined harness. run them yourself.",12,FAINT,"mono")
    S.append(f'<rect x="16" y="{H-8}" width="{W-32}" height="4" fill="{MAG}"/>')
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'font-family="\'Arial Narrow\',\'Helvetica Neue\',Arial,sans-serif" role="img">'
            '<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#070a0d"/><stop offset="1" stop-color="#03060a"/></linearGradient>'
            '<pattern id="scan" width="3" height="3" patternUnits="userSpaceOnUse">'
            '<rect width="3" height="1" fill="#0c1a1d" opacity="0.5"/></pattern>'
            "<style>.mono{font-family:'SF Mono','Menlo',monospace}"
            ".hv{font-family:'Arial Black',Arial,sans-serif;font-weight:900}"
            ".nar{font-family:'Arial Narrow',Arial,sans-serif}</style></defs>"
            f'<rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#scan)"/>'
            f'<path d="M16,16 H{W-50} L{W-16},50 V{H-16} H66 L16,{H-66} Z" fill="none" stroke="#1f5c54" stroke-width="2"/>')
    return head + "\n" + "\n".join(S) + "\n</svg>\n"

if __name__ == "__main__":
    axes = json.loads(sys.argv[1])
    out = os.path.expanduser("~/repos/verity-harness/assets/scorecard.svg")
    open(out, "w").write(build(axes))
    print("wrote", out)

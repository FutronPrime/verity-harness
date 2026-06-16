#!/usr/bin/env python3
"""Generate the eval infographics (AVANI UI DNA style) from REAL `verity eval` numbers.

Emits:
  assets/eval-proof.svg       — the 5-model A/B (naive vs harness) + aggregate + lift
  assets/eval-iterations.svg  — the honest iteration progression (incl. the v2 dip where the
                                eval caught its OWN invalidity, then the registry-grounded fix)

Usage:  python3 tools/gen_eval_multimodel.py [results.json]
results.json = the list dumped by run_models() ({model,traps,naive_correct,harness_correct,lift}).
NEVER fabricate — only run with numbers a real eval produced. v1/v2 below are MEASURED runs
(provenance in comments), not invented."""
import json, sys, os

CYAN="#2dd4bf"; MAG="#d6299e"; AMB="#fcee0a"; INK="#eafffb"; GRY="#8fb8b1"; DIM="#5b8a84"; FAINT="#586872"
RED="#ff5d6c"

def cut(x,y,w,h,ctr,cbl):
    return (f"M{x},{y} L{x+w-ctr},{y} L{x+w},{y+ctr} L{x+w},{y+h} "
            f"L{x+cbl},{y+h} L{x},{y+h-cbl} Z")
def panel(S,x,y,w,h,ctr,cbl,stroke,fill,sw=1.4):
    S.append(f'<path d="{cut(x,y,w,h,ctr,cbl)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    S.append(f'<path d="{cut(x+4,y+4,w-8,h-8,max(ctr-3,4),max(cbl-3,3))}" fill="none" stroke="{stroke}" stroke-width="0.7" opacity="0.38"/>')
def t(S,x,y,s,size,fill,cls="nar",anchor="start",ls=None):
    e=f' letter-spacing="{ls}"' if ls else ""
    S.append(f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{e}>{s}</text>')

def frame(W,H,body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'font-family="\'Arial Narrow\',\'Helvetica Neue\',Arial,sans-serif" role="img">\n'
            '<defs>'
            '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#070a0d"/><stop offset="1" stop-color="#03060a"/></linearGradient>'
            '<pattern id="scan" width="3" height="3" patternUnits="userSpaceOnUse">'
            '<rect width="3" height="1" fill="#0c1a1d" opacity="0.5"/></pattern>'
            "<style>.mono{font-family:'SF Mono','Menlo',monospace}"
            ".hv{font-family:'Arial Black',Arial,sans-serif;font-weight:900}"
            ".nar{font-family:'Arial Narrow',Arial,sans-serif}</style></defs>"
            f'<rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#scan)"/>'
            f'<path d="M16,16 H{W-50} L{W-16},50 V{H-16} H66 L16,{H-66} Z" fill="none" stroke="#1f5c54" stroke-width="2"/>\n'
            + "\n".join(body) + "\n</svg>\n")

def short(m): return m.split("/")[-1]

# ── 1. FIVE-MODEL PROOF ─────────────────────────────────────────────────────
def proof_svg(data):
    W,H = 1200, 856
    n = sum(r["naive_correct"] for r in data); h = sum(r["harness_correct"] for r in data)
    tot = sum(r["traps"] for r in data)
    S=[]
    t(S,40,54,"/// VERITY.EVAL // SAME MODEL · OPPOSITE RESULT · REPRODUCIBLE",13,CYAN,"mono","start",2)
    t(S,44,104,"FORCE THE LOOKUP,",40,INK,"hv"); t(S,44,148,"FLIP THE ANSWER.",40,CYAN,"hv")
    S.append(f'<rect x="46" y="162" width="300" height="3" fill="{MAG}"/>')
    t(S,44,192,f"A/B on {data[0]['traps']} assumption-traps whose answers are POST training-cutoff "
               f"(the model can't know them). Same model + prompts each —",15.5,GRY)
    t(S,44,213,"the only change: the harness reads the authoritative source first.",15.5,GRY)
    # ── left: per-model rows ──
    bx, bw, by = 60, 540, 268
    rh = 82
    t(S,bx,by-30,"naive ▁  vs  harness ▔   (per model)",12,FAINT,"mono")
    for i,r in enumerate(data):
        y = by + i*rh
        frac_n = r["naive_correct"]/r["traps"]; frac_h = r["harness_correct"]/r["traps"]
        t(S,bx,y-8,short(r["model"]),16,INK,"hv")
        S.append(f'<rect x="{bx}" y="{y}" width="{bw}" height="18" rx="2" fill="#0c1417" stroke="#1f3a3a"/>')
        if frac_n>0: S.append(f'<rect x="{bx}" y="{y}" width="{int(bw*frac_n)}" height="18" rx="2" fill="#3a5660"/>')
        S.append(f'<rect x="{bx}" y="{y+22}" width="{bw}" height="18" rx="2" fill="#0c1417" stroke="#1f3a3a"/>')
        if frac_h>0: S.append(f'<path d="{cut(bx,y+22,int(bw*frac_h),18,8,5)}" fill="{CYAN}" opacity="0.92"/>')
        t(S,bx+bw+12,y+13,f"{r['naive_correct']}/{r['traps']}",13,DIM,"hv")
        t(S,bx+bw+12,y+36,f"{r['harness_correct']}/{r['traps']}",14,CYAN,"hv")
        t(S,bx+bw+66,y+27,f"+{r['lift']}",22,MAG,"hv")
    # ── right: aggregate column (clear of the bars: bars end ~660, column at 770) ──
    rx = 772
    S.append(f'<path d="M{rx-22},{by-26} V{by+5*rh-30}" stroke="#1f3a3a" stroke-width="1"/>')
    t(S,rx,by-2,">> AGGREGATE",13,CYAN,"mono","start",1)
    t(S,rx,by+58,f"{n/tot:.0%}",52,"#3a5660","hv"); t(S,rx,by+84,"naive — from memory",13,DIM)
    t(S,rx,by+162,f"{h/tot:.0%}",72,CYAN,"hv"); t(S,rx,by+190,"with VERITY",14,GRY)
    t(S,rx,by+232,f"across {len(data)} current models, every one +12..+14:",12.5,GRY)
    t(S,rx,by+252,"gpt-4o-mini · gemini-2.5-flash · llama-3.3",11.5,FAINT,"mono")
    t(S,rx,by+269,"· qwen3.5-flash · gemma-4-31b",11.5,FAINT,"mono")
    # ── aggregate panel (full width, below) ──
    ay = by + len(data)*rh + 8
    panel(S,60,ay,1080,96,26,15,MAG,"#10090d",1.6)
    t(S,86,ay+44,f"{n}/{tot}",32,"#3a5660","hv"); t(S,86,ay+78,"naive (answers from memory)",13,DIM)
    t(S,300,ay+44,"→",30,GRY,"hv")
    t(S,350,ay+44,f"{h}/{tot}",32,CYAN,"hv"); t(S,350,ay+78,"harness (reads ground truth)",13,GRY)
    t(S,720,ay+40,f"+{h-n}",52,MAG,"hv"); t(S,830,ay+40,"TOTAL LIFT",15,INK,"hv")
    t(S,830,ay+64,"same models · opposite result · reproducible",12.5,GRY)
    # ── footer ──
    t(S,44,H-32,"$ python3 -m verity eval --models",14,"#8fc7bf","mono")
    t(S,372,H-32,"# deterministic (temp=0, registry ground truth) · run it on your own suite",13,FAINT,"mono")
    S.append(f'<rect x="16" y="{H-20}" width="{W-32}" height="4" fill="{MAG}"/>')
    return frame(W,H,S)

# ── 2. ITERATION PROGRESSION (honest — incl. the dip we caught) ──────────────
# MEASURED runs (not invented):
#  v1 — 4 traps, web-search markers, 3 models (n=4): pasted run 2/12 → 7/12 (gemini-2.0 +0; noisy).
#  v2 — 16 traps, web-search markers, gpt-4o-mini: 1/16 → 2/16. Search couldn't surface exact
#       post-cutoff slugs → harness COLLAPSED. This run EXPOSED the invalid markers (the eval
#       caught its own flaw — the whole point).
#  v3 — 16 traps, AUTHORITATIVE REGISTRY + temp=0, 5 models: aggregate from results.json.
def iterations_svg(data):
    W,H = 1200, 720
    n = sum(r["naive_correct"] for r in data); h = sum(r["harness_correct"] for r in data)
    tot = sum(r["traps"] for r in data)
    ITERS = [
        ("v1","4 traps · web search · n=4","2/12","7/12",17,58,AMB,
         "noisy — gemini-2.0 landed +0, gpt-4o-mini swung 0→4 then 1→3 between runs"),
        ("v2","16 traps · web-search markers","1/16","2/16",6,12,RED,
         "harness COLLAPSED: web search can't surface exact slugs (kimi-k2.7, opus-4.8). the eval"
         " caught its OWN invalid markers — diagnosed, not shipped"),
        ("v3","16 traps · registry · temp=0 · 5 models",f"{n}/{tot}",f"{h}/{tot}",
         round(100*n/tot), round(100*h/tot), CYAN,
         "deterministic; every model +12..+14; lift generalizes uniformly"),
    ]
    S=[]
    t(S,40,54,"/// VERITY.EVAL // HOW WE GOT TO A NUMBER WE TRUST",13,CYAN,"mono","start",2)
    t(S,44,104,"THE ITERATIONS",40,INK,"hv")
    S.append(f'<rect x="46" y="118" width="270" height="3" fill="{MAG}"/>')
    t(S,44,150,"Honest progression — including the run where the harness caught its OWN broken eval. "
               "That dip is a feature: a confidently-wrong 92% would have been worse than no number.",15.5,GRY)
    cx,cw,gap = 60, 360, 20
    cy = 200; ch = 410
    for i,(tag,setup,nv,hv,np_,hp,col,note) in enumerate(ITERS):
        x = cx + i*(cw+gap)
        panel(S,x,cy,cw,ch,26,16,col,"#0a0f12",1.5)
        t(S,x+24,cy+44,tag.upper(),34,col,"hv")
        t(S,x+24,cy+74,setup,12.5,GRY,"mono")
        # bars
        byy=cy+120; bw=cw-110
        t(S,x+24,byy-6,"naive",12,DIM)
        S.append(f'<rect x="{x+24}" y="{byy}" width="{bw}" height="26" rx="2" fill="#0c1417" stroke="#1f3a3a"/>')
        if np_>0: S.append(f'<rect x="{x+24}" y="{byy}" width="{int(bw*np_/100)}" height="26" rx="2" fill="#3a5660"/>')
        t(S,x+24+bw+12,byy+20,f"{np_}%",16,DIM,"hv")
        t(S,x+24,byy+52,"harness",12,col)
        S.append(f'<rect x="{x+24}" y="{byy+58}" width="{bw}" height="26" rx="2" fill="#0c1417" stroke="#1f3a3a"/>')
        if hp>0: S.append(f'<path d="{cut(x+24,byy+58,int(bw*hp/100),26,10,6)}" fill="{col}" opacity="0.92"/>')
        t(S,x+24+bw+12,byy+78,f"{hp}%",16,col,"hv")
        # score chips
        t(S,x+24,byy+128,f"{nv}",20,"#3a5660","hv"); t(S,x+70,byy+128,"→",18,GRY,"hv")
        t(S,x+96,byy+128,f"{hv}",20,col,"hv")
        # note
        words=note.split(); lines=[]; cur=""
        for w in words:
            if len(cur)+len(w)>34: lines.append(cur); cur=w
            else: cur=(cur+" "+w).strip()
        if cur: lines.append(cur)
        for j,ln in enumerate(lines[:5]):
            t(S,x+24,byy+165+j*18,ln,12.5,GRY)
        # arrow between
        if i<2:
            ax=x+cw+gap/2
            S.append(f'<path d="M{x+cw+3},{cy+ch/2} L{x+cw+gap-3},{cy+ch/2}" stroke="{FAINT}" stroke-width="2"/>')
            S.append(f'<path d="M{x+cw+gap-9},{cy+ch/2-5} L{x+cw+gap-3},{cy+ch/2} L{x+cw+gap-9},{cy+ch/2+5}" fill="{FAINT}"/>')
    t(S,44,H-44,"# v2 wasn't a failure to hide — it's the receipt that the method is honest. v3 is the number.",13,FAINT,"mono")
    S.append(f'<rect x="16" y="{H-20}" width="{W-32}" height="4" fill="{MAG}"/>')
    return frame(W,H,S)

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/verity_eval_results.json"
    data = json.load(open(src))
    out = os.path.expanduser("~/repos/verity-harness/assets")
    open(os.path.join(out,"eval-proof.svg"),"w").write(proof_svg(data))
    open(os.path.join(out,"eval-iterations.svg"),"w").write(iterations_svg(data))
    print("wrote assets/eval-proof.svg + assets/eval-iterations.svg from", len(data), "models")

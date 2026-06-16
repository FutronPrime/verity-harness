#!/usr/bin/env python3
"""VERITY CAPABILITY × MODEL SWEEP — one DNA-styled SVG matrix from REAL sweep data (/tmp/verity-sweep.json
or a path arg). Rows = models, cols = capability axes; each cell = naive→harness with a lift-intensity bar.
NEVER fabricate — renders only what the sweep actually produced; untested cells render as a dim dash."""
import json, sys, os

CYAN="#2dd4bf"; MAG="#d6299e"; AMB="#fcee0a"; INK="#eafffb"; GRY="#8fb8b1"; DIM="#5b8a84"; FAINT="#586872"
AXES=[("A","ACCURACY"),("C","CODING"),("M","MEMORY"),("R","RESEARCH"),("X","COORD.")]

def cut(x,y,w,h,ctr,cbl):
    return (f"M{x},{y} L{x+w-ctr},{y} L{x+w},{y+ctr} L{x+w},{y+h} L{x+cbl},{y+h} L{x},{y+h-cbl} Z")
def t(S,x,y,s,size,fill,cls="nar",anchor="start",ls=None):
    e=f' letter-spacing="{ls}"' if ls else ""
    S.append(f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{e}>{s}</text>')

def build(data):
    models=list(data.get("models",{}).items())
    W=1240; top=210; rh=70; H=top+rh*len(models)+96
    S=[]
    t(S,40,52,"/// VERITY // CAPABILITY × MODEL SWEEP · SAME MODEL ± THE HARNESS · LIVE A/B",12.5,CYAN,"mono","start",2)
    t(S,44,100,"ONE RULE, EVERY MODEL, EVERY CAPABILITY.",34,INK,"hv")
    S.append(f'<rect x="46" y="112" width="430" height="3" fill="{MAG}"/>')
    t(S,44,140,"Each cell: naive (harness OFF) → harness ON, on the same model. Green = the discipline lifted it. "
               "Numbers are live, ledger-logged runs — reproducible on your own models.",13.5,GRY)
    # column headers
    x0=300; cw=(W-x0-40)//len(AXES)
    t(S,56,top-12,">> MODEL",12,CYAN,"mono","start",1)
    for i,(_,label) in enumerate(AXES):
        t(S,x0+i*cw+cw//2,top-12,label,11.5,CYAN,"mono","middle",1)
    agg_naive=agg_harn=0
    for r,(mname,axes) in enumerate(models):
        y=top+r*rh
        S.append(f'<path d="{cut(48,y,W-88,rh-10,16,10)}" fill="#0a0f12" stroke="#16343a" stroke-width="1.1"/>')
        t(S,64,y+34,mname,15,INK,"hv" if r<4 else "nar")
        for i,(ax,_) in enumerate(AXES):
            cx=x0+i*cw; c=axes.get(ax)
            if not c or "error" in c:
                t(S,cx+cw//2,y+34,"·" if not c else "err",13,FAINT,"mono","middle")
                continue
            n,h,tot,lift=c.get("naive",0),c.get("harness",0),c.get("total",0),c.get("lift",0)
            agg_naive+=n; agg_harn+=h
            col=CYAN if lift>0 else (AMB if lift==0 else MAG)
            t(S,cx+cw//2,y+27,f"{n}→{h}",16,col,"hv","middle")
            t(S,cx+cw//2,y+43,f"of {tot}   +{lift}" if lift>=0 else f"of {tot}   {lift}",10.5,GRY,"mono","middle")
            # lift bar
            bw=cw-30; fr=(h/tot) if tot else 0
            S.append(f'<rect x="{cx+15}" y="{y+rh-15}" width="{bw}" height="5" rx="1.5" fill="#0c1417" stroke="#1f3a3a"/>')
            if fr>0: S.append(f'<rect x="{cx+15}" y="{y+rh-15}" width="{int(bw*fr)}" height="5" rx="1.5" fill="{col}" opacity="0.9"/>')
    fy=top+rh*len(models)+34
    lift=agg_harn-agg_naive
    t(S,64,fy,f"AGGREGATE  naive {agg_naive} → harness {agg_harn}   (+{lift} across all graded cells)",15,CYAN,"hv")
    t(S,64,fy+24,"Gradeable A/B axes shown. Web-browsing/scraping/trending ≈ RESEARCH; goals/automation ≈ COORD.; "
                 "app/site-build ≈ CODING. (Design/content-gen are separate FUTRON subsystems, not VERITY.)",11.5,FAINT)
    head=(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
          f'font-family="\'Arial Narrow\',\'Helvetica Neue\',Arial,sans-serif" role="img">'
          '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
          '<stop offset="0" stop-color="#070a0d"/><stop offset="1" stop-color="#03060a"/></linearGradient>'
          '<pattern id="scan" width="3" height="3" patternUnits="userSpaceOnUse">'
          '<rect width="3" height="1" fill="#0c1a1d" opacity="0.5"/></pattern>'
          "<style>.mono{font-family:'SF Mono','Menlo',monospace}.hv{font-family:'Arial Black',Arial,sans-serif;font-weight:900}"
          ".nar{font-family:'Arial Narrow',Arial,sans-serif}</style></defs>"
          f'<rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#scan)"/>'
          f'<path d="M16,16 H{W-50} L{W-16},50 V{H-16} H66 L16,{H-66} Z" fill="none" stroke="#1f5c54" stroke-width="2"/>'
          f'<rect x="16" y="{H-8}" width="{W-32}" height="4" fill="{MAG}"/>')
    return head+"\n"+"\n".join(S)+"\n</svg>\n"

if __name__=="__main__":
    src=sys.argv[1] if len(sys.argv)>1 else "/tmp/verity-sweep.json"
    data=json.load(open(src))
    out=os.path.expanduser("~/repos/verity-harness/assets/capability-matrix.svg")
    open(out,"w").write(build(data))
    print(f"wrote {out}")

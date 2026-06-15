#!/usr/bin/env python3
"""Regenerate assets/gates.svg in the AVANI UI DNA system (augmented-ui tr-clip/bl-clip dual
corner cuts + low-opacity inlay double-border), unified with architecture.svg.
Category color: teal=enforced gates, muted=dead 'prompt hopes', magenta accent strip."""
import os
CYAN="#2dd4bf"; MAG="#d6299e"; INK="#eafffb"
S=[]
def cut(x,y,w,h,ctr,cbl):
    return (f"M{x},{y} L{x+w-ctr},{y} L{x+w},{y+ctr} L{x+w},{y+h} "
            f"L{x+cbl},{y+h} L{x},{y+h-cbl} Z")
def panel(x,y,w,h,ctr,cbl,stroke,fill,sw=1.2,inlay=True,inlay_op=0.38):
    S.append(f'<path d="{cut(x,y,w,h,ctr,cbl)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    if inlay:
        S.append(f'<path d="{cut(x+4,y+4,w-8,h-8,max(ctr-3,4),max(cbl-3,3))}" fill="none" '
                 f'stroke="{stroke}" stroke-width="0.7" opacity="{inlay_op}"/>')
def txt(x,y,s,size,fill,cls="nar",anchor="start",ls=None):
    e=f' letter-spacing="{ls}"' if ls else ""
    S.append(f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{e}>{s}</text>')

# dead "prompt hopes" cards (muted, DNA dual-cut)
doctrine=[("\"verify before you act\"","may or may not. no backstop."),
          ("\"don't give up\"","quits at the first wall anyway."),
          ("\"reuse existing tools\"","reinvents from scratch when it forgets.")]
for i,(a,b) in enumerate(doctrine):
    y=304+i*82
    panel(44,y,472,52,18,11,"#26323b","#0c1217",1.0,inlay=True,inlay_op=0.5)
    txt(62,y+28,a,13,"#76858f","mono"); txt(62,y+50,b,17,"#5e6e78")

# enforced VERITY gates (teal, DNA dual-cut + inlay + accent bar)
gates=[("VERIFY_GATE","every action adversarially checked — did it REALLY work?"),
       ("CALIBRATION_GATE",'challenges every "done" → tags VERIFIED vs GUESS'),
       ("PERSISTENCE_GATE","refuses to abort — forces a different approach, N times"),
       ("RESEARCH_ON_STUCK","auto-searches GitHub/Reddit/HN/SO on the real error"),
       ("REUSE_FIRST_DISCOVERY","own tools → external → build; auto-fires on build tasks"),
       ("OBJECTIVE_GATE",'"done" rejected until a real test/build exits 0')]
for i,(a,b) in enumerate(gates):
    y=300+i*46
    crit = a=="OBJECTIVE_GATE"
    col = MAG if crit else "#1f6b60"
    panel(640,y,520,42,14,9,col,"#0a1d1b",1.1,inlay=True,inlay_op=0.4)
    S.append(f'<rect x="644" y="{y+3}" width="5" height="30" fill="url(#tg)"/>')
    txt(666,y+20,a,13,(MAG if crit else "#5eead4"),"mono")
    txt(666,y+36,b,14.5,"#86bfb6")

head=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 766" font-family="'Arial Narrow','Helvetica Neue',Arial,sans-serif" role="img" aria-labelledby="t d">
  <title id="t">VERITY enforcement gates</title>
  <desc id="d">Left: prompt 'hopes' that have no backstop. Right: VERITY's deterministic gates (verify, calibration, persistence, research-on-stuck, reuse-first, objective) that fire on code conditions. AVANI UI DNA corner-cut panels.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#070a0d"/><stop offset="1" stop-color="#03060a"/></linearGradient>
    <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2dd4bf"/><stop offset="1" stop-color="#0c6e62"/></linearGradient>
    <pattern id="scan" width="3" height="3" patternUnits="userSpaceOnUse"><rect width="3" height="1" fill="#0c1a1d" opacity="0.5"/></pattern>
    <style>.mono{{font-family:'SF Mono','Menlo','Consolas',monospace}} .hv{{font-family:'Arial Black','Helvetica Neue',Arial,sans-serif;font-weight:900}} .nar{{font-family:'Arial Narrow',Arial,sans-serif}}</style>
  </defs>
  <rect width="1200" height="766" fill="url(#bg)"/>
  <rect width="1200" height="766" fill="url(#scan)"/>
  <path d="M16,16 H1150 L1184,50 V750 H66 L16,700 Z" fill="none" stroke="#1f5c54" stroke-width="2"/>
  <path d="M16,70 V16 H70 M1184,696 V750 H1130" fill="none" stroke="#2dd4bf" stroke-width="3"/>
  <rect x="16" y="746" width="1168" height="4" fill="#d6299e"/>
  <text x="40" y="58" class="mono" font-size="14" letter-spacing="3" fill="#2dd4bf">/// VERITY.ENFORCEMENT.MODULE</text>
  <text x="1160" y="58" text-anchor="end" class="mono" font-size="14" letter-spacing="2" fill="#5b8a84">[ STATUS: ACTIVE ]</text>
  <text x="44" y="132" class="hv" font-size="56" letter-spacing="1" fill="#eafffb">A PROMPT <tspan fill="#7fb3ab">REQUESTS.</tspan></text>
  <text x="44" y="190" class="hv" font-size="56" letter-spacing="1" fill="#2dd4bf">VERITY ENFORCES.</text>
  <rect x="46" y="204" width="430" height="3" fill="#d6299e"/>
  <text x="44" y="234" class="nar" font-size="20" fill="#8fb8b1">LLMs are probabilistic — the harness, not the model, decides when discipline fires.</text>
  <text x="44" y="290" class="mono" font-size="13" letter-spacing="3" fill="#586872">&gt;&gt; PROMPT DOCTRINE // HOPES</text>
  <text x="640" y="290" class="mono" font-size="13" letter-spacing="3" fill="#2dd4bf">&gt;&gt; VERITY GATES // FIRE ON CODE CONDITIONS</text>
'''
foot='''  <text x="44" y="640" class="hv" font-size="24" fill="#cdeee8">THE MODEL REASONS INSIDE RAILS IT CANNOT FALL OFF OF.</text>
  <g fill="#2dd4bf" opacity="0.8">
    <rect x="44" y="658" width="2" height="22"/><rect x="49" y="658" width="5" height="22"/><rect x="57" y="658" width="2" height="22"/><rect x="62" y="658" width="3" height="22"/><rect x="68" y="658" width="6" height="22"/><rect x="77" y="658" width="2" height="22"/><rect x="82" y="658" width="4" height="22"/><rect x="89" y="658" width="2" height="22"/>
  </g>
  <text x="100" y="674" class="mono" font-size="12" letter-spacing="2" fill="#3f7d76">PROBABILISTIC CORE · DETERMINISTIC RAILS</text>
  <g transform="translate(1090,660)">
    <path d="M0,-10 L9,10 L18,-10" fill="none" stroke="#b9c8c4" stroke-width="3" stroke-linejoin="round"/>
    <path d="M4,-1 L8,4 L15,-8" fill="none" stroke="#2dd4bf" stroke-width="2.6" stroke-linecap="round"/>
    <text x="28" y="6" class="hv" font-size="16" letter-spacing="3" fill="#eafffb">VERITY</text>
  </g>
</svg>
'''
svg=head+"\n  "+"\n  ".join(S)+"\n"+foot
out=os.path.expanduser("~/repos/verity-harness/assets/gates.svg")
open(out,"w").write(svg)
print("wrote",out,len(svg),"bytes")

#!/usr/bin/env python3
"""Generate VERITY architecture.svg using AVANI UI DNA geometry:
augmented-ui diagonal corner cuts (tr-clip bl-clip signature) + low-opacity inlay border.
Palette on VERITY brand (teal=cyan/data analog, magenta=danger analog, amber=focus accent)."""

CYAN = "#2dd4bf"; MAG = "#d6299e"; AMB = "#fcee0a"
INK = "#eafffb"; GRY = "#8fb8b1"; DIM = "#5b8a84"; FAINT = "#586872"
FILL = "#0a1417"; FILL2 = "#0c191c"; FILLD = "#10090d"; PANELBG = "#081012"
S = []

def cut(x, y, w, h, ctr, cbl):
    return (f"M{x},{y} L{x+w-ctr},{y} L{x+w},{y+ctr} L{x+w},{y+h} "
            f"L{x+cbl},{y+h} L{x},{y+h-cbl} Z")

def panel(x, y, w, h, ctr=24, cbl=14, stroke=CYAN, sw=1.5, fill=FILL, inlay=True):
    S.append(f'<path d="{cut(x,y,w,h,ctr,cbl)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    if inlay:
        S.append(f'<path d="{cut(x+4,y+4,w-8,h-8,max(ctr-3,4),max(cbl-3,3))}" fill="none" '
                 f'stroke="{stroke}" stroke-width="0.7" opacity="0.38"/>')

def t(x, y, s, size=14, fill=INK, cls="nar", anchor="start", ls=None):
    extra = f' letter-spacing="{ls}"' if ls else ""
    S.append(f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}" '
             f'text-anchor="{anchor}"{extra}>{s}</text>')

def arrow(x1, y1, x2, y2, color=CYAN, sw=2):
    m = "arm" if color == MAG else "ar"
    S.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
             f'stroke-width="{sw}" marker-end="url(#{m})"/>')

def pill(cx, y, w, h, label, size=16, stroke=CYAN):
    S.append(f'<rect x="{cx-w/2}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="{FILL}" '
             f'stroke="{stroke}" stroke-width="2"/>')
    t(cx, y+h/2+6, label, size, INK, "hv", "middle")

W, H = 1280, 1300

# ---------- HUD frame ----------
t(42, 56, "/// VERITY.ARCHITECTURE", 13, CYAN, "mono", "start", 3)
t(1238, 56, "[ FABLE TELLS THE TALE · VERITY VERIFIES IT ]", 13, DIM, "mono", "end", 2)
t(44, 118, 'THE TRUTH HARNESS <tspan fill="%s">· FLOW</tspan>' % CYAN, 46, INK, "hv")
S.append(f'<rect x="46" y="132" width="360" height="3" fill="{MAG}"/>')
t(44, 166, "Don't let a vendor hold your AI hostage — or let a model proceed on a confident guess. "
           "Every gate fires on a CODE condition, not the model's goodwill.", 19, GRY)

# ---------- INPUT ----------
pill(640, 196, 280, 46, "GOAL / PROMPT", 20)
arrow(640, 242, 640, 282)

# ---------- (1) ROUTER ----------
panel(60, 288, 1160, 150, 38, 22, CYAN)
t(84, 318, "① SOVEREIGN ROUTER", 14, CYAN, "mono", "start", 2)
t(1196, 318, "capability-preserving failover · never a single point of failure", 15, DIM, "nar", "end")
t(84, 350, "TIER 1 — peer chain (each self-retries, then → next peer)", 14, "#7fb3ab")
chain = [("Opus 4.8", "Anthropic"), ("GPT-5.5", "OpenAI"), ("Gemini 3.1", "Google")]
cx = 84
for i, (a, b) in enumerate(chain):
    panel(cx, 360, 150, 56, 14, 9, CYAN, 1.2, FILL2)
    t(cx+75, 384, a, 16, INK, "hv", "middle"); t(cx+75, 404, b, 12, DIM, "nar", "middle")
    if i < 2:
        arrow(cx+150, 388, cx+174, 388)
    cx += 178
t(cx+10, 392, "…peers", 13, FAINT)
arrow(cx+72, 388, cx+108, 388, MAG)
t(cx+90, 378, "all down", 11, MAG, "nar", "middle")
panel(cx+112, 354, 1206-(cx+112), 68, 20, 12, CYAN, 2, FILL)
t(cx+132, 382, "TIER 0 — LOCAL FLOOR (Ollama, on YOUR disk)", 17, CYAN, "hv")
t(cx+132, 406, "un-revocable open weights · last resort, never first · sovereignty", 13.5, GRY)
arrow(640, 438, 640, 478)

# ---------- (2) DISCIPLINE LAYER ----------
panel(60, 484, 1160, 660, 42, 24, CYAN)
t(84, 514, "② DISCIPLINE LAYER", 14, CYAN, "mono", "start", 2)
t(1196, 514, "deterministic enforcers — the harness decides when discipline fires, not the model",
  15, DIM, "nar", "end")

panel(84, 532, 540, 70, 20, 12, CYAN, 1.3)
t(104, 558, "\U0001f9e0 RULE 0 · METACOGNITIVE PRE-FLIGHT", 15, INK, "hv")
t(104, 582, "live-search the CURRENT best approach → inject it (may supersede stale training)", 13.5, GRY)
panel(640, 532, 554, 70, 20, 12, CYAN, 1.3)
t(660, 558, "♻ REUSE-FIRST DISCOVERY", 15, INK, "hv")
t(660, 582, "your own tools → existing OSS → only then build (web-reach: x-read, agent-reach)", 13.5, GRY)
arrow(354, 602, 354, 634)

# verified loop (focus panel = amber accent border)
panel(84, 640, 760, 300, 40, 24, AMB, 1.6, FILL)
t(104, 668, "VERIFIED LOOP  ·  think → act → VERIFY → recover", 13, AMB, "mono", "start", 1)
panel(104, 684, 200, 58, 14, 9, CYAN, 1.1, FILL2)
t(204, 709, "THINK", 15, INK, "hv", "middle"); t(204, 729, "plan one minimal step", 12, DIM, "nar", "middle")
arrow(304, 713, 328, 713)
panel(332, 684, 200, 58, 14, 9, CYAN, 1.1, FILL2)
t(432, 709, "ACT", 15, INK, "hv", "middle"); t(432, 729, "real shell command", 12, DIM, "nar", "middle")
arrow(532, 713, 556, 713)
panel(560, 684, 260, 58, 16, 10, CYAN, 1.6, FILL2)
t(690, 709, "VERIFY", 15, CYAN, "hv", "middle")
t(690, 729, "adversarial · separate cheap tier · maker≠checker", 12, GRY, "nar", "middle")
t(724, 768, "✓ OK → next step ↺", 12, CYAN, "mono", "middle")
panel(104, 784, 716, 58, 16, 10, MAG, 1.5, FILLD)
t(124, 809, "✗ FAIL →", 14, MAG, "hv")
t(214, 809, "QC self-heal (drop CAPTCHA/empty/error)", 14, INK)
t(124, 829, "PERSISTENCE: auto-research the obstacle (GitHub/Reddit/HN/SO) → force a DIFFERENT approach", 13.5, GRY)
S.append(f'<path d="M104,813 H92 V713 H100" fill="none" stroke="{MAG}" stroke-width="2" marker-end="url(#arm)"/>')
t(104, 878, "No head-bumping: refuses to quit on one failed approach; never reasons over garbage output.", 13, FAINT)
t(104, 912, "PLAN-ONLY by default · allowlisted / full shell opt-in · destructive ops blocked.", 13, FAINT)

# done funnel
t(884, 668, '"DONE" PASSES 3 GATES', 13, CYAN, "mono", "start", 1)
panel(884, 682, 310, 44, 14, 9, CYAN, 1.2, FILL2)
t(900, 709, '① EVIDENCE — no "done" w/o proof', 14, INK)
arrow(1039, 726, 1039, 742, CYAN, 1.5)
panel(884, 746, 310, 44, 14, 9, CYAN, 1.2, FILL2)
t(900, 773, "② CALIBRATION — kill overconfidence", 14, INK)
arrow(1039, 790, 1039, 806, CYAN, 1.5)
panel(884, 810, 310, 44, 14, 9, MAG, 1.4, FILL2)
t(900, 837, "③ OBJECTIVE GATE — test exits 0", 14, INK)
arrow(1039, 854, 1039, 884, MAG)
panel(884, 888, 310, 44, 16, 10, CYAN, 2, FILL)
t(1039, 916, '✓ ACCEPT "DONE"', 15, CYAN, "hv", "middle")

# hard stops + memory
panel(84, 958, 556, 64, 18, 11, CYAN, 1.3)
t(104, 982, "⏱ HARD STOPS", 14, INK, "hv")
t(104, 1004, "max_steps · --deadline (wall-clock) · goal reanchor — a loop can't run until it burns the bill", 13.5, GRY)
panel(656, 958, 538, 64, 18, 11, CYAN, 1.3)
t(676, 982, "\U0001f5c4 PERSISTENT MEMORY", 14, INK, "hv")
t(676, 1004, "recall prior verified outcomes · remember only what passed (~/.verity-harness)", 13.5, GRY)
t(84, 1058, "+ QC SELF-HEAL · 5-BLOCK ERROR PROTOCOL (What/Why/Impact/Fix/Prevention) · LEDGER → `verity proof`",
  13, DIM, "mono", "start", 1)
t(84, 1086, '+ AUTONOMY: on "proceed", chain EVERY goal to completion; pause only for destructive/ambiguous acts',
  13, DIM, "mono", "start", 1)
arrow(640, 1144, 640, 1170)

# ---------- OUTPUT ----------
pill(640, 1108, 560, 40, "VERIFIED RESULT  +  auditable proof ledger", 16)

# ---------- (3) DISTRIBUTION ----------
panel(60, 1176, 1160, 56, 22, 13, CYAN)
t(84, 1199, "③ ALWAYS-ON · UNIVERSAL", 13, CYAN, "mono", "start", 2)
t(84, 1221, "Proxy :11500 (OpenAI-compatible — any client inherits gates + failover)   ·   "
            "injected into → Claude Code · Codex · Gemini CLI · local/OSS models", 14, GRY)

# ===================== assemble =====================
head = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="'Arial Narrow','Helvetica Neue',Arial,sans-serif" role="img" aria-labelledby="t d">
  <title id="t">VERITY architecture and control flow</title>
  <desc id="d">A goal enters the sovereign router (cloud peer chain failing over to a local floor), then runs through the discipline layer — pre-flight, reuse-first discovery, a think/act/verify loop with persistence and QC self-heal, and a done-funnel of evidence, calibration and objective gates with hard stops and persistent memory — producing a verified result, exposed via an always-on proxy and injected into every agent class. Panels use AVANI UI DNA augmented-ui corner-cut geometry.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#070a0d"/><stop offset="1" stop-color="#03060a"/></linearGradient>
    <pattern id="scan" width="3" height="3" patternUnits="userSpaceOnUse"><rect width="3" height="1" fill="#0c1a1d" opacity="0.5"/></pattern>
    <marker id="ar" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="{CYAN}"/></marker>
    <marker id="arm" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="{MAG}"/></marker>
    <style>
      .mono{{font-family:'SF Mono','Menlo','Consolas',monospace}}
      .hv{{font-family:'Arial Black','Helvetica Neue',Arial,sans-serif;font-weight:900}}
      .nar{{font-family:'Arial Narrow',Arial,sans-serif}}
    </style>
  </defs>
  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <rect width="{W}" height="{H}" fill="url(#scan)"/>
  <path d="M16,16 H1230 L1264,50 V1250 H66 L16,1200 Z" fill="none" stroke="#1f5c54" stroke-width="2"/>
  <path d="M16,70 V16 H70 M1264,1196 V1250 H1130" fill="none" stroke="{CYAN}" stroke-width="3"/>
  <rect x="16" y="1246" width="1248" height="4" fill="{MAG}"/>
'''
svg = head + "\n  " + "\n  ".join(S) + "\n</svg>\n"
import os
out = os.path.expanduser("~/repos/verity-harness/assets/architecture.svg")
open(out, "w").write(svg)
print("wrote", out, len(svg), "bytes,", len(S), "elements")

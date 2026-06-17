#!/usr/bin/env python3
"""VERITY gameplay promo — REAL footage, not a slideshow.

Records actual browser video of the Tetris that VERITY's harness made a model write
(demo-out/claude-opus-4.8/harness.html) being PLAYED by an injected auto-player bot
(greedy El-Tetris heuristic → competent, line-clearing play). Then brands it with a
corner badge + lower-third over the live footage and scores it with an ORIGINAL chiptune
(stdlib square-wave synth — NOT the copyrighted Tetris melody). Outro: the Truth Hawk card.

Pipeline: Playwright(video) → ffmpeg(scale/pad/overlay/concat) + stdlib wave(audio).
Out: assets/demo-gameplay-promo.mp4
"""
import os, subprocess, shutil, struct, wave, math, base64

ROOT = os.path.expanduser("~/repos/verity-harness")
ASSETS = os.path.join(ROOT, "assets")
GAME = os.path.join(ROOT, "demo-out", "claude-opus-4.8", "harness.html")
MASCOT = os.path.join(ASSETS, "mascot-hawk.png")
TMP = "/tmp/verity_gameplay"
PLAY_SECS = 19
W, H = 1280, 720
TEAL = "#2dd4bf"; MAG = "#d6299e"; BG = "#070a0d"; WHITE = "#eef6f4"; FG = "#cfe7e2"; DIM = "#5e7270"
MONO = "ui-monospace, 'SF Mono', Menlo, monospace"

# ── the auto-player: greedy heuristic, runs in page scope (globals are reachable) ──────────────
BOT_JS = r"""
(() => {
  const W8 = {height:-0.51, lines:0.76, holes:-0.36, bump:-0.18};
  const clone = b => b.map(r => r.slice());
  function rots(shape){ const out=[]; let s=shape; for(let i=0;i<4;i++){ out.push(s); s=rotate(s);} return out; }
  function landY(shape,x){ const p={type:current.type,shape,x,y:-2}; while(!collide(p,board)) p.y++; p.y--; return p.y; }
  function place(b,shape,x,y){ const c=clone(b); let ok=true; shape.forEach((row,yy)=>row.forEach((v,xx)=>{ if(v){const ny=y+yy,nx=x+xx; if(ny<0){ok=false;return;} c[ny][nx]=current.type;}})); return ok?c:null; }
  function evalB(b){
    let agg=0,holes=0,bump=0,lines=0; const hgt=[];
    for(let x=0;x<COLS;x++){ let h=0; for(let y=0;y<ROWS;y++){ if(b[y][x]){h=ROWS-y;break;} } hgt.push(h); agg+=h; }
    for(let x=0;x<COLS;x++){ let seen=false; for(let y=0;y<ROWS;y++){ if(b[y][x]) seen=true; else if(seen) holes++; } }
    for(let x=0;x<COLS-1;x++) bump+=Math.abs(hgt[x]-hgt[x+1]);
    for(let y=0;y<ROWS;y++){ let full=true; for(let x=0;x<COLS;x++) if(!b[y][x]){full=false;break;} if(full) lines++; }
    return W8.height*agg + W8.lines*lines + W8.holes*holes + W8.bump*bump;
  }
  function bestMove(){
    let best=null; const shapes=rots(current.shape);
    for(let r=0;r<shapes.length;r++){ const sh=shapes[r];
      for(let x=-2;x<COLS;x++){ const y=landY(sh,x); if(y<-1) continue;
        const b=place(board,sh,x,y); if(!b) continue;
        const sc=evalB(b); if(!best||sc>best.sc) best={sc,r,x,sh}; } }
    return best;
  }
  function shapeEq(a,b){ return JSON.stringify(a)===JSON.stringify(b); }
  window.__verityBot = setInterval(() => {
    if (typeof gameOver!=='undefined' && gameOver) { restart(); return; }
    if (typeof current==='undefined' || !current) return;
    const m = bestMove(); if(!m) { hardDrop(); return; }
    let guard=0; while(!shapeEq(current.shape,m.sh) && guard++<4) doRotate();
    guard=0; while(current.x>m.x && guard++<12) move(-1);
    guard=0; while(current.x<m.x && guard++<12) move(1);
    hardDrop(); draw();
  }, 270);
})();
"""

def synth_chiptune(path, seconds):
    """Original 8-bit chiptune: arpeggiated vi-IV-I-V (generic progression) + bass. stdlib only."""
    sr = 44100
    def sq(f, t):  # square wave sample at time t
        return 1.0 if math.sin(2*math.pi*f*t) >= 0 else -1.0
    NOTE = {n: 440.0*2**((i-9)/12) for i, n in enumerate(
        ["C","Cs","D","Ds","E","F","Fs","G","Gs","A","As","B"])}
    def freq(name, octave): return NOTE[name]*2**(octave-4)
    # 4 bars, each an arpeggio of a chord (8 eighth-notes), bass = root
    chords = [  # (arp notes [name,oct], bass [name,oct])
        ([("A",4),("C",5),("E",5),("A",5),("E",5),("C",5),("A",4),("E",5)], ("A",2)),
        ([("F",4),("A",4),("C",5),("F",5),("C",5),("A",4),("F",4),("C",5)], ("F",2)),
        ([("C",5),("E",5),("G",5),("C",6),("G",5),("E",5),("C",5),("G",5)], ("C",3)),
        ([("G",4),("B",4),("D",5),("G",5),("D",5),("B",4),("G",4),("D",5)], ("G",2)),
    ]
    eighth = 0.1875  # ~160bpm
    frames = []
    loop_dur = len(chords)*8*eighth
    total = 0.0
    while total < seconds + loop_dur:
        for arp, bassn in chords:
            bf = freq(*bassn)/2
            for note in arp:
                nf = freq(*note)
                n = int(sr*eighth)
                for i in range(n):
                    t = i/sr
                    env = min(1.0, (n-i)/(sr*0.03)) * min(1.0, i/(sr*0.005))  # quick attack, decay tail
                    lead = sq(nf, t)*0.22*env
                    bass = sq(bf, t)*0.16
                    s = max(-1.0, min(1.0, lead+bass))
                    frames.append(int(s*26000))
            total += 8*eighth
    # trim to length, fade out last 0.8s
    want = int(sr*seconds)
    frames = frames[:want]
    fo = int(sr*0.8)
    for i in range(max(0, len(frames)-fo), len(frames)):
        frames[i] = int(frames[i]*(len(frames)-i)/fo)
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", f) for f in frames))

def overlay_svg():
    with open(MASCOT, "rb") as f:
        uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
  width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <image xlink:href="{uri}" x="28" y="22" width="92" height="92"/>
  <text x="128" y="62" font-family="{MONO}" font-size="30" font-weight="800" fill="{WHITE}" letter-spacing="2">VERITY</text>
  <text x="128" y="90" font-family="{MONO}" font-size="15" fill="{TEAL}" letter-spacing="2">THE OPEN-SOURCE FABLE ALTERNATIVE</text>
  <rect x="0" y="{H-78}" width="{W}" height="78" fill="#05080b" opacity="0.82"/>
  <rect x="0" y="{H-78}" width="{W}" height="3" fill="{TEAL}"/>
  <text x="40" y="{H-44}" font-family="{MONO}" font-size="23" font-weight="700" fill="{WHITE}">
    This Tetris was written by an LLM — <tspan fill="{TEAL}">gated by VERITY</tspan> (run the test before "done").</text>
  <text x="40" y="{H-18}" font-family="{MONO}" font-size="17" fill="{DIM}">
    coding axis: 60% → 93% · same model, only the discipline changed · github.com/FutronPrime/verity-harness</text>
</svg>'''

def endcard_svg():
    cx = W//2
    with open(MASCOT, "rb") as f:
        uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
  width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs><radialGradient id="g" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="{TEAL}" stop-opacity="0.22"/><stop offset="100%" stop-color="{TEAL}" stop-opacity="0"/>
  </radialGradient></defs>
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <ellipse cx="{cx}" cy="235" rx="430" ry="300" fill="url(#g)"/>
  <image xlink:href="{uri}" x="{cx-210}" y="40" width="420" height="420"/>
  <text x="{cx}" y="495" text-anchor="middle" font-family="{MONO}" font-size="80" font-weight="800" fill="{WHITE}" letter-spacing="6">VERITY</text>
  <text x="{cx}" y="535" text-anchor="middle" font-family="{MONO}" font-size="21" font-weight="600" fill="{TEAL}" letter-spacing="4">THE OPEN-SOURCE FABLE ALTERNATIVE</text>
  <text x="{cx}" y="588" text-anchor="middle" font-family="{MONO}" font-size="23" font-weight="700" fill="{FG}">make ANY model verify instead of guess</text>
  <rect x="{cx-300}" y="612" width="600" height="46" rx="8" fill="#0c1116" stroke="{TEAL}" stroke-width="1.5"/>
  <text x="{cx}" y="642" text-anchor="middle" font-family="{MONO}" font-size="23" font-weight="700" fill="{TEAL}">github.com/FutronPrime/verity-harness</text>
  <rect x="32" y="{H-30}" width="{W-64}" height="3" fill="{MAG}"/>
</svg>'''

def record_gameplay(out_webm):
    from playwright.sync_api import sync_playwright
    vid_dir = os.path.join(TMP, "vid"); os.makedirs(vid_dir, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1000, "height": 720},
                            record_video_dir=vid_dir,
                            record_video_size={"width": 1000, "height": 720})
        pg = ctx.new_page()
        pg.goto("file://" + GAME)
        pg.add_style_tag(content="body{background:#070a0d!important;margin:0;display:flex;"
                                 "align-items:center;justify-content:center;min-height:100vh}")
        pg.wait_for_timeout(600)
        pg.evaluate(BOT_JS)
        pg.wait_for_timeout(PLAY_SECS * 1000)
        path = pg.video.path()
        ctx.close(); b.close()
    shutil.move(path, out_webm)

def run(*a):
    subprocess.run(a, check=True, capture_output=True)

def main():
    for t in ("rsvg-convert", "ffmpeg"):
        if not shutil.which(t): raise SystemExit(f"need {t}")
    if os.path.exists(TMP): shutil.rmtree(TMP)
    os.makedirs(TMP)
    webm = os.path.join(TMP, "raw.webm")
    print("recording real gameplay…"); record_gameplay(webm)
    # branding overlay + endcard → PNG
    for name, svg in (("overlay", overlay_svg()), ("endcard", endcard_svg())):
        sp = os.path.join(TMP, name+".svg"); open(sp, "w").write(svg)
        run("rsvg-convert", "-w", str(W), "-h", str(H), sp, "-o", os.path.join(TMP, name+".png"))
    # chiptune
    print("synthesizing chiptune…"); wav = os.path.join(TMP, "music.wav"); synth_chiptune(wav, PLAY_SECS+3)
    # 1) gameplay: scale+pad to 16:9 DNA bg, burn in branding overlay
    gp = os.path.join(TMP, "gameplay.mp4")
    run("ffmpeg", "-y", "-i", webm, "-i", os.path.join(TMP, "overlay.png"),
        "-filter_complex",
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x070a0d,setsar=1[bg];[bg][1:v]overlay=0:0,fps=30[v]",
        "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p", gp)
    # 2) outro card 2.5s
    outro = os.path.join(TMP, "outro.mp4")
    run("ffmpeg", "-y", "-loop", "1", "-t", "2.5", "-i", os.path.join(TMP, "endcard.png"),
        "-vf", f"scale={W}:{H},fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "20", outro)
    # 3) concat
    lst = os.path.join(TMP, "list.txt"); open(lst, "w").write(f"file '{gp}'\nfile '{outro}'\n")
    silent = os.path.join(TMP, "silent.mp4")
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent)
    # 4) mux chiptune (fit to video, fade handled in synth)
    out = os.path.join(ASSETS, "demo-gameplay-promo.mp4")
    run("ffmpeg", "-y", "-i", silent, "-i", wav, "-c:v", "copy",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out)
    print("OK", out)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""The fun, practical head-to-head: give the SAME model a real build task (e.g. "make Tetris"),
once RAW (one-shot) and once through VERITY's discipline (build → actually RUN it in a headless
browser → read the console errors → fix → repeat until it's clean). Then look at the two artifacts.

This is the YouTube "vibe check" made reproducible and honest: same model, same prompt, the only
difference is the harness forces it to run its own code and fix what's broken before calling it done.

Output (in ./demo-out/): naive.html + harness.html + their screenshots + a report.json.
Run:  python3 -m verity demo            # default: Tetris on the configured model
      python3 -m verity demo "build a playable Snake game in one HTML file" --model google/gemini-2.5-flash
"""
from __future__ import annotations

import json
import os
import re

DEFAULT_TASK = ("Build a complete, PLAYABLE Tetris game as a single self-contained .html file "
                "(inline CSS + JS, HTML5 canvas, no external libraries). It must have: the 7 "
                "tetromino pieces, arrow-key controls (left/right/down move, up rotates), line "
                "clearing with scoring, increasing speed, and a game-over state. Output ONLY the "
                "full HTML in one ```html code block.")

# Heuristic feature checklist for Tetris (evidence the build is actually complete, not a stub).
TETRIS_FEATURES = {
    "canvas": r"<canvas|getContext",
    "7 pieces": r"[IOTSZJL].*\[|SHAPES|TETROMINO|pieces",
    "rotation": r"rotat|transpose",
    "line clear": r"clearLines|removeRow|line.?clear|splice",
    "scoring": r"score",
    "keyboard": r"keydown|addEventListener\(['\"]key|ArrowLeft",
    "game over": r"game.?over|gameOver",
    "gravity/tick": r"setInterval|requestAnimationFrame|drop|tick",
}


def _extract_html(text: str) -> str:
    m = re.search(r"```(?:html)?\s*(.*?)```", text or "", re.S)
    code = m.group(1).strip() if m else (text or "").strip()
    if "<html" not in code.lower() and "<canvas" in code.lower():
        code = f"<!doctype html><html><body>{code}</body></html>"
    return code


def _features(html: str, checklist: dict) -> dict:
    return {name: bool(re.search(pat, html, re.I)) for name, pat in checklist.items()}


def _headless_check(path: str, keypress=True, record=False):
    """Open the HTML in a real headless browser; return (console_errors, screenshot, blank, filled).
    This is the crux: it RUNS the code instead of trusting it looks right. record=True also captures
    a real SCREEN RECORDING of the gameplay → path.replace('.html','.webm') (the video proof)."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return (["[playwright not installed — run `python3 -m verity web-setup`]"], None, None, 0.0)
    errors, shot = [], path.replace(".html", ".png")
    viddir = os.path.join(os.path.dirname(path), "_vid")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            if record:
                os.makedirs(viddir, exist_ok=True)
                ctx = b.new_context(viewport={"width": 420, "height": 720},
                                    record_video_dir=viddir, record_video_size={"width": 420, "height": 720})
                pg = ctx.new_page()
            else:
                ctx = None
                pg = b.new_page(viewport={"width": 420, "height": 720})
            pg.on("console", lambda m: errors.append(m.text[:200]) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
            pg.goto("file://" + os.path.abspath(path))
            pg.wait_for_timeout(1200)
            if keypress:
                # actually PLAY it — drop several pieces with rotations. Many one-shot games look
                # fine on load but throw (or freeze) once pieces lock / lines clear / it speeds up.
                seq = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "ArrowDown", "ArrowDown"]
                for n in range(40):
                    pg.keyboard.press(seq[n % len(seq)]); pg.wait_for_timeout(60)
                pg.wait_for_timeout(800)
            pg.screenshot(path=shot)
            # FUNCTIONAL signal: after 40 moves a working Tetris has LOCKED pieces stacked on the
            # board. Measure the fraction of canvas pixels that differ from the background — a broken
            # game (pieces don't lock, score stuck at 0, empty board) stays near-empty even after play.
            filled = pg.evaluate("""() => { const c=document.querySelector('canvas');
                if(!c) return 0; const x=c.getContext('2d'); if(!x) return 0;
                const d=x.getImageData(0,0,c.width,c.height).data; const bg=[d[0],d[1],d[2]];
                let nz=0,t=0; for(let i=0;i<d.length;i+=4){ t++;
                  if(Math.abs(d[i]-bg[0])+Math.abs(d[i+1]-bg[1])+Math.abs(d[i+2]-bg[2])>60) nz++; }
                return t ? nz/t : 0; }""")
            vidsrc = None
            if ctx is not None:
                vidsrc = pg.video.path() if pg.video else None
                ctx.close()   # finalizes the .webm
            b.close()
        # move the recording to a stable name next to the html
        if record and vidsrc and os.path.exists(vidsrc):
            import shutil as _sh
            try:
                _sh.move(vidsrc, path.replace(".html", ".webm"))
            except Exception:  # noqa: BLE001
                pass
        blank = filled < 0.004
        return (errors, shot, bool(blank), float(filled))
    except Exception as e:  # noqa: BLE001
        return ([f"[render failed: {type(e).__name__}: {e}"], shot if os.path.exists(shot) else None, None, 0.0)


def run(task: str = None, model: str = None, max_fixes: int = 4, verbose: bool = True,
        outdir: str = None, record: bool = True) -> dict:
    from .router import ask, chat
    from . import config
    task = task or DEFAULT_TASK
    outdir = os.path.abspath(outdir or "demo-out"); os.makedirs(outdir, exist_ok=True)
    checklist = TETRIS_FEATURES if "tetris" in task.lower() else \
        {"canvas": r"<canvas|getContext", "keyboard": r"keydown|key", "loop": r"setInterval|requestAnimationFrame"}

    tiers = None
    if model:
        tiers = [config.Tier(name=f"demo-{model.split('/')[-1][:16]}", protocol="openai",
                             base_url=config._T1_URL, model=model, api_key=config._T1_KEY,
                             timeout_s=max(config._T1_TIMEOUT, 120))]
    kw = {"tiers": tiers} if tiers else {}
    def _ask(p, sysp=None):
        r = ask(p, system=sysp, **kw); return r.text if hasattr(r, "text") else str(r)

    PLAYS = 0.03   # >=3% of the board filled after 40 moves = pieces actually locked / it plays
    def _real(errs):  # env/tooling sentinels (bracketed) are NOT the game's fault — don't "fix" them
        return [e for e in errs if not e.lstrip().startswith("[")]

    # ---------- NAIVE: one shot, ship it ----------
    if verbose: print("[demo] NAIVE — one-shot build…")
    naive_html = _extract_html(_ask(task))
    np_ = os.path.join(outdir, "naive.html"); open(np_, "w").write(naive_html)
    n_err, n_shot, n_blank, n_fill = _headless_check(np_, record=record)  # record the gameplay
    n_feat = _features(naive_html, checklist)

    # ---------- HARNESS: build → RUN+PLAY → read failures → fix → repeat ----------
    if verbose: print("[demo] HARNESS — build, then run-play-and-fix until it actually works…")
    h_html = _extract_html(_ask(task))
    rounds = 0
    h_err, h_fill, missing = [], 0.0, []
    for i in range(max_fixes):
        hp = os.path.join(outdir, "harness.html"); open(hp, "w").write(h_html)
        h_err, h_shot, h_blank, h_fill = _headless_check(hp)
        h_feat = _features(h_html, checklist)
        missing = [k for k, v in h_feat.items() if not v]
        real_err = _real(h_err); h_err = real_err
        plays = h_fill >= PLAYS
        if not real_err and not h_blank and not missing and plays:
            break  # VERIFIED: runs clean, renders, feature-complete, AND actually plays
        rounds += 1
        if verbose: print(f"   fix round {rounds}: {len(real_err)} err · blank={h_blank} · "
                          f"plays={plays} (fill={h_fill:.1%}) · missing={missing}")
        fixprompt = (f"This Tetris HTML was RUN in a real browser and PLAYED (40 key moves). Problems:\n"
                     f"- console errors: {real_err or 'none'}\n"
                     f"- canvas blank (nothing drawn): {h_blank}\n"
                     f"- DOESN'T PLAY: after 40 moves the board is still ~empty ({h_fill:.0%} filled) — "
                     f"pieces aren't locking / the game isn't progressing: {not plays}\n"
                     f"- missing features: {missing or 'none'}\n\nHere is the file:\n```html\n{h_html[:9000]}\n```\n"
                     f"Fix ALL of it so the game actually plays (pieces fall, lock, stack, lines clear, "
                     f"score increases). Output ONLY the corrected full HTML in one ```html block.")
        h_html = _extract_html(_ask(fixprompt))
    hp = os.path.join(outdir, "harness.html"); open(hp, "w").write(h_html)
    h_err, h_shot, h_blank, h_fill = _headless_check(hp, record=record); h_err = _real(h_err)  # record gameplay
    h_feat = _features(h_html, checklist)

    def _vid(p):
        v = p.replace(".html", ".webm")
        return v if os.path.exists(v) else None
    def _arm(html, err, blank, fill, feat, shot, f):
        return {"bytes": len(html), "console_errors": err, "blank": blank,
                "board_filled_pct": round(fill * 100, 1), "plays": fill >= PLAYS,
                "features_present": sum(feat.values()), "features_total": len(checklist),
                "features": feat, "screenshot": shot, "video": _vid(f), "file": f}
    report = {"task": task[:120], "model": model or "(configured tier)", "fix_rounds": rounds,
              "naive":   _arm(naive_html, n_err, n_blank, n_fill, n_feat, n_shot, np_),
              "harness": _arm(h_html, h_err, h_blank, h_fill, h_feat, h_shot, hp)}
    json.dump(report, open(os.path.join(outdir, "report.json"), "w"), indent=2)
    if verbose:
        n, h = report["naive"], report["harness"]
        print("\n──────── NAIVE vs VERITY (same model, real build, actually played) ────────")
        print(f"  NAIVE   : {n['features_present']}/{n['features_total']} feat · {len(n['console_errors'])} err · "
              f"{'BLANK' if n['blank'] else 'renders'} · board {n['board_filled_pct']}% filled · "
              f"{'PLAYS' if n['plays'] else 'DOESNT PLAY'}")
        print(f"  HARNESS : {h['features_present']}/{h['features_total']} feat · {len(h['console_errors'])} err · "
              f"{'BLANK' if h['blank'] else 'renders'} · board {h['board_filled_pct']}% filled · "
              f"{'PLAYS' if h['plays'] else 'DOESNT PLAY'}  (after {rounds} run-and-fix round(s))")
        print(f"  artifacts + screenshots → {outdir}/")
    return report


def run_models(models, task: str = None, max_fixes: int = 3, verbose: bool = True) -> list:
    """Robust spread: run the same build head-to-head across MANY models → see how each is improved.
    Each model writes its own demo-out/<slug>/ (naive+harness html, screenshots, .webm recordings)."""
    results = []
    for m in models:
        slug = m.split("/")[-1].replace(":", "-")
        if verbose:
            print(f"\n========== {m} ==========")
        try:
            r = run(task=task, model=m, max_fixes=max_fixes, verbose=verbose,
                    outdir=os.path.join("demo-out", slug))
            results.append(r)
        except Exception as e:  # noqa: BLE001 — one model failing must not kill the sweep
            if verbose:
                print(f"  [model {m} errored: {type(e).__name__}: {e}]")
            results.append({"model": m, "error": str(e)[:120]})
    if verbose:
        print("\n──────── MULTI-MODEL — naive vs VERITY (does the game actually PLAY?) ────────")
        for r in results:
            if "error" in r:
                print(f"  {r['model'][:30]:30}  [errored]"); continue
            n, h = r["naive"], r["harness"]
            print(f"  {r['model'].split('/')[-1][:24]:24}  naive {'PLAYS ' if n['plays'] else 'BROKEN'}"
                  f" ({n['board_filled_pct']:>4}%)  →  VERITY {'PLAYS ' if h['plays'] else 'BROKEN'}"
                  f" ({h['board_filled_pct']:>4}%)  [{r['fix_rounds']} fix]")
    return results


if __name__ == "__main__":
    import sys
    run()

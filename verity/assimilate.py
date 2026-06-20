#!/usr/bin/env python3
"""FUTRON Assimilation Loop — Scout → Filter → Assimilate → Synthesize.

The "watch everything for me / learn-to-do" engine. Turns the one input an LLM
normally can't take — a *video* — into queryable, regenerable knowledge, the way
a human watches and learns. Triage-FIRST so a whole-channel backlog never nukes
the token budget: cheap RSS metadata → relevance filter → only-then the expensive
multimodal watch.

Pipeline (see memory/spec-futron-assimilation-system-v1.md in the FUTRON brain):

  1. SCOUT       — poll YouTube channel RSS (no API key/quota), dedupe new videos.
  2. FILTER      — score metadata vs DJ's learning goals (router LLM, with a
                   deterministic keyword fallback so an outage never blocks it).
  3. ASSIMILATE  — shell out to taoufik123-collab/claude-watch's watch.py:
                   yt-dlp download → ffmpeg scene-change frames → captions/Whisper
                   transcript → structured report.md. Full visual "seeing" happens
                   when an AGENT (Claude Code / multimodal tier) Reads the frames;
                   headless gives a transcript-level synthesis (flagged honestly).
  4. SYNTHESIZE  — capture the assimilated knowledge into VERITY membank (bounded
                   persistent memory) so any FUTRON agent can recall the skill.

CLI:
  python3 -m verity assimilate targets                 # show config (channels + goals)
  python3 -m verity assimilate resolve @MarketMondays  # @handle -> channel_id
  python3 -m verity assimilate scout [channel_id]      # list NEW videos (RSS)
  python3 -m verity assimilate filter "<title>" [--goals "a,b"]   # triage one title
  python3 -m verity assimilate watch <url> [--intent "..."] [watch.py flags]
  python3 -m verity assimilate run [--watch] [--max N]  # full loop (queue; --watch = assimilate)

Pure stdlib. No hardcoded secrets. claude-watch handles its own ffmpeg/yt-dlp/keys.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from pathlib import Path
from xml.etree import ElementTree as ET

# ── paths / config ────────────────────────────────────────────────────────────
HOME = Path(os.path.expanduser("~"))
STATE_DIR = HOME / ".verity-harness"
CONFIG_PATH = STATE_DIR / "assimilate.json"
SEEN_PATH = STATE_DIR / "assimilate_seen.json"

# Where claude-watch was cloned. Override with $WATCH_SKILL_DIR.
DEFAULT_WATCH_DIRS = [
    HOME / "repos" / "claude-watch",
    HOME / ".claude" / "skills" / "watch",
    HOME / ".codex" / "skills" / "watch",
]
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
_YT_NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "media": "http://search.yahoo.com/mrss/"}
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) FUTRON-Assimilate/1.0"


@dataclass
class Channel:
    name: str
    channel_id: str = ""
    handle: str = ""                       # e.g. "@MarketMondays" — resolved lazily
    goals: list[str] = field(default_factory=list)
    schedule_hint: str = ""                # e.g. "Mon 18:00" — for schedule-learned scouting
    live: bool = False                     # channel posts LIVESTREAMS the RSS feed misses → also scout /streams


@dataclass
class Config:
    learning_goals: list[str] = field(default_factory=list)
    channels: list[Channel] = field(default_factory=list)
    watch_skill: str = ""                  # path to claude-watch/scripts/watch.py
    max_videos_per_run: int = 3
    include_streams: bool = True           # also pull each channel's /streams tab (RSS misses livestreams)
    # ── audio "hearing" (DJ's call: Gemini hears singing/comedic-timing/emotion that Whisper-text misses) ──
    gemini_cli: str = ""                                  # (deprecated path; the built-in transcriber is used)
    gemini_model: str = "gemini-2.5-flash"                # works on the FREE Gemini tier; multimodal video
    gemini_transcriber: str = "python3 -m verity video"   # BUILT-IN, self-contained (no external tool needed)
    # external taste profile to import channels FROM (FUTRON genie prefs; generic fallback = none)
    genie_prefs: str = os.environ.get(
        "GENIE_PREFS_PATH",
        os.path.expanduser("~/.openclaw/workspace/AVANI_SHARED_BRAIN/genie-mode-preferences.json"))


def _watch_script() -> str:
    """Locate claude-watch's watch.py."""
    env = os.environ.get("WATCH_SKILL_DIR")
    cands = ([Path(env)] if env else []) + DEFAULT_WATCH_DIRS
    for d in cands:
        p = d / "scripts" / "watch.py"
        if p.exists():
            return str(p)
        if d.name == "watch.py" and d.exists():
            return str(d)
    return ""


def default_config() -> Config:
    return Config(
        learning_goals=["AI infrastructure", "agent automation", "music production",
                        "DJ technique", "investing & markets", "content creation"],
        channels=[],
        watch_skill=_watch_script(),
        max_videos_per_run=3,
    )


def load_config() -> Config:
    if CONFIG_PATH.exists():
        raw = json.loads(CONFIG_PATH.read_text())
        chans = [Channel(**c) for c in raw.get("channels", [])]
        d = Config()  # defaults for any keys absent from older config files
        return Config(
            learning_goals=raw.get("learning_goals", []),
            channels=chans,
            watch_skill=raw.get("watch_skill") or _watch_script(),
            max_videos_per_run=int(raw.get("max_videos_per_run", 3)),
            gemini_cli=raw.get("gemini_cli", d.gemini_cli),
            gemini_model=raw.get("gemini_model", d.gemini_model),
            gemini_transcriber=raw.get("gemini_transcriber", d.gemini_transcriber),
            genie_prefs=raw.get("genie_prefs", d.genie_prefs),
            include_streams=raw.get("include_streams", d.include_streams),
        )
    cfg = default_config()
    save_config(cfg)
    return cfg


def save_config(cfg: Config) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    out = asdict(cfg)
    CONFIG_PATH.write_text(json.dumps(out, indent=2))


def _load_seen() -> set[str]:
    if SEEN_PATH.exists():
        try:
            return set(json.loads(SEEN_PATH.read_text()))
        except Exception:
            return set()
    return set()


def _save_seen(seen: set[str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(sorted(seen), indent=2))


def _http_get(url: str, timeout: float = 20.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ── stage 1: SCOUT ─────────────────────────────────────────────────────────────
def resolve_handle(handle: str) -> str:
    """@handle or channel URL -> channelId, by scraping the channel page."""
    handle = handle.strip()
    if handle.startswith("UC") and len(handle) == 24:
        return handle                              # already a channel id
    if handle.startswith("http"):
        url = handle
    else:
        h = handle if handle.startswith("@") else "@" + handle
        url = f"https://www.youtube.com/{h}"
    try:
        html = _http_get(url)
    except urllib.error.URLError as e:
        return ""
    m = re.search(r'"channelId":"(UC[0-9A-Za-z_-]{22})"', html) \
        or re.search(r'channel/(UC[0-9A-Za-z_-]{22})', html)
    return m.group(1) if m else ""


def scout_channel(channel_id: str, limit: int = 15) -> list[dict]:
    """Return recent videos from a channel's RSS feed (newest first)."""
    xml = _http_get(RSS_URL.format(cid=channel_id))
    root = ET.fromstring(xml)
    vids = []
    for entry in root.findall("atom:entry", _YT_NS)[:limit]:
        vid = entry.findtext("yt:videoId", default="", namespaces=_YT_NS)
        title = entry.findtext("atom:title", default="", namespaces=_YT_NS)
        published = entry.findtext("atom:published", default="", namespaces=_YT_NS)
        link_el = entry.find("atom:link", _YT_NS)
        link = link_el.get("href") if link_el is not None else f"https://youtu.be/{vid}"
        media = entry.find("media:group", _YT_NS)
        desc = ""
        if media is not None:
            desc = (media.findtext("media:description", default="", namespaces=_YT_NS) or "")[:500]
        vids.append({"video_id": vid, "title": title, "published": published,
                     "url": link, "description": desc, "channel_id": channel_id})
    return vids


def scout_streams(channel_id: str, limit: int = 8) -> list[dict]:
    """Recent LIVESTREAMS/premieres via yt-dlp's /streams tab — the RSS feed misses these entirely
    (verified 2026-06-18: Alex Finn's whole LIVE output is absent from his RSS). Currently-live and
    upcoming streams are skipped (nothing to assimilate yet); completed VODs are returned."""
    import shutil
    if not shutil.which("yt-dlp"):
        return []
    url = f"https://www.youtube.com/channel/{channel_id}/streams"
    try:
        p = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--no-warnings", "-I", f"1:{limit}",
             "--print", "%(id)s\t%(title)s\t%(live_status)s", url],
            capture_output=True, text=True, timeout=90)
    except Exception:
        return []
    out = []
    for line in (p.stdout or "").strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or not parts[0]:
            continue
        vid, title = parts[0], parts[1]
        live_status = parts[2] if len(parts) > 2 else ""
        if live_status in ("is_live", "is_upcoming"):   # can't assimilate a stream that hasn't finished
            continue
        out.append({"video_id": vid, "title": title, "published": "",
                    "url": f"https://youtu.be/{vid}", "description": "",
                    "channel_id": channel_id, "is_live_vod": True})
    return out


def scout_new(channel_id: str, mark: bool = False, include_streams: bool = False) -> list[dict]:
    """Videos not seen before (RSS + optionally the /streams tab). If mark=True, record as seen."""
    seen = _load_seen()
    items = scout_channel(channel_id)
    if include_streams:
        have = {v["video_id"] for v in items}
        for s in scout_streams(channel_id):
            if s["video_id"] not in have:
                items.append(s); have.add(s["video_id"])
    fresh = [v for v in items if v["video_id"] not in seen]
    if mark and fresh:
        seen |= {v["video_id"] for v in fresh}
        _save_seen(seen)
    return fresh


# ── stage 2: FILTER (triage) ────────────────────────────────────────────────────
def _deterministic_score(title: str, desc: str, goals: list[str]) -> tuple[float, str]:
    """Keyword-overlap fallback — never blocks on an LLM outage (Borg: 2nd backend)."""
    text = (title + " " + desc).lower()
    hits = [g for g in goals if any(tok in text for tok in g.lower().split() if len(tok) > 3)]
    score = min(1.0, len(hits) / max(1, len(goals)) + (0.3 if hits else 0.0))
    reason = f"keyword overlap on: {', '.join(hits)}" if hits else "no goal-keyword overlap"
    return round(score, 2), reason


def triage(title: str, desc: str, goals: list[str], use_llm: bool = True) -> dict:
    """Score a video's relevance to the learning goals. Returns {keep, score, reason, via}."""
    if use_llm:
        try:
            from .router import ask, AllTiersFailed
            prompt = (
                "You are a triage filter for a personal knowledge-assimilation system.\n"
                f"Learning goals: {', '.join(goals)}\n"
                f"Video title: {title}\nDescription: {desc[:400]}\n\n"
                "Rate relevance 0.0-1.0 to the goals and decide keep/skip. "
                'Reply ONLY compact JSON: {"score": <float>, "keep": <bool>, "reason": "<short>"}'
            )
            r = ask(prompt, verbose=False)
            m = re.search(r"\{.*\}", r.text, re.S)
            if m:
                d = json.loads(m.group(0))
                return {"keep": bool(d.get("keep", d.get("score", 0) >= 0.5)),
                        "score": float(d.get("score", 0.0)),
                        "reason": str(d.get("reason", ""))[:200], "via": f"llm:{r.tier}"}
        except Exception as e:
            pass  # fall through to deterministic
    score, reason = _deterministic_score(title, desc, goals)
    return {"keep": score >= 0.4, "score": score, "reason": reason, "via": "deterministic"}


# ── stage 3: ASSIMILATE (claude-watch wrapper) ──────────────────────────────────
def assimilate(url: str, intent: str = "", extra: list[str] | None = None,
               watch_script: str = "") -> dict:
    """Run claude-watch on a video. Returns {ok, workdir, report, stdout, note}.

    NOTE: full *visual* assimilation requires an agent (Claude Code / multimodal tier)
    to Read the emitted frames and fill report.md. Run headless, you still get frames +
    transcript + a skeleton report (transcript-level synthesis is then possible)."""
    ws = watch_script or _watch_script()
    if not ws:
        return {"ok": False, "note": "claude-watch not found. Clone it: "
                "git clone https://github.com/taoufik123-collab/claude-watch.git ~/repos/claude-watch "
                "(or set $WATCH_SKILL_DIR)."}
    cmd = [sys.executable, ws, url]
    if intent:
        cmd += ["--intent", intent]
    if extra:
        cmd += extra
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return {"ok": False, "note": "watch.py timed out (>30min) — try --start/--end focused mode."}
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    # watch.py prints the workdir + report path; surface them.
    wd = re.search(r"(/[^\s]+?/(?:tmp|watch)[^\s]*)", out)
    rep = re.search(r"(/[^\s]+report\.md)", out)
    return {"ok": p.returncode == 0, "workdir": wd.group(1) if wd else "",
            "report": rep.group(1) if rep else "", "stdout": out[-4000:],
            "note": "frames+transcript emitted; have an agent Read frames to fill report.md"}


# ── stage 4: SYNTHESIZE ─────────────────────────────────────────────────────────
def synthesize(report_path: str, intent: str = "") -> dict:
    """Capture assimilated knowledge into VERITY membank (bounded persistent memory)."""
    p = Path(report_path)
    if not p.exists():
        return {"ok": False, "note": f"report not found: {report_path}"}
    text = p.read_text(errors="replace")
    try:
        from . import membank as _mb
        head = text[:1800]
        note = f"[ASSIMILATED VIDEO] intent={intent or 'general'}\n{head}"
        _mb.capture(note, scope="lesson")
        return {"ok": True, "note": "captured into membank (scope=lesson)"}
    except Exception as e:
        return {"ok": False, "note": f"membank capture failed: {e}"}


# ── GEMINI "hearing" — capture what Whisper-text CAN'T ──────────────────────────
# DJ's call (2026-06-18): a text transcript throws away the performance. Gemini natively
# HEARS — singing/pitch, comedic timing, acting range, emotional affect, accent, laugh —
# so for assimilating a PERSON or a PERFORMER it carries signal Whisper drops on the floor.
PERFORMANCE_PROMPT = (
    "You are analyzing the AUDIO/PERFORMANCE of this media for a knowledge-assimilation system "
    "that quantifies human expression so it can be studied and faithfully recreated. Do NOT just "
    "transcribe. Produce a structured analysis covering, with timestamps where it changes:\n"
    "1. VOICE — timbre, pitch range (low/mid/high), resonance, breathiness, raspiness, volume dynamics.\n"
    "2. SINGING (if any) — melody contour, pitch accuracy, vibrato, runs, key/register, tone.\n"
    "3. CADENCE & TIMING — pacing (slow/measured/rapid), pauses, rhythm, comedic timing & beats, "
    "setup→punchline gaps, emphasis patterns.\n"
    "4. EMOTION & DELIVERY — emotional affect over time (warmth, excitement, anger, sadness, irony, "
    "deadpan), sincerity vs sarcasm, energy curve.\n"
    "5. ACTING RANGE & PERSONALITY — expressiveness, character voices, verbal signatures/catchphrases, "
    "filler words, laugh character, accent/dialect/regional markers.\n"
    "6. RECREATION NOTES — the concrete, quantified cues a voice-clone + performance-direction system "
    "would need to reproduce this delivery convincingly.\n"
    "Be specific and observational; cite what you HEAR, not assumptions.")


def gemini_listen(media: str, mode: str = "performance", model: str = "",
                  cfg: "Config | None" = None) -> dict:
    """Have Gemini HEAR a video/audio (or URL). mode='performance' = vocal/emotional/timing
    analysis (the Whisper-can't layer); mode='transcript' = multimodal verbatim via the FUTRON
    transcriber. Returns {ok, mode, model, text, note}."""
    cfg = cfg or load_config()
    model = model or cfg.gemini_model
    if mode == "transcript":
        # reuse-first: the proven multimodal transcriber (Gemini watches+listens).
        import shutil
        if not shutil.which(cfg.gemini_transcriber.split()[0]):
            return {"ok": False, "note": f"transcriber '{cfg.gemini_transcriber}' not on PATH"}
        cmd = cfg.gemini_transcriber.split() + [media, "--model", model]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            return {"ok": p.returncode == 0, "mode": mode, "model": model,
                    "text": (p.stdout or "")[:20000], "note": p.stderr[-400:] if p.returncode else ""}
        except Exception as e:
            return {"ok": False, "note": f"transcriber error: {e}"}
    # performance mode → the Gemini CLI (DJ wants the 3.1-pro-preview CLI path) with @file attach.
    # The CLI's @ attaches LOCAL files only — it can't fetch a URL — so localize the audio first.
    import shutil
    if not shutil.which(cfg.gemini_cli):
        return {"ok": False, "note": f"gemini CLI '{cfg.gemini_cli}' not on PATH"}
    tmp_audio = ""
    if media.startswith("http"):
        tmp_audio = _download_audio(media)
        if not tmp_audio:
            return {"ok": False, "mode": mode,
                    "note": "couldn't localize audio for the performance pass (need yt-dlp+ffmpeg); "
                            "pass a local clip, or use --mode transcript"}
        ref = tmp_audio
    else:
        ref = os.path.abspath(media)
    prompt = f"{PERFORMANCE_PROMPT}\n\nMedia to analyze: @{ref}"
    try:
        p = subprocess.run([cfg.gemini_cli, "-m", model, "-p", prompt],
                           capture_output=True, text=True, timeout=900)
        return {"ok": p.returncode == 0, "mode": mode, "model": model,
                "text": (p.stdout or "").strip()[:20000],
                "note": p.stderr[-400:] if p.returncode else "performance analysis via gemini CLI"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "note": "gemini CLI timed out (>15min) — try a shorter clip/--start/--end"}
    except Exception as e:
        return {"ok": False, "note": f"gemini CLI error: {e}"}
    finally:
        if tmp_audio:
            try:
                os.remove(tmp_audio)
            except OSError:
                pass


def _download_audio(url: str) -> str:
    """Download a compact audio file for a Gemini performance pass (the CLI @ needs a local file)."""
    import shutil, tempfile
    if not shutil.which("yt-dlp"):
        return ""
    stem = os.path.join(tempfile.gettempdir(), "assim-audio-" + _slug(url)[:24])
    try:
        subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", "bestaudio/best",
                        "-x", "--audio-format", "m4a", "-o", stem + ".%(ext)s", url],
                       capture_output=True, text=True, timeout=600)
    except Exception:
        return ""
    for ext in ("m4a", "mp3", "webm", "opus", "wav"):
        if os.path.exists(stem + "." + ext):
            return stem + "." + ext
    return ""


# ── PERSONA / DIGITAL DOUBLE — molecular-level human assimilation ────────────────
# DJ's intent: take a video of a person (e.g. his parents) and capture them so completely —
# looks, voice, mannerisms, personality — that a faithful digital double can be recreated, a
# way to preserve and honor someone, especially against the day they're no longer here.
# Ties to the FUTRON LAWs: character-identity-fidelity + reference-image-required-for-generation.
PERSONA_DIR = STATE_DIR / "personas"

PERSONA_DOSSIER = """# DIGITAL DOUBLE DOSSIER — {name}

> **Purpose & consent:** legacy / memorial preservation of a real person, to honor and faithfully
> recreate them. Handle with care and respect. Recreation for any other purpose requires {name}'s
> (or their family's) consent. Source: `{source}` · captured {date}.

## 1. Identity
- Name: {name}
- Relationship / context: <!-- pending: who they are to DJ -->
- Approx age in footage / era: <!-- pending -->

## 2. Physical (fill from FRAMES — read every hero frame)
- **Face geometry** — head/face shape, proportions (eye spacing, nose, lips, jaw, chin, brow, cheekbones, forehead).
- **Eyes** — color, shape, lid, signature expression.
- **Skin** — tone (be specific), texture, marks/moles/scars, wrinkles & where.
- **Hair** — color, texture, hairline, style, facial hair.
- **Distinguishing features** — anything that makes them unmistakably them.
- **Body** — build, height impression, posture, hands.
- **Wardrobe/era markers** — <!-- pending -->
<!-- pending Claude fill: physical from frames -->

## 3. Voice & speech (fill from GEMINI performance analysis)
- Timbre, pitch range, accent/dialect, cadence, volume dynamics.
- Speech signatures — catchphrases, filler words, laugh character, singing (if any).
<!-- pending fill: paste gemini_listen(performance) output here -->

## 4. Mannerisms & non-verbal
- Gestures, hand habits, facial expressions, smile, eye contact, head tilt, posture, micro-habits.
- Emotional range & how it shows on the face/body.
<!-- pending Claude fill: mannerisms from frames + audio -->

## 5. Personality & essence
- Humor style, warmth, values, how they make people feel, verbal worldview.
<!-- pending Claude fill -->

## 6. Reference assets (the recreation kit)
- Best FACE frame(s): {frames_dir}
- Voice clip(s): {audio_note}
- Recreation path: clean face ref → image model character sheet (per character-identity-fidelity LAW) →
  voice clone from clips → performance-direct with the Section 3 cues.

## 7. Provenance
- Workdir: {workdir}
- Frames: {frames_dir}
- Generated by `verity assimilate persona`.
"""


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:60] or "person"


def persona(video: str, name: str, extra: list[str] | None = None,
            cfg: "Config | None" = None) -> dict:
    """Build a Digital Double Dossier from a video of a person: claude-watch frames + a Gemini
    performance/voice pass + a structured dossier the agent finishes by reading the frames."""
    cfg = cfg or load_config()
    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slug(name)
    pdir = PERSONA_DIR / slug
    pdir.mkdir(parents=True, exist_ok=True)
    # 1. visual pass — dense + high-res so on-face detail survives (a person, not a tutorial).
    flags = ["--resolution", "1024"] + (extra or [])
    av = assimilate(video, intent=f"build a faithful physical+behavioral profile of {name}",
                    extra=flags, watch_script=cfg.watch_skill)
    # 2. audio/performance pass — the layer Whisper text drops (voice, emotion, mannerism-in-speech).
    listen = gemini_listen(video, mode="performance", cfg=cfg)
    # 3. emit the dossier skeleton (agent fills physical/mannerism from frames; audio prefilled below).
    from datetime import date  # date.today() is allowed (not the banned argless now())
    dossier = PERSONA_DOSSIER.format(
        name=name, source=video, date="(captured this run)",
        frames_dir=av.get("workdir", "(see watch output)"),
        audio_note="extracted by claude-watch in the workdir" if av.get("ok") else "(audio pass pending)",
        workdir=av.get("workdir", ""))
    if listen.get("ok") and listen.get("text"):
        dossier = dossier.replace(
            "<!-- pending fill: paste gemini_listen(performance) output here -->",
            "### Gemini performance analysis (auto)\n" + listen["text"])
    dpath = pdir / "dossier.md"
    dpath.write_text(dossier)
    # capture a pointer into persistent memory
    try:
        from . import membank as _mb
        _mb.capture(f"[DIGITAL DOUBLE] {name} — dossier at {dpath}. "
                    f"voice/performance captured via Gemini; physical refs in {av.get('workdir','')}.",
                    scope="project")
    except Exception:
        pass
    return {"ok": True, "name": name, "dossier": str(dpath),
            "visual": {k: av.get(k) for k in ("ok", "workdir", "report")},
            "audio": {"ok": listen.get("ok"), "note": listen.get("note")},
            "note": f"dossier scaffolded at {dpath} — have an agent Read the frames to fill the "
                    "physical + mannerism sections."}


# ── IMPORT favorite channels from an external taste profile (genie prefs) ────────
def import_genie(cfg: "Config | None" = None, write: bool = True) -> dict:
    """Merge the channels from DJ's genie-mode-preferences.json (youtube_personalities + podcasts)
    into the assimilate config. Append-only (the genie list is a living list — never replace)."""
    cfg = cfg or load_config()
    pref_path = Path(cfg.genie_prefs)
    if not pref_path.exists():
        return {"ok": False, "note": f"genie prefs not found: {pref_path}"}
    prefs = json.loads(pref_path.read_text()).get("preferences", {})
    have_names = {c.name.lower() for c in cfg.channels}
    have_ids = {c.channel_id for c in cfg.channels if c.channel_id}
    candidates = []
    for p in prefs.get("youtube_personalities", []):
        nm = p.get("channel") or p.get("name")
        candidates.append((p.get("name", nm), nm, p.get("focus", "")))
    for p in prefs.get("podcasts", []):
        candidates.append((p.get("title"), p.get("title"), "podcast"))
    added, skipped = [], []
    for disp, query, focus in candidates:
        if not disp or disp.lower() in have_names:
            skipped.append(disp); continue
        cid = _ytdlp_channel_id(query)
        if cid and cid in have_ids:          # same channel under a different name → don't duplicate
            skipped.append(f"{disp} (dup of existing {cid})"); continue
        ch = Channel(name=disp, channel_id=cid, handle="", goals=_genie_goals(focus, disp),
                     schedule_hint="source:genie-prefs" + ("" if cid else " (UNRESOLVED — set channel_id)"))
        cfg.channels.append(ch)
        added.append({"name": disp, "channel_id": cid or "UNRESOLVED", "focus": focus})
        have_names.add(disp.lower())
        if cid:
            have_ids.add(cid)
    if write and added:
        save_config(cfg)
    return {"ok": True, "added": added, "skipped": skipped,
            "note": f"{len(added)} channel(s) imported from genie prefs, {len(skipped)} already present/dup"}


def _genie_goals(focus: str, name: str = "") -> list[str]:
    """Map a genie-prefs entry (focus + channel name) to assimilation learning goals.
    Reads the NAME too, since podcasts carry 'focus=podcast' and the real signal is the title."""
    table = [
        (("dating", "mindset", "alpha male"), ["dating & attraction dynamics", "non-verbal communication"]),
        (("comedy", "stand-up", "crowd work", "comedian", "lovely ti"), ["comedic timing & crowd work"]),
        (("rocket", "texan", "locker room", "locked on", "sports", "nba", "nfl"), ["sports analysis"]),
        (("ai ", "a.i", "tech", "strategy daily"), ["AI tools", "AI infrastructure"]),
        (("market", "invest", "leisure", "wealth", "budden"), ["investing & markets", "culture & entertainment news"]),
        (("politic",), ["history & geopolitics", "media commentary"]),
        (("film", "comics", "entertainment", "review", "trailer", "media"), ["culture & entertainment news", "media commentary"]),
        (("greenleaf", "faith", "gospel"), ["culture & entertainment news"]),
    ]
    hay = ((focus or "") + " " + (name or "")).lower()
    for keys, goals in table:
        if any(k in hay for k in keys):
            return goals
    return ["culture & entertainment news"]  # safe general default, never mislabel as AI


def _ytdlp_channel_id(query: str) -> str:
    """Resolve a channel name -> UC… id via yt-dlp search (best-effort)."""
    import shutil
    if not shutil.which("yt-dlp"):
        return ""
    try:
        p = subprocess.run(
            ["yt-dlp", "--quiet", "--no-warnings", "--playlist-items", "1",
             "--print", "%(channel_id)s", f"ytsearch1:{query}"],
            capture_output=True, text=True, timeout=60)
        out = (p.stdout or "").strip().splitlines()
        cid = out[0].strip() if out else ""
        return cid if cid.startswith("UC") else ""
    except Exception:
        return ""


# ── the loop ────────────────────────────────────────────────────────────────────
def run(do_watch: bool = False, max_videos: int = 0, verbose: bool = True) -> dict:
    cfg = load_config()
    max_videos = max_videos or cfg.max_videos_per_run
    if not cfg.channels:
        return {"ok": False, "note": f"no channels configured. Edit {CONFIG_PATH} "
                "(add {{name, channel_id|handle, goals}}) then re-run."}
    queue, watched = [], []
    for ch in cfg.channels:
        cid = ch.channel_id or (resolve_handle(ch.handle) if ch.handle else "")
        if not cid:
            if verbose:
                print(f"[scout] {ch.name}: no channel_id (set channel_id or a resolvable handle)")
            continue
        try:
            fresh = scout_new(cid, mark=True, include_streams=(cfg.include_streams or ch.live))
        except Exception as e:
            if verbose:
                print(f"[scout] {ch.name}: feed error: {e}")
            continue
        goals = ch.goals or cfg.learning_goals
        for v in fresh:
            t = triage(v["title"], v["description"], goals)
            if verbose:
                print(f"[filter] {'KEEP' if t['keep'] else 'skip'} ({t['score']:.2f} {t['via']}) "
                      f"{v['title'][:70]}  — {t['reason'][:60]}")
            if t["keep"]:
                queue.append({**v, "intent": ", ".join(goals), **t})
    queue = queue[:max_videos]
    if do_watch:
        for v in queue:
            if verbose:
                print(f"[assimilate] watching: {v['title'][:60]}")
            a = assimilate(v["url"], intent=v["intent"])
            if a.get("ok") and a.get("report"):
                synthesize(a["report"], intent=v["intent"])
            watched.append({"title": v["title"], "url": v["url"], **a})
    return {"ok": True, "queued": queue, "watched": watched,
            "note": f"{len(queue)} video(s) queued"
                    + (f", {len(watched)} assimilated" if do_watch else " (use --watch to assimilate)")}


# ── HEADLESS "full seeing" via Gemini — closes the agent-in-loop gap ─────────────
# The old honesty caveat was "headless = transcript-only; only an agent can SEE the frames."
# Gemini removes that limit: it ingests the whole video (sees on-screen + hears audio) AND it's
# far cheaper than burning Claude Opus tokens — so autonomous, scheduled assimilation is now both
# possible AND affordable. Claude-in-the-loop stays the premium tier for deep one-offs.
def gemini_watch(media: str, intent: str = "", visual: bool = False,
                 with_performance: bool = False, cfg: "Config | None" = None) -> dict:
    """Headless watch via Gemini: multimodal read of the video → structured brief through the intent
    lens. with_performance=True adds the (heavier) vocal/emotion pass — off by default so the daily
    digest stays lean. Returns {ok, analysis, transcript_len, performance, model}."""
    cfg = cfg or load_config()
    import shutil
    transcript = ""
    base = cfg.gemini_transcriber.split()[0]
    if shutil.which(base):
        tcmd = cfg.gemini_transcriber.split() + [media, "--model", cfg.gemini_model]
        if visual:
            tcmd.append("--visual")              # premium: also capture on-screen text/UI
        try:
            p = subprocess.run(tcmd, capture_output=True, text=True, timeout=1200)
            if p.returncode == 0:
                transcript = (p.stdout or "")[:30000]
        except Exception:
            pass
    if not transcript:                            # fallback to claude-watch's text path
        a = assimilate(media, intent=intent, watch_script=cfg.watch_skill)
        transcript = (a.get("stdout", "") or "")[:8000]
    if not transcript:
        return {"ok": False, "analysis": "", "note": "no transcript (need gemini transcriber or claude-watch)"}
    perf = gemini_listen(media, mode="performance", cfg=cfg) if with_performance else {"ok": False}
    synth = (
        f"You watched a video. Through the lens of '{intent or 'general interest'}', write a tight "
        "structured brief: \n**TL;DR** (3-5 bullets) · **Key moments** (timestamps if present) · "
        "**On-screen / shown** (UI, steps, visuals) · **Entities** (people/tools/companies) · "
        "**Concepts & takeaways** · **1-line editorial/performance note**. Be concise and faithful "
        "to what was actually shown and said.\n\n=== TRANSCRIPT ===\n" + transcript +
        (("\n\n=== PERFORMANCE/AUDIO ===\n" + perf["text"]) if perf.get("ok") and perf.get("text") else ""))
    analysis = ""
    if shutil.which(cfg.gemini_cli):
        try:
            p = subprocess.run([cfg.gemini_cli, "-m", cfg.gemini_model, "-p", synth],
                               capture_output=True, text=True, timeout=600)
            if p.returncode == 0:
                analysis = (p.stdout or "").strip()
        except Exception:
            pass
    return {"ok": bool(analysis), "analysis": analysis or transcript[:2000],
            "transcript_len": len(transcript), "performance": bool(perf.get("ok")),
            "model": cfg.gemini_model}


# ── DIGEST — the efficient scheduler entry point (spread out, budgeted, cheap) ───
# Scout + triage are ~free (RSS + tiny metadata calls), so they run daily. The expensive WATCH is
# budgeted (default 2/day) and rotated (≤1 per channel/run) so a 26-channel roster spreads itself
# across days instead of spiking — and each watch goes through cheap Gemini, not Opus.
DIGEST_DIR = STATE_DIR / "digests"


def digest(budget: int = 2, scout_only: bool = False, visual: bool = True,
           smart: bool = False, cfg: "Config | None" = None, verbose: bool = True) -> dict:
    # smart=False → DETERMINISTIC triage (instant, zero tokens): the daily job stays cheap; the only
    # token spend is the budgeted Gemini watches. smart=True opts into LLM triage for finer filtering.
    # visual=True (DEFAULT) → Gemini SEES the video (on-screen content), not just hears it — the whole
    # point of "watch" is the visual intel. include_streams catches livestreams the RSS feed misses.
    cfg = cfg or load_config()
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import date
    today = date.today().isoformat()
    new_items = []
    for ch in cfg.channels:
        cid = ch.channel_id or (resolve_handle(ch.handle) if ch.handle else "")
        if not cid:
            continue
        try:
            fresh = scout_new(cid, mark=True, include_streams=(cfg.include_streams or ch.live))
        except Exception as e:
            if verbose:
                print(f"[digest] {ch.name}: feed error: {e}")
            continue
        goals = ch.goals or cfg.learning_goals
        for v in fresh:
            t = triage(v["title"], v["description"], goals, use_llm=smart)
            new_items.append({**v, "channel": ch.name, "intent": ", ".join(goals[:3]), **t})
    keepers = sorted([v for v in new_items if v.get("keep")], key=lambda x: x["score"], reverse=True)
    picked, seen_ch = [], set()
    if not scout_only:
        for v in keepers:                          # rotation: ≤1 per channel, up to budget
            if v["channel"] in seen_ch:
                continue
            picked.append(v); seen_ch.add(v["channel"])
            if len(picked) >= budget:
                break
    assimilated = []
    for v in picked:
        if verbose:
            print(f"[digest] assimilating (gemini): {v['channel']} — {v['title'][:55]}")
        gw = gemini_watch(v["url"], intent=v["intent"], visual=visual, cfg=cfg)
        assimilated.append({**v, "analysis": gw.get("analysis", ""), "_ok": gw.get("ok")})
        try:
            from . import membank as _mb
            _mb.capture(f"[DIGEST {today}] {v['channel']}: {v['title']}\n{gw.get('analysis','')[:1500]}",
                        scope="lesson")
        except Exception:
            pass
    md = _render_digest(today, new_items, keepers, assimilated, scout_only)
    path = DIGEST_DIR / f"{today}.md"
    path.write_text(md)
    if verbose:
        print(f"\n[digest] {len(new_items)} new · {len(keepers)} relevant · "
              f"{len(assimilated)} assimilated → {path}")
    return {"ok": True, "date": today, "new": len(new_items), "relevant": len(keepers),
            "assimilated": len(assimilated), "digest": str(path)}


def _render_digest(day, new_items, keepers, assimilated, scout_only) -> str:
    lines = [f"# Assimilation Digest — {day}", "",
             f"_{len(new_items)} new across your channels · {len(keepers)} relevant · "
             f"{len(assimilated)} assimilated_", ""]
    if assimilated:
        lines.append("## 🎬 Assimilated (watched for you)\n")
        for v in assimilated:
            lines += [f"### {v['channel']} — {v['title']}",
                      f"<{v['url']}> · relevance {v['score']:.2f}", "",
                      v.get("analysis") or "_(analysis unavailable)_", ""]
    if keepers:
        lines.append("## 📌 Worth watching (queued, not yet assimilated)\n")
        for v in keepers:
            if any(a["url"] == v["url"] for a in assimilated):
                continue
            lines.append(f"- **{v['channel']}** — [{v['title']}]({v['url']}) "
                         f"· {v['score']:.2f} · _{v.get('reason','')[:60]}_")
        lines.append("")
    skipped = [v for v in new_items if not v.get("keep")]
    if skipped:
        lines.append(f"## 🗂️ New but off-goal ({len(skipped)})\n")
        for v in skipped[:30]:
            lines.append(f"- {v['channel']} — {v['title']}")
        lines.append("")
    if not new_items:
        lines.append("_No new videos since the last run._")
    return "\n".join(lines)


# ── CLI dispatch (called from verity/__main__.py) ───────────────────────────────
def cli(rest: list[str]) -> None:
    sub = rest[0] if rest else "targets"
    args = rest[1:]

    if sub == "targets":
        cfg = load_config()
        print(f"config: {CONFIG_PATH}")
        print(f"watch_skill: {cfg.watch_skill or '(NOT FOUND — clone claude-watch)'}")
        print(f"learning_goals: {', '.join(cfg.learning_goals)}")
        print(f"channels ({len(cfg.channels)}):")
        for c in cfg.channels:
            print(f"  - {c.name}  id={c.channel_id or c.handle or '?'}  goals={c.goals or '(global)'}")
        if not cfg.channels:
            print("  (none — add channels to the config, then `assimilate run`)")

    elif sub == "resolve":
        if not args:
            print("usage: assimilate resolve <@handle|url>", file=sys.stderr); sys.exit(2)
        cid = resolve_handle(args[0])
        print(cid or "(could not resolve — pass an explicit UC… channel_id)")

    elif sub == "scout":
        cfg = load_config()
        if args:
            cid = args[0] if args[0].startswith("UC") else resolve_handle(args[0])
            vids = scout_channel(cid)
            for v in vids:
                print(f"{v['published'][:10]}  {v['video_id']}  {v['title']}")
        else:
            for ch in cfg.channels:
                cid = ch.channel_id or resolve_handle(ch.handle)
                if not cid:
                    print(f"# {ch.name}: unresolved"); continue
                print(f"# {ch.name}")
                for v in scout_new(cid):
                    print(f"  NEW  {v['published'][:10]}  {v['title']}")

    elif sub == "filter":
        if not args:
            print('usage: assimilate filter "<title>" [--desc "..."] [--goals "a,b"]',
                  file=sys.stderr); sys.exit(2)
        title = args[0]
        desc = ""
        goals = load_config().learning_goals
        if "--desc" in args:
            i = args.index("--desc"); desc = args[i + 1] if i + 1 < len(args) else ""
        if "--goals" in args:
            i = args.index("--goals")
            goals = [g.strip() for g in (args[i + 1] if i + 1 < len(args) else "").split(",") if g.strip()]
        print(json.dumps(triage(title, desc, goals), indent=2))

    elif sub == "watch":
        if not args:
            print('usage: assimilate watch <url> [--intent "..."] [extra watch.py flags]',
                  file=sys.stderr); sys.exit(2)
        url = args[0]
        intent = ""
        extra = args[1:]
        if "--intent" in extra:
            i = extra.index("--intent")
            intent = extra[i + 1] if i + 1 < len(extra) else ""
            extra = extra[:i] + extra[i + 2:]
        r = assimilate(url, intent=intent, extra=extra)
        print(json.dumps({k: v for k, v in r.items() if k != "stdout"}, indent=2))
        if r.get("stdout"):
            print("\n--- watch.py output (tail) ---\n" + r["stdout"])

    elif sub == "persona":
        if not args:
            print('usage: assimilate persona <video-url-or-path> --name "Mom" [watch flags]\n'
                  '  builds a Digital Double Dossier (looks+voice+mannerisms+personality) for '
                  'faithful recreation', file=sys.stderr); sys.exit(2)
        video = args[0]
        name = "Unknown"
        extra = args[1:]
        if "--name" in extra:
            i = extra.index("--name"); name = extra[i + 1] if i + 1 < len(extra) else name
            extra = extra[:i] + extra[i + 2:]
        r = persona(video, name=name, extra=extra)
        print(json.dumps(r, indent=2))

    elif sub == "listen":
        if not args:
            print('usage: assimilate listen <media> [--mode performance|transcript] [--model M]',
                  file=sys.stderr); sys.exit(2)
        media = args[0]
        mode = "performance"
        model = ""
        if "--mode" in args:
            i = args.index("--mode"); mode = args[i + 1] if i + 1 < len(args) else mode
        if "--model" in args:
            i = args.index("--model"); model = args[i + 1] if i + 1 < len(args) else ""
        r = gemini_listen(media, mode=mode, model=model)
        print(json.dumps({k: v for k, v in r.items() if k != "text"}, indent=2))
        if r.get("text"):
            print("\n--- gemini " + mode + " ---\n" + r["text"])

    elif sub in ("import-genie", "import"):
        r = import_genie()
        print(json.dumps(r, indent=2))

    elif sub == "digest":
        # the scheduler entry point: free scout+triage daily, budgeted Gemini-watch, daily brief.
        scout_only = "--scout-only" in args
        visual = "--no-visual" not in args     # SEE by default; the visual intel is the whole point
        smart = "--smart" in args
        budget = 2
        if "--budget" in args:
            i = args.index("--budget")
            try: budget = int(args[i + 1])
            except (IndexError, ValueError): pass
        r = digest(budget=budget, scout_only=scout_only, visual=visual, smart=smart)
        print(json.dumps(r, indent=2))

    elif sub == "run":
        do_watch = "--watch" in args
        mx = 0
        if "--max" in args:
            i = args.index("--max")
            try: mx = int(args[i + 1])
            except (IndexError, ValueError): pass
        r = run(do_watch=do_watch, max_videos=mx)
        print("\n" + r["note"])

    else:
        print(f"unknown assimilate subcommand: {sub}\n"
              "  targets | resolve <@handle> | scout [id] | filter \"<title>\" |\n"
              "  watch <url> | listen <media> [--mode performance|transcript] |\n"
              "  persona <video> --name \"X\" | import-genie | run [--watch] [--max N]",
              file=sys.stderr)
        sys.exit(2)

"""VERITY voice loop — route the user's setup/tray choices to a real speak (and, later, listen) pipeline.

Reads the mascot config + state files the setup popup / tray menu write, resolves
{speak-mode, readout-style, engine, voice, interactive}, and SPEAKS accordingly:

  speak mode : off | tldr (a short persona-styled summary) | full (read it all)
  style      : standard (warm) | lcars (terse computer) | aisha (Gen-Z) — shapes the TL;DR + picks a voice
  engine     : oss (Voicebox / on-device, free) | openai (realtime) | elevenlabs | hybrid (oss read-outs)
  voice      : per-style DEFAULT (warm female / British male / Black female) | uploaded | cloned

Engine routing, in order of preference and graceful fallback:
  elevenlabs -> ElevenLabs API (key from config/creds)        [premium]
  oss/hybrid -> Voicebox local API (:17493) if up             [free, on-device]
  (any)      -> OS speech floor (macOS `say -v`, with a per-style voice)   [zero-dep, always works]

Listen / interactive (STT) is a documented entry point (`listen()`) — wired to Voicebox Whisper when the
two-way loop is enabled; until then it reports what it needs (mic + Accessibility TCC) instead of pretending.
Pure stdlib. CLI: `verity voice say "<text>"`, `verity voice status`, `verity voice listen`.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time

# Pronunciation respellings for proper nouns TTS engines mangle. Extend per deployment.
_PRON = [
    (re.compile(r"\bJ\.?A\.?R\.?V\.?I\.?S\.?", re.I), "Jarvis"),   # J.A.R.V.I.S. -> "Jarvis", not spelled out
    (re.compile(r"\bavani\b", re.I), "Ah-Voh-nee"),
    (re.compile(r"\baisha\b", re.I), "Eye-EE-sha"),
    (re.compile(r"\blcars\b", re.I), "El Cars"),
]


def _fix_pron(text: str) -> str:
    for pat, repl in _PRON:
        text = pat.sub(repl, text)
    return text

_HOME = pathlib.Path.home()
_VOICES = _HOME / ".verity-harness" / "voices"            # per-style trained voice references live here
_CFG = _HOME / ".verity-harness" / "mascot.json"
_STYLE_FILES = ("~/.verity-harness/tts-style", "~/.openclaw/state/tts-style")
_MODE_FILE = _HOME / ".verity-harness" / "voice-mode"
# Spoken TL;DR runs LOCAL-FIRST: an OAuth-bridge shim that spawns a vendor CLI per call can be ~19s/call —
# unusable for live speech — so default to a fast local Ollama model (~1s). Point these at any
# OpenAI-compatible endpoint+model to trade speed for cloud quality:
#   FUTRON_SHIM_URL=<your /chat/completions endpoint>   FUTRON_TTS_MODEL=<your model id>
_SHIM = os.getenv("FUTRON_SHIM_URL", "http://127.0.0.1:11434/v1/chat/completions")
_TTS_MODEL = os.getenv("FUTRON_TTS_MODEL", "qwen2.5:3b-instruct")
_VOICEBOX = os.getenv("VOICEBOX_URL", "http://127.0.0.1:17493")
# ── Conversation BRAIN (provider-agnostic) ──────────────────────────────────────────────────────────
# VERITY's spoken replies + persona TL;DRs are written by WHATEVER LLM THE USER ALREADY RUNS — you wire it
# at install. We do NOT assume a multi-LLM rig, and we DON'T bundle a tiny persona model: a sub-1B model is
# too flat to carry a persona, so the user's OWN model writes the persona build + reply in the background.
# Resolution order (first match wins):
#   1. env:   VERITY_VOICE_BRAIN_URL / _MODEL  (OpenAI-compatible endpoint), or VERITY_VOICE_BRAIN_CMD
#             (a CLI that takes the prompt as its last arg and prints ONLY the reply — codex/claude/gemini)
#   2. file:  ~/.verity-harness/brain.json  ->  {"url": "...", "model": "...", "cmd": "..."}
#   3. default: local Ollama with WHATEVER model the user set via VERITY_BRAIN_FALLBACK_MODEL. If unset and
#             nothing is wired, the persona reply degrades gracefully (no separate writer) — wire your model.
# Examples a user might wire: their own OpenAI/Anthropic key+url, an Ollama/LM Studio model, or a local
# OAuth-bridge shim that exposes subscription models over an OpenAI-compatible port. See docs/BRAIN_SETUP.md.
_BRAIN_DEFAULT_URL = "http://127.0.0.1:11434/v1/chat/completions"   # local Ollama (only if a model is set)
_BRAIN_DEFAULT_MODEL = os.getenv("VERITY_BRAIN_FALLBACK_MODEL", "")   # NO bundled model — user wires their own


def _brain_cfg():
    """Resolve (url, model, cmd) for the conversation brain — env > brain.json > user's own local model."""
    url = os.getenv("VERITY_VOICE_BRAIN_URL", "")
    model = os.getenv("VERITY_VOICE_BRAIN_MODEL", "")
    cmd = os.getenv("VERITY_VOICE_BRAIN_CMD", "")
    if not (url or model or cmd):
        try:
            j = json.loads((_HOME / ".verity-harness" / "brain.json").read_text())
            url, model, cmd = j.get("url", ""), j.get("model", ""), j.get("cmd", "")
        except Exception:
            pass
    return (url or _BRAIN_DEFAULT_URL, model or _BRAIN_DEFAULT_MODEL, cmd)
# Per-style Kokoro preset voice (local neural TTS). Public repo: run a kokoro-onnx server (or the
# voxsona-server) and set KOKORO_URL. standard = af_heart (warm female); override via env.
_KOKORO_URL = os.getenv("KOKORO_URL", "http://127.0.0.1:9102/v1/tts")
STYLE_KOKORO_VOICE = {"standard": os.getenv("KOKORO_STANDARD_VOICE", "af_heart")}

# per-style DEFAULT voices. Real voices come from Voicebox/ElevenLabs; the OS-`say` floor maps to the
# closest built-in macOS voice so the per-style personality still comes through with zero deps.
# lcars → Zarvox: macOS's iconic robotic voice — instant, on-device, zero-latency, and on-theme for a
# terse starship computer. (Personalities that want a HUMAN OS voice use Samantha/Daniel.)
STYLE_OS_VOICE = {"standard": "Samantha", "lcars": "Zarvox", "aisha": "Samantha", "jarvis": "Daniel"}
STYLE_DESC = {"standard": "warm female", "lcars": "Federation Computer", "aisha": "Black female",
              "jarvis": "British male"}

_PERSONA = {
    "standard": "Re-voice this as a warm, conversational, emotive assistant — natural, a little expressive, "
                "no slang, no robotic flatness.",
    "lcars": "Re-voice this as a terse, emotionless starship AI computer (LCARS) — crisp "
             "status-report cadence, e.g. 'Acknowledged. Task complete.' No warmth, no slang.",
    "aisha": "Re-voice this with confident Gen-Z + AAVE swagger (Aisha from Solar Opposites) — cool, dry-"
             "witty, a little sassy, never corny.",
    "jarvis": "Re-voice this as J.A.R.V.I.S. — a refined, unflappable British AI butler. Polished, dry "
              "wit, impeccably composed; address the user as 'sir' when natural. No slang, never casual.",
}


def cfg() -> dict:
    """Resolve the live voice config from the files the setup popup / tray menu write."""
    c = {}
    try:
        c = json.loads(_CFG.read_text())
    except Exception:
        pass
    style = ""
    for p in _STYLE_FILES:
        try:
            style = pathlib.Path(os.path.expanduser(p)).read_text().strip().lower()
            if style:
                break
        except Exception:
            pass
    mode = ""
    try:
        mode = _MODE_FILE.read_text().strip().lower()
    except Exception:
        pass
    return {
        "speak": c.get("voice", "off"),                         # off | tldr | full
        "style": style or c.get("readout", "standard"),
        "engine": c.get("voiceengine", "oss"),                  # oss | openai | elevenlabs | hybrid
        "voicesrc": c.get("voicesrc", "default"),
        "voiceid": c.get("elvoiceid", ""),
        "apikey": c.get("apikey", ""),
        "interactive": (mode == "interactive") or (c.get("interactive") == "ptt"),
    }


def _get_cred(key: str) -> str:
    for f in (_HOME / ".openclaw/credentials/llm.env",):
        try:
            for line in f.read_text().splitlines():
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
    return ""


def _tldr(text: str, style: str) -> str:
    """Shorten to a spoken TL;DR in the chosen persona via the local shim; fall back to first 2 sentences."""
    import re
    import urllib.request
    sysp = (_PERSONA.get(style, _PERSONA["standard"])
            + " Output ONE or TWO spoken sentences, first person, no markdown/code/URLs. ENGLISH ONLY —"
            + " never any other language or script. Just the line.")
    body = json.dumps({"model": _TTS_MODEL,
                       "reasoning_effort": "none",   # no-op for qwen2.5; guards a reasoning-model override
                       "messages": [{"role": "system", "content": sysp},
                                    {"role": "user", "content": text[:4000]}],
                       "temperature": 0.7, "max_tokens": 200}).encode()
    # retry a few times (~1s each): the local model can intermittently return empty / non-English.
    # SHIP-SAFE: if the local LLM endpoint isn't reachable (fresh public box with no Ollama), the first
    # connection attempt fails fast and we drop straight to the first-2-sentences fallback — never hang.
    for _ in range(3):
        try:
            req = urllib.request.Request(_SHIM, data=body, headers={"Content-Type": "application/json"})
            d = json.loads(urllib.request.urlopen(req, timeout=8).read())
            out = (d.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
            if out and not re.search(r"[^\x00-\x7F]", out):
                return out
        except urllib.error.URLError:
            break   # no server / unreachable / timeout — don't hammer a box that has no local LLM
        except Exception:
            pass
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:2])[:400]


def _strip(text: str) -> str:
    import re
    bt = chr(96)
    text = re.sub(bt * 3 + r".*?" + bt * 3, " ", text, flags=re.DOTALL)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_#>`~|]", "", text)
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ── ElevenLabs budget guard ─────────────────────────────────────────────────────────────────────────
# AISHA's premium ElevenLabs voice is used SPARINGLY + RANDOMLY and hard-capped per month so it can never
# drain credits (paid cloud TTS can silently rack up cost). When the gate says no, the caller falls through to a
# FREE local voice — she still speaks, just not in the paid voice. Tunable:
#   VERITY_EL_MONTHLY_CAP  monthly character/credit cap (default 25000)
#   VERITY_EL_PROBABILITY  chance any given line uses the paid voice (default 0.25 = ~1 in 4)
_EL_USAGE = _HOME / ".verity-harness" / "elevenlabs-usage.json"
_EL_CAP = int(os.getenv("VERITY_EL_MONTHLY_CAP", "25000"))
_EL_PROB = float(os.getenv("VERITY_EL_PROBABILITY", "0.25"))


def _el_month() -> str:
    # stdlib only; avoid argless datetime.now() bans elsewhere — read the system clock via time.strftime
    return time.strftime("%Y-%m")


def _el_usage() -> dict:
    try:
        d = json.loads(_EL_USAGE.read_text())
        if d.get("month") == _el_month():
            return d
    except Exception:
        pass
    return {"month": _el_month(), "used": 0}


def _el_budget_ok(n_chars: int, force: bool = False) -> bool:
    """True if the paid ElevenLabs voice may speak this line: under the monthly cap AND (unless force) it
    wins the sparing random roll. force=True (e.g. an explicit `verity voice say`) skips the random gate
    but still respects the hard cap."""
    import random
    u = _el_usage()
    if u["used"] + max(0, n_chars) > _EL_CAP:
        return False                      # hard monthly cap — never exceed
    if not force and random.random() > _EL_PROB:
        return False                      # sparing/random: most lines use the free voice
    return True


def _el_record(n_chars: int) -> None:
    u = _el_usage()
    u["used"] += max(0, n_chars)
    try:
        _EL_USAGE.parent.mkdir(parents=True, exist_ok=True)
        _EL_USAGE.write_text(json.dumps(u))
    except Exception:
        pass


def _say_elevenlabs(text: str, voiceid: str, apikey: str) -> bool:
    import urllib.request
    key = apikey or _get_cred("ELEVENLABS_API_KEY")
    vid = voiceid or _get_cred("ELEVENLABS_VOICE_ID")
    if not key or not vid:
        return False
    # CLEAN settings — tuned for a natural-sounding clone. The API `speed` param adds a high-pitch
    # artifact, so we do NOT send it; pacing is slowed AFTER, via ffmpeg atempo (pitch-preserving).
    vs = {"stability": 0.45, "similarity_boost": 0.8}
    body = json.dumps({"text": text[:5000], "model_id": "eleven_turbo_v2_5", "voice_settings": vs}).encode()
    try:
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}", data=body,
                                     headers={"xi-api-key": key, "Content-Type": "application/json",
                                              "Accept": "audio/mpeg"})
        audio = urllib.request.urlopen(req, timeout=60).read()
        if len(audio) < 1000:
            return False
        _el_record(len(text))   # the paid API call succeeded — bank the spend against the monthly cap
        import tempfile
        f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        f.write(audio); f.close()
        playpath = f.name
        # Two independent knobs, both pitch-preserving where they should be:
        #   $VERITY_EL_PITCH (default 0.95) — LOWER her pitch (the clone renders high). <1 = deeper.
        #   $VERITY_EL_SPEED (default 0.9)  — slow the PACE. <1 = slower.
        # Implemented as asetrate (shifts pitch) + atempo (restores/sets tempo), so pitch and pace are
        # controlled separately with no chipmunk artifact.
        try: _pace = float(os.getenv("VERITY_EL_SPEED", "0.9"))
        except Exception: _pace = 0.9
        try: _pitch = float(os.getenv("VERITY_EL_PITCH", "0.95"))
        except Exception: _pitch = 0.95
        ff = shutil.which("ffmpeg")
        if ff and (_pitch < 0.99 or _pace < 0.99):
            sr = 24000
            tempo = max(0.5, min(2.0, _pace / max(_pitch, 0.1)))
            af = f"aresample={sr},asetrate={int(sr * _pitch)},aresample={sr},atempo={tempo:.4f}"
            out2 = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            subprocess.run([ff, "-y", "-i", f.name, "-filter:a", af, out2], capture_output=True, timeout=60)
            if os.path.exists(out2) and os.path.getsize(out2) > 1000:
                playpath = out2
        player = shutil.which("afplay") or shutil.which("play") or shutil.which("ffplay")
        if player:
            subprocess.run([player, playpath], timeout=300, capture_output=True)
        for _p in {f.name, playpath}:
            try: os.unlink(_p)
            except Exception: pass
        return True
    except Exception:
        return False


def _say_voicebox(text: str, style: str) -> bool:
    """Speak via a local Voicebox instance if its API is up. Best-effort; returns False to fall through."""
    import urllib.request
    try:
        # liveness check — cheap; if Voicebox isn't up, fall through to the OS floor.
        urllib.request.urlopen(_VOICEBOX, timeout=1)
    except Exception:
        return False
    # Voicebox's TTS endpoint/contract varies by version; without a confirmed schema we don't guess.
    # (Wired in a follow-up once the local API shape is pinned; for now the OS floor covers OSS.)
    return False


def _say_futron(text: str) -> bool:
    """Reuse an existing AVANI-voice CLI if present (futron-cli-speak → Kokoro/RVC AVANI voice).
    Preferred over the plain-`say` floor so we keep AVANI's actual voice, not a generic system one."""
    cli = shutil.which("futron-cli-speak") or os.path.expanduser("~/.openclaw/bin/futron-cli-speak")
    if not (os.path.exists(cli) or shutil.which("futron-cli-speak")):
        return False
    try:
        return subprocess.run([cli, text[:5000]], timeout=300).returncode == 0
    except Exception:
        return False


def _voice_ref(style: str):
    p = _VOICES / f"{style}.wav"
    return str(p) if p.exists() else None


def _say_clone(text: str, style: str) -> bool:
    """Speak in a TRAINED voice — futron-tts (Qwen3 zero-shot clone). Per-style ref wins; else a 'default'
    or 'avani' trained voice covers every style (so one trained AVANI voice voices all responses)."""
    ref = _voice_ref(style) or _voice_ref("default") or _voice_ref("avani")
    if not ref:
        return False
    tts = shutil.which("futron-tts") or os.path.expanduser("~/.openclaw/bin/futron-tts")
    if not (os.path.exists(tts) or shutil.which("futron-tts")):
        return False
    import tempfile
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    env = dict(os.environ, FUTRON_TTS_REF_AUDIO=ref)
    ref_txt = os.path.splitext(ref)[0] + ".txt"   # per-voice transcript — must match the ref audio
    if os.path.exists(ref_txt):
        env["FUTRON_TTS_REF_TEXT"] = ref_txt
    try:
        r = subprocess.run([tts, "generate", "--text", text[:2000], "--output", out],
                           env=env, timeout=300, capture_output=True)
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000:
            player = shutil.which("play") or shutil.which("afplay")
            if player:
                subprocess.run([player, out], timeout=300, capture_output=True)
            os.unlink(out)
            return True
    except Exception:
        pass
    try:
        os.unlink(out)
    except Exception:
        pass
    return False


def train(style: str, clip_path: str) -> dict:
    """Register a rights-clean clip as the voice for a style. Clones what YOU supply — sources nothing.
    Converts to 24k-mono WAV (ffmpeg) into ~/.verity-harness/voices/<style>.wav for the OSS clone path."""
    style = (style or "").strip().lower()
    src = os.path.expanduser(clip_path or "")
    if not style:
        return {"ok": False, "error": "need a style name (standard|lcars|aisha|avani|veri|…)"}
    if not os.path.exists(src):
        return {"ok": False, "error": f"clip not found: {src}"}
    _VOICES.mkdir(parents=True, exist_ok=True)
    dst = _VOICES / f"{style}.wav"
    try:
        ff = shutil.which("ffmpeg")
        if ff:
            subprocess.run([ff, "-y", "-i", src, "-ar", "24000", "-ac", "1", str(dst)],
                           capture_output=True, timeout=120)
        if not dst.exists() or dst.stat().st_size < 1000:
            shutil.copy(src, dst)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": dst.exists(), "style": style, "ref": str(dst),
            "note": "speak it: readout-style=" + style + " + engine=oss → the OSS path clones from this reference."}


def watch(interval: float = 5.0):
    """Daemon: watch ~/.verity-harness/voices/incoming/ for <style>.<ext> clips and auto-train each.
    Drop a rights-clean clip named by its style; it gets registered. Sources nothing — only processes drops."""
    inbox, done = _VOICES / "incoming", _VOICES / "trained"
    inbox.mkdir(parents=True, exist_ok=True)
    done.mkdir(parents=True, exist_ok=True)
    print(f"[voice-train] watching {inbox}\n  drop <style>.wav|mp3|m4a|flac  (style = standard|lcars|aisha|avani|veri)")
    while True:
        try:
            for f in sorted(inbox.iterdir()):
                if f.is_file() and f.suffix.lower() in (".wav", ".mp3", ".m4a", ".flac", ".ogg"):
                    print(f"[voice-train] {f.name} -> {train(f.stem, str(f))}")
                    try:
                        f.rename(done / f.name)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[voice-train] scan error: {e}")
        time.sleep(interval)


def _say_os(text: str, style: str) -> bool:
    """Zero-dep speech floor — macOS `say -v <per-style voice>` (or `espeak`/`spd-say` on Linux)."""
    say = shutil.which("say")
    if say:
        v = STYLE_OS_VOICE.get(style, "Samantha")
        try:
            subprocess.run([say, "-v", v, text[:5000]], timeout=300)
            return True
        except Exception:
            return False
    for tool in ("spd-say", "espeak"):
        p = shutil.which(tool)
        if p:
            try:
                subprocess.run([p, text[:5000]], timeout=300)
                return True
            except Exception:
                pass
    return False


def _piper_bin():
    b = os.environ.get("PIPER_BIN")
    if b and os.path.exists(b):
        return b
    for c in (os.path.expanduser("~/repos/voxsona/.venv/bin/piper"), shutil.which("piper")):
        if c and os.path.exists(c):
            return c
    return None


def _say_piper(text: str, style: str) -> bool:
    """Dedicated per-style Piper neural voice if ~/.verity-harness/voices/<style>.onnx exists — local,
    fast, free. e.g. lcars = the Federation Computer (Majel Barrett) voice. Ships by dropping a Piper
    <style>.onnx (+ .onnx.json) into the voices dir; install piper-tts (or set PIPER_BIN)."""
    model = _VOICES / f"{style}.onnx"
    pbin = _piper_bin()
    if not (model.exists() and pbin):
        return False
    import tempfile
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    try:
        subprocess.run([pbin, "-m", str(model), "-f", out], input=text[:5000].encode(),
                       capture_output=True, timeout=120)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            player = shutil.which("afplay") or shutil.which("play")
            if player:
                subprocess.run([player, out], capture_output=True, timeout=300)
            os.unlink(out)
            return True
    except Exception:
        pass
    try:
        os.unlink(out)
    except Exception:
        pass
    return False


def _say_kokoro(text: str, style: str) -> bool:
    """Per-style Kokoro preset voice (e.g. standard = af_heart) via a local kokoro-onnx server. Local,
    fast, free. Public repo: run a Kokoro server (or voxsona-server) and set KOKORO_URL."""
    import urllib.request
    voice = STYLE_KOKORO_VOICE.get(style)
    if not voice:
        return False
    import tempfile
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    try:
        body = json.dumps({"text": text[:5000], "voice": voice}).encode()
        req = urllib.request.Request(_KOKORO_URL, data=body, headers={"Content-Type": "application/json"})
        data = urllib.request.urlopen(req, timeout=60).read()
        if len(data) > 1000:
            with open(out, "wb") as f:
                f.write(data)
            player = shutil.which("afplay") or shutil.which("play")
            if player:
                subprocess.run([player, out], capture_output=True, timeout=300)
            os.unlink(out)
            return True
    except Exception:
        pass
    try:
        os.unlink(out)
    except Exception:
        pass
    return False


_VOXSONA_SERVER = os.getenv("VOXSONA_SERVER", "http://127.0.0.1:9106")


def _say_voxsona_overlay(text: str, style: str) -> bool:
    """FREE local cloned voice via voxsona-server /tts (KokoClone zero-shot, ~3s) — synthesizes the text
    DIRECTLY in the ~/.verity-harness/voices/<style>.wav cloned timbre. On-device, no cloud cost.
    NOTE: deliberately uses /tts (text->clone), NOT /convert (the say-overlay): converting macOS `say`
    inherits the base voice's white American accent/prosody + artifacts, so the clone sounded wrong."""
    import tempfile, urllib.request
    ref = _VOICES / f"{style}.wav"
    if not ref.exists():
        return False
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    try:
        body = json.dumps({"text": text[:4000], "ref": str(ref), "lang": "en"}).encode()
        req = urllib.request.Request(_VOXSONA_SERVER + "/tts", data=body,
                                     headers={"Content-Type": "application/json"})
        data = urllib.request.urlopen(req, timeout=120).read()
        if len(data) > 1000:
            with open(out, "wb") as f:
                f.write(data)
            player = shutil.which("afplay") or shutil.which("play")
            if player:
                subprocess.run([player, out], capture_output=True, timeout=300)
            return True
    except Exception:
        pass
    finally:
        try: os.unlink(out)
        except Exception: pass
    return False


def say(text: str, verbose: bool = False, force: bool = False, realtime: bool = False) -> dict:
    """Speak `text` per the resolved config. force=True speaks it IN FULL regardless of the speak-mode
    setting. realtime=True prefers the FAST cloud voice (ElevenLabs) over the slower local clone — for
    live conversation, where a ~0.6s reply matters and the local clone (~3s, more under CPU load) lags."""
    c = cfg()
    if c["speak"] == "off" and not force:
        return {"spoke": False, "reason": "speak mode is OFF"}
    spoken = _strip(text)
    if c["speak"] == "tldr" and not force:
        spoken = _tldr(spoken, c["style"])
    if len(spoken) < 2:
        return {"spoke": False, "reason": "nothing to say"}
    spoken = _fix_pron(spoken)   # respell mangled proper nouns before any engine speaks it
    eng = c["engine"]
    style = c["style"]
    # Per-style ElevenLabs voice: the `aisha` personality has its own cloned voice id (fast cloud Aisha,
    # ~0.6s vs ~12s for the local neural clone). Other styles use the configured/default voice id.
    el_vid = c["voiceid"]
    if style == "aisha":
        el_vid = _get_cred("ELEVENLABS_AISHA_VOICE_ID") or el_vid
    used = None
    # Dedicated per-style Piper neural voice wins when present (e.g. lcars = Federation Computer) —
    # it IS that personality's voice, regardless of the configured engine.
    if _say_piper(spoken, style):
        used = "piper:" + style
    # Per-style Kokoro preset voice (e.g. standard = af_heart) — local neural, fast.
    if not used and _say_kokoro(spoken, style):
        used = "kokoro:" + style
    # AISHA's clean, exactly-her voice is ElevenLabs — but used SPARINGLY + RANDOMLY under a hard monthly
    # cap (never drain credits). When the budget gate says no, we skip EL and fall through to the FREE
    # local voice below — she still speaks, just not in the paid voice. Only an explicit engine=elevenlabs
    # config opts into the paid voice every time (skips the random roll, still respects the cap). The
    # conversation loop passes force=True only to speak-when-muted — that must NOT bypass the sparing roll.
    _el_intentional = (eng == "elevenlabs")
    if not used and (realtime or eng == "elevenlabs" or (style == "aisha" and el_vid)) \
            and _el_budget_ok(len(spoken), force=_el_intentional) \
            and _say_elevenlabs(spoken, el_vid, c["apikey"]):
        used = "elevenlabs:" + style
    # FREE local cloned voice — voxsona-server /tts (KokoClone text→clone, ~3s). A solid free path for the
    # aisha free path ("sounds just like AISHA"). Default when NOT on the paid elevenlabs engine; saves
    # cloud cost, fully on-device + open-source. (NOT the say-overlay /convert — that sounded white/distorted.)
    if not used and _say_voxsona_overlay(spoken, style):
        used = "voxsona-tts:" + style
    if not used and eng in ("oss", "hybrid") and _say_voicebox(spoken, style):
        used = "voicebox"
    if not used and eng in ("oss", "hybrid") and _say_clone(spoken, c["style"]):  # TRAINED per-style voice
        used = "clone:" + c["style"]
    if not used and _say_futron(spoken):          # existing AVANI voice (Kokoro/RVC) — keep her voice, not generic
        used = "futron-cli (AVANI)"
    if not used and _say_os(spoken, c["style"]):  # zero-dep floor only when no AVANI voice path exists
        used = "os-floor"
    if verbose:
        print(f"[voice] engine={eng}->{used} style={c['style']} mode={c['speak']}\n  «{spoken}»")
    return {"spoke": bool(used), "engine": used, "style": c["style"], "text": spoken}


def _mic_device():
    """Resolve the input device for sox: $VERITY_MIC, else ~/.verity-harness/mic file, else system default.
    Critical on rigs where the default input is a virtual audio device (e.g. DJ/DAW software), not the mic."""
    m = os.getenv("VERITY_MIC")
    if m:
        return m.strip()
    f = _HOME / ".verity-harness" / "mic"
    if f.exists():
        try:
            return f.read_text(encoding="utf-8").strip() or None
        except Exception:
            pass
    return None


def _rec_env():
    env = dict(os.environ)
    mic = _mic_device()
    if mic:
        env["AUDIODEV"] = mic
    return env


def _ptt_key_name() -> str:
    """The push-to-talk key, configurable via $VERITY_PTT_KEY or ~/.verity-harness/ptt-key (default
    'shift_r' = Right-Shift). Accepts a pynput special-key name (shift_r, shift_l, ctrl_r, cmd_r, alt_r,
    space, f13, caps_lock, …) OR a single character (e.g. 'z')."""
    name = os.getenv("VERITY_PTT_KEY", "").strip()
    if not name:
        f = _HOME / ".verity-harness" / "ptt-key"
        if f.exists():
            try:
                name = f.read_text(encoding="utf-8").strip()
            except Exception:
                name = ""
    if not name:   # the setup popup writes the picked key into mascot.json
        try:
            name = (json.loads(_CFG.read_text()).get("pttkey") or "").strip()
        except Exception:
            name = ""
    return name or "shift_r"


def _resolve_ptt_key(name: str):
    """Map a key name to a pynput key object. Returns (key_obj, display_name)."""
    from pynput import keyboard
    if hasattr(keyboard.Key, name):
        return getattr(keyboard.Key, name), name
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name), f"'{name}'"
    return keyboard.Key.shift_r, "shift_r"


def _record_turn(max_s: int = 20):
    """Hands-free: record ONE spoken turn, silence-bounded (sox `rec`). Returns wav path or None."""
    rec = shutil.which("rec")
    if not rec:
        return None
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    try:
        # start when speech begins; stop after ~1.5s trailing silence; hard cap max_s
        # start on quiet speech (1% / 0.1s — was 2% and missed soft voices); stop after 1.5s silence
        subprocess.run([rec, "-q", "-c", "1", "-r", "16000", out, "trim", "0", str(max_s),
                        "silence", "1", "0.1", "1%", "1", "1.5", "1.5%"],
                       capture_output=True, timeout=max_s + 10, env=_rec_env())
        if os.path.exists(out) and os.path.getsize(out) > 4000:
            return out
    except Exception:
        pass
    try: os.unlink(out)
    except Exception: pass
    return None


def _record_until_enter():
    """Record from the DEFAULT mic until ENTER is pressed again — the proven futron-avani-voice-chat
    method. Default device (NO AUDIODEV — a friendly name like 'MacBook Pro Microphone' makes sox fail
    with 'no default audio device') + no silence detection = bulletproof. Returns wav path or None."""
    rec = shutil.which("rec")
    if not rec:
        return None
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    try:
        # stdin=DEVNULL is CRITICAL: without it, sox `rec` shares the terminal stdin and consumes the
        # ENTER keystrokes meant for the input() prompts below — both input()s then return instantly,
        # rec is killed before capturing audio, the file is <4000 bytes, and the loop spins on
        # "didn't catch that" forever. Detaching rec's stdin fixes it.
        proc = subprocess.Popen([rec, "-q", out, "rate", "16k", "channels", "1"],
                                stdin=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        try:
            input("  🎤 recording… press ENTER to send: ")
        except EOFError:
            pass
        try: proc.terminate(); proc.wait(timeout=2)
        except Exception: pass
        if os.path.exists(out) and os.path.getsize(out) > 4000:
            return out
    except Exception:
        pass
    try: os.unlink(out)
    except Exception: pass
    return None


def _record_turn_ptt(max_s: int = 30):
    """Push-to-talk: record ONLY while the PTT key (Right-Shift) is held; send on release. Zero false
    triggers — best for noisy environments. Needs pynput + macOS Input Monitoring grant (prompted once).
    Falls back to hands-free if pynput is unavailable."""
    rec = shutil.which("rec")
    if not rec:
        return None
    try:
        from pynput import keyboard
    except Exception:
        return _record_turn(max_s)
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    target, _ = _resolve_ptt_key(_ptt_key_name())
    st = {"proc": None}
    env = _rec_env()
    def on_press(k):
        if k == target and st["proc"] is None:
            st["proc"] = subprocess.Popen([rec, "-q", "-c", "1", "-r", "16000", out, "trim", "0", str(max_s)],
                                          env=env, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    def on_release(k):
        if k == target and st["proc"] is not None:
            try: st["proc"].terminate()
            except Exception: pass
            return False   # release -> stop the listener, send the turn
    try:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as L:
            L.join()
        if st["proc"]:
            try: st["proc"].wait(timeout=2)
            except Exception: pass
    except Exception:
        return _record_turn(max_s)   # pynput blocked (no Input Monitoring grant) -> fall back
    if os.path.exists(out) and os.path.getsize(out) > 4000:
        return out
    try: os.unlink(out)
    except Exception: pass
    return None


def _transcribe(wav: str) -> str:
    """Whisper STT -> text. Model via $VERITY_STT_MODEL (default tiny.en, fast)."""
    import glob
    whisper = shutil.which("whisper") or os.path.expanduser("~/Library/Python/3.14/bin/whisper")
    if not os.path.exists(whisper) and not shutil.which("whisper"):
        return ""
    d = tempfile.mkdtemp()
    try:
        subprocess.run([whisper, wav, "--model", os.getenv("VERITY_STT_MODEL", "tiny.en"),
                        "--language", "en", "--fp16", "False", "--output_format", "txt", "--output_dir", d],
                       capture_output=True, timeout=120)
        for f in glob.glob(d + "/*.txt"):
            return pathlib.Path(f).read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def _brain_label() -> str:
    """Human-readable name of the active conversation brain (for the live banner)."""
    url, model, cmd = _brain_cfg()
    if cmd:
        return f"cmd:{cmd.split()[0]}"
    if not model:
        return "unset (wire your LLM → ~/.verity-harness/brain.json)"
    host = "shim" if ":11445" in url else ("local" if ":11434" in url else url)
    return f"{model}@{host}"


def _brain_messages(user_text: str, style: str, history=None):
    """Build the chat messages: persona system prompt + recent turns + this turn."""
    sysp = (_PERSONA.get(style, _PERSONA["standard"]) + " You are in a LIVE voice conversation — reply in "
            "1-3 spoken sentences, natural and conversational, no markdown/lists/code/URLs. Stay fully in "
            "character. ENGLISH ONLY.")
    msgs = [{"role": "system", "content": sysp}]
    for turn in (history or [])[-8:]:          # last ~4 exchanges keep it contextual without bloating
        msgs.append(turn)
    msgs.append({"role": "user", "content": user_text[:2000]})
    return msgs


def _brain_via_cmd(user_text: str, style: str, history=None) -> str:
    """Route the turn through a CLI brain (Codex / Claude Code / Gemini / futron-chatgpt-plus).
    The command gets the FULL spoken prompt (persona + short history + user) as its last arg and must
    print ONLY the reply on stdout. Lets the voice loop talk to whatever LLM the user already drives."""
    parts = _brain_cfg()[2].split()
    sysp = (_PERSONA.get(style, _PERSONA["standard"]) + " Reply in 1-3 spoken sentences, in character, "
            "no markdown/code/URLs, ENGLISH ONLY.")
    convo = "\n".join(f"{t['role']}: {t['content']}" for t in (history or [])[-6:])
    prompt = (sysp + ("\n\n" + convo if convo else "") + f"\nuser: {user_text[:2000]}\nassistant:")
    try:
        r = subprocess.run(parts + [prompt], capture_output=True, text=True, timeout=120)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _persona_reply(user_text: str, style: str, history=None) -> str:
    """Conversational reply IN the active persona, from the USER'S OWN LLM.
    Routing: VERITY_VOICE_BRAIN_CMD (CLI) → configured URL/MODEL (brain.json / env) → optional local model.
    The user wires their own LLM; if nothing is configured the reply degrades gracefully (returns "")."""
    import urllib.request
    b_url, b_model, b_cmd = _brain_cfg()
    if b_cmd:
        out = _brain_via_cmd(user_text, style, history)
        if out:
            return out
    msgs = _brain_messages(user_text, style, history)
    # the user's configured LLM, then an optional local model (only if one is set). Skip tiers with no model.
    for url, model, tmo in ((b_url, b_model, 90), (_BRAIN_DEFAULT_URL, _BRAIN_DEFAULT_MODEL, 30)):
        if not model:
            continue
        body = json.dumps({"model": model, "reasoning_effort": "none", "messages": msgs,
                           "temperature": 0.8, "max_tokens": 220}).encode()
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            d = json.loads(urllib.request.urlopen(req, timeout=tmo).read())
            out = (d.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
            if out:
                return out
        except Exception:
            continue   # primary unreachable → fall through to the local fast model
    return ""


def listen(ptt: bool = False, vad: bool = False) -> dict:
    """LIVE two-way voice loop: mic -> Whisper STT -> persona LLM -> say() (in the persona's voice).
    Modes (the press-ENTER default is the voice-os 'run.sh' pattern — 100% reliable, mic-only):
      DEFAULT  press ENTER, talk, pause to send — needs ONLY the Microphone grant. No Input Monitoring.
      ptt=True hold the PTT key (Right-Shift) ANYWHERE — needs Input Monitoring (fragile; only if granted).
      vad=True hands-free, voice-activated.
    Say 'goodbye'/'q' or Ctrl-C to stop. Requires sox `rec`, whisper, an LLM at $FUTRON_SHIM_URL.
    Mic via $VERITY_MIC or ~/.verity-harness/mic. Public-repo reproducible."""
    c = cfg()
    style = c["style"]
    if not shutil.which("rec"):
        return {"ready": False, "needs": ["sox for mic capture: brew install sox"]}
    if not (shutil.which("whisper") or os.path.exists(os.path.expanduser("~/Library/Python/3.14/bin/whisper"))):
        return {"ready": False, "needs": ["whisper STT: pip install openai-whisper"]}
    enter = not (ptt or vad)
    mode = ("press-ENTER to talk (reliable, mic-only)" if enter
            else (f"hold {_ptt_key_name()} (needs Input Monitoring)" if ptt else "hands-free (VAD)"))
    print(f"[verity] LIVE voice — persona={style} ({STYLE_DESC.get(style,'?')}) · brain={_brain_label()} · "
          f"mode: {mode}. Mic: {_mic_device() or 'system default'}. (Ctrl-C to exit)", flush=True)
    # Probe the mic once so the macOS Microphone prompt fires now (the only permission ENTER-mode needs).
    try:
        _r = shutil.which("rec")
        if _r:
            _p = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            print("  [requesting Microphone access — click Allow if macOS prompts]", flush=True)
            subprocess.run([_r, "-q", "-c", "1", "-r", "16000", _p, "trim", "0", "0.3"],
                           capture_output=True, timeout=10, env=_rec_env())
            try: os.unlink(_p)
            except Exception: pass
    except Exception:
        pass
    say("I'm listening.", force=True)
    turns = 0
    history = []   # rolling [{role,content}] so the brain holds the thread of the conversation
    try:
        while True:
            if enter:
                try:
                    cmd = input("\n  ▶ press ENTER to START talking ('q' to quit): ")
                except EOFError:
                    break
                if cmd.strip().lower() in ("q", "quit", "exit", "goodbye"):
                    say("Aight, catch you later.", force=True); break
                wav = _record_until_enter()   # records until you press ENTER again (proven method)
            elif ptt:
                wav = _record_turn_ptt()
            else:   # hands-free (VAD): settle first so we don't catch the tail of our own reply
                time.sleep(0.4)
                print("  …listening — just talk (pause to send)…", flush=True)
                wav = _record_turn()
            if not wav:
                print("  (didn't catch that — try again)", flush=True); continue
            user = _transcribe(wav)
            try: os.unlink(wav)
            except Exception: pass
            if not user or len(user) < 2:
                print("  (silence — try again)", flush=True); continue
            print(f"  you: {user}", flush=True)
            if re.search(r"\b(goodbye|good bye|stop listening|that'?s all|end conversation)\b", user, re.I):
                say("Aight, catch you later.", force=True); break
            reply = _persona_reply(user, style, history) or "Say that again?"
            print(f"  {style}: {reply}", flush=True)
            history.append({"role": "user", "content": user})
            history.append({"role": "assistant", "content": reply})
            del history[:-12]                        # keep the last ~6 exchanges in context
            say(reply, force=True, realtime=True)   # ALWAYS speak, FAST cloud voice (ElevenLabs ~0.6s)
            turns += 1
    except KeyboardInterrupt:
        print("\n[verity] live voice ended.", flush=True)
    return {"ready": True, "ended": True, "turns": turns, "persona": style}


def _paste_into_focused(text: str, submit: bool = False, app: str = None) -> bool:
    """Type `text` into the focused app via CLIPBOARD PASTE (robust for long / unicode text vs char-by-char
    keystroke). If `app` is given, bring it to the front first. submit=True presses Return after.
    Needs macOS Accessibility for the terminal/osascript (System Events keystroke)."""
    try:
        if app:
            subprocess.run(["osascript", "-e", f'tell application "{app}" to activate'],
                           capture_output=True, timeout=10)
            time.sleep(0.4)
        p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        p.communicate(text.encode("utf-8"))
        r = subprocess.run(["osascript", "-e",
                            'tell application "System Events" to keystroke "v" using command down'],
                           capture_output=True, timeout=10)
        if submit:
            time.sleep(0.25)
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 36'],
                           capture_output=True, timeout=10)   # key code 36 = Return
        return r.returncode == 0
    except Exception:
        return False


def dictate(ptt: bool = False, vad: bool = False, submit: bool = False, app: str = None) -> dict:
    """VOICE INPUT bridge — you speak, your words are TYPED into the focused app (your real assistant's
    prompt box). This makes voice an I/O layer over WHATEVER agent you already run — Claude Code, Codex, a
    chat box — instead of a separate throwaway chatbot. Pair it with the persona-voiced output (the
    auto-speak TL;DR of the agent's reply) and you have a full two-way voice loop with your REAL assistant,
    which keeps all its context, memory, and tools (its 'hands').
    INTEGRATED so users don't have to wire a 3rd-party dictation app — but they still CAN (e.g. Wispr Flow):
    just don't run this, and dictate with whatever you prefer.
    Modes: default press-ENTER (reliable, terminal-focused) — pair with --app to paste into another app;
           --ptt hold-key anywhere (seamless, needs Input Monitoring); --vad hands-free.
    --submit presses Return after pasting. Needs macOS Accessibility granted to the terminal."""
    if not shutil.which("rec"):
        return {"ready": False, "needs": ["sox for mic capture: brew install sox"]}
    if not (shutil.which("whisper") or os.path.exists(os.path.expanduser("~/Library/Python/3.14/bin/whisper"))):
        return {"ready": False, "needs": ["whisper STT: pip install openai-whisper"]}
    mode = "press-ENTER" if not (ptt or vad) else ("hold-key PTT (needs Input Monitoring)" if ptt else "hands-free VAD")
    tgt = f"app '{app}'" if app else "the focused app"
    print(f"[verity] VOICE DICTATE → types your speech into {tgt} · mode: {mode}"
          f"{' · auto-submit' if submit else ''}. (Ctrl-C to stop)", flush=True)
    n = 0
    try:
        while True:
            if ptt:
                wav = _record_turn_ptt()
            elif vad:
                time.sleep(0.3)
                print("  …listening — just talk (pause to send)…", flush=True)
                wav = _record_turn()
            else:
                try:
                    cmd = input("\n  ▶ press ENTER, speak, ENTER to type ('q' quits): ")
                except EOFError:
                    break
                if cmd.strip().lower() in ("q", "quit", "exit"):
                    break
                wav = _record_until_enter()
            if not wav:
                print("  (didn't catch that — try again)", flush=True); continue
            text = _transcribe(wav)
            try: os.unlink(wav)
            except Exception: pass
            if not text or len(text) < 2:
                print("  (silence — try again)", flush=True); continue
            ok = _paste_into_focused(text, submit=submit, app=app)
            print(f"  {'typed' if ok else 'FAILED to type (grant Accessibility?)'}: {text}", flush=True)
            n += 1
    except KeyboardInterrupt:
        print("\n[verity] dictate ended.", flush=True)
    return {"ok": True, "typed": n}


def status() -> str:
    c = cfg()
    floor = "say" if shutil.which("say") else ("espeak/spd-say" if (shutil.which("espeak") or shutil.which("spd-say")) else "NONE")
    return (
        "VERITY voice loop — resolved config:\n"
        f"  speak mode : {c['speak']}\n"
        f"  readout    : {c['style']}  ({STYLE_DESC.get(c['style'],'?')} default voice)\n"
        f"  engine     : {c['engine']}\n"
        f"  voice src  : {c['voicesrc']}" + (f"  voice-id={c['voiceid']}" if c['voiceid'] else "") + "\n"
        f"  interactive: {'on' if c['interactive'] else 'off'}  ·  conversation brain: {_brain_label()}\n"
        f"  OS floor   : {floor}\n"
        "  say:  verity voice say \"<text>\"   ·   listen:  verity voice listen  (press ENTER, talk, ENTER)"
    )

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
import shutil
import subprocess

_HOME = pathlib.Path.home()
_CFG = _HOME / ".verity-harness" / "mascot.json"
_STYLE_FILES = ("~/.verity-harness/tts-style", "~/.openclaw/state/tts-style")
_MODE_FILE = _HOME / ".verity-harness" / "voice-mode"
_SHIM = os.getenv("FUTRON_SHIM_URL", "http://127.0.0.1:11445/v1/chat/completions")
_VOICEBOX = os.getenv("VOICEBOX_URL", "http://127.0.0.1:17493")

# per-style DEFAULT voices. Real voices come from Voicebox/ElevenLabs; the OS-`say` floor maps to the
# closest built-in macOS voice so the per-style personality still comes through with zero deps.
STYLE_OS_VOICE = {"standard": "Samantha", "lcars": "Daniel", "aisha": "Samantha"}
STYLE_DESC = {"standard": "warm female", "lcars": "British male", "aisha": "Black female"}

_PERSONA = {
    "standard": "Re-voice this as a warm, conversational, emotive assistant — natural, a little expressive, "
                "no slang, no robotic flatness.",
    "lcars": "Re-voice this as a terse, emotionless starship AI computer (LCARS / J.A.R.V.I.S.) — crisp "
             "status-report cadence, e.g. 'Acknowledged. Task complete.' No warmth, no slang.",
    "aisha": "Re-voice this with confident Gen-Z + AAVE swagger (Aisha from Solar Opposites) — cool, dry-"
             "witty, a little sassy, never corny.",
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
            + " Output ONE or TWO spoken sentences, first person, no markdown/code/URLs. Just the line.")
    body = json.dumps({"messages": [{"role": "system", "content": sysp},
                                    {"role": "user", "content": text[:4000]}],
                       "temperature": 0.7, "max_tokens": 160}).encode()
    try:
        req = urllib.request.Request(_SHIM, data=body, headers={"Content-Type": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=30).read())
        out = (d.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        if out:
            return out
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


def _say_elevenlabs(text: str, voiceid: str, apikey: str) -> bool:
    import urllib.request
    key = apikey or _get_cred("ELEVENLABS_API_KEY")
    vid = voiceid or _get_cred("ELEVENLABS_VOICE_ID")
    if not key or not vid:
        return False
    body = json.dumps({"text": text[:5000], "model_id": "eleven_turbo_v2_5",
                       "voice_settings": {"stability": 0.45, "similarity_boost": 0.8}}).encode()
    try:
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}", data=body,
                                     headers={"xi-api-key": key, "Content-Type": "application/json",
                                              "Accept": "audio/mpeg"})
        audio = urllib.request.urlopen(req, timeout=60).read()
        if len(audio) < 1000:
            return False
        import tempfile
        f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        f.write(audio); f.close()
        player = shutil.which("play") or shutil.which("afplay") or shutil.which("ffplay")
        if player:
            subprocess.run([player, f.name], timeout=300, capture_output=True)
        os.unlink(f.name)
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


def say(text: str, verbose: bool = False) -> dict:
    """Speak `text` per the resolved config. Returns what happened (engine used, spoken text)."""
    c = cfg()
    if c["speak"] == "off":
        return {"spoke": False, "reason": "speak mode is OFF"}
    spoken = _strip(text)
    if c["speak"] == "tldr":
        spoken = _tldr(spoken, c["style"])
    if len(spoken) < 2:
        return {"spoke": False, "reason": "nothing to say"}
    eng = c["engine"]
    used = None
    if eng == "elevenlabs" and _say_elevenlabs(spoken, c["voiceid"], c["apikey"]):
        used = "elevenlabs"
    elif eng in ("oss", "hybrid") and _say_voicebox(spoken, c["style"]):
        used = "voicebox"
    if not used and _say_futron(spoken):          # existing AVANI voice (Kokoro/RVC) — keep her voice, not generic
        used = "futron-cli (AVANI)"
    if not used and _say_os(spoken, c["style"]):  # zero-dep floor only when no AVANI voice path exists
        used = "os-floor"
    if verbose:
        print(f"[voice] engine={eng}->{used} style={c['style']} mode={c['speak']}\n  «{spoken}»")
    return {"spoke": bool(used), "engine": used, "style": c["style"], "text": spoken}


def listen() -> dict:
    """Two-way interactive (STT) entry point. Not yet wired — reports what it needs instead of faking it."""
    c = cfg()
    return {
        "ready": False,
        "interactive_selected": c["interactive"],
        "needs": ["a running STT engine (Voicebox Whisper or a local whisper)",
                  "microphone + Accessibility TCC grant (the setup/agent-desktop can request these)",
                  "the listen→LLM→say wiring (next build)"],
        "note": "Interactive talk-back is selected but the listen loop isn't built yet. Use `verity desktop` "
                "to grant mic/Accessibility, then this will capture speech → your LLM → say().",
    }


def status() -> str:
    c = cfg()
    floor = "say" if shutil.which("say") else ("espeak/spd-say" if (shutil.which("espeak") or shutil.which("spd-say")) else "NONE")
    return (
        "VERITY voice loop — resolved config:\n"
        f"  speak mode : {c['speak']}\n"
        f"  readout    : {c['style']}  ({STYLE_DESC.get(c['style'],'?')} default voice)\n"
        f"  engine     : {c['engine']}\n"
        f"  voice src  : {c['voicesrc']}" + (f"  voice-id={c['voiceid']}" if c['voiceid'] else "") + "\n"
        f"  interactive: {'on' if c['interactive'] else 'off'} (listen loop: not built yet)\n"
        f"  OS floor   : {floor}\n"
        "  say:  verity voice say \"<text>\"   ·   listen:  verity voice listen"
    )

#!/usr/bin/env python3
"""verity video — transcribe/analyse a video with NO captions required.

This is a first-class VERITY capability (not an optional add-on): an agent should NEVER skip a video just
because it lacks captions (RULE 7 — never "can't"). Gemini is MULTIMODAL — give it a public YouTube URL and
it WATCHES the video (visuals + audio), so it captures on-screen UI, menus, code, and settings that
caption/audio-only tools miss. Perfect for tutorials/workflow walkthroughs.

Zero pip deps — pure stdlib over Gemini's REST API. Get a FREE key at
https://aistudio.google.com/app/apikey (the free -flash tier is plenty for transcription).

Key resolution (first found): env GEMINI_API_KEY → GOOGLE_API_KEY → a Gemini tier key in
~/.verity-harness/verity.env (any LLM_*_API_KEY whose matching LLM_*_URL points at generativelanguage).

CLI:  python3 -m verity video <youtube_url> [--model gemini-2.5-flash] [--summary]
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time
import urllib.request

_GEMINI_REST = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
_ENV_FILE = pathlib.Path(os.path.expanduser("~/.verity-harness/verity.env"))


def _gemini_key() -> str:
    """Find a Gemini API key without hardcoding one (env first, then a Gemini tier in verity.env)."""
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "VERITY_GEMINI_KEY"):
        v = os.environ.get(name)
        if v:
            return v.strip()
    # scan verity.env for a key whose paired URL points at Google's API
    try:
        kv = {}
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, val = line.split("=", 1)
                kv[k.strip()] = val.strip().strip('"').strip("'")
        for prefix in ("LLM_VERIFIER", "LLM_TIER1", "LLM_TIER2"):
            url = kv.get(f"{prefix}_URL", "")
            key = kv.get(f"{prefix}_API_KEY", "")
            if "generativelanguage" in url and key and key != "not-used":
                return key
        for k, v in kv.items():
            if "GEMINI" in k and v and v != "not-used":
                return v
    except Exception:
        pass
    return ""


def transcribe(url: str, model: str = "gemini-2.5-flash", summary: bool = False, key: str = "") -> str:
    """Return a verbatim transcript (or a structured summary) of a public video via Gemini multimodal.
    Raises RuntimeError with a clear, actionable message on failure — never returns a silent empty."""
    key = key or _gemini_key()
    if not key:
        raise RuntimeError(
            "no Gemini API key found. Set GEMINI_API_KEY (free key: https://aistudio.google.com/app/apikey) "
            "or add a Gemini tier to ~/.verity-harness/verity.env.")
    if summary:
        instr = ("Watch this video and produce a STRUCTURED brief: 1) one-line thesis, 2) the key points / "
                 "steps in order, 3) any concrete commands/tools/settings shown on screen, 4) takeaways. "
                 "Use the VISUALS (on-screen UI, code, menus), not just the audio.")
    else:
        instr = ("Transcribe this video VERBATIM. Watch the visuals too — include on-screen text, code, UI "
                 "labels, and menu/settings actions where they matter. Plain text, no timestamps.")
    # MEDIA_RESOLUTION_LOW samples the video at fewer tokens/frame — required for LONG videos (a 2-hour talk
    # at default resolution blows past the 1M-token window). For very long videos we drop to fps=1 too.
    def _post(media_res, fps=None):
        fdata = {"file_uri": url}
        if fps is not None:
            fdata["video_metadata"] = {"fps": fps}
        b = json.dumps({"contents": [{"parts": [{"text": instr}, {"file_data": fdata}]}],
                        "generationConfig": {"mediaResolution": media_res}}).encode()
        r = urllib.request.Request(_GEMINI_REST.format(model=model, key=key), data=b,
                                   headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(r, timeout=900).read())

    d = None
    last_err = ""
    # escalating attempts: LOW res → LOW res + fps 1 → LOW res + fps 0.5 (fits longer videos each step)
    for media_res, fps in (("MEDIA_RESOLUTION_LOW", None), ("MEDIA_RESOLUTION_LOW", 1), ("MEDIA_RESOLUTION_LOW", 0.5)):
        try:
            d = _post(media_res, fps)
            break
        except urllib.error.HTTPError as e:
            last_err = e.read().decode(errors="ignore")[:300]
            if "exceeds the maximum number of tokens" in last_err:
                time.sleep(1)
                continue            # too long → next step samples fewer frames
            raise RuntimeError(f"Gemini API error {e.code}: {last_err}") from e
        except urllib.error.URLError as e:
            last_err = str(e); time.sleep(4); continue
    if d is None:
        raise RuntimeError(f"video too long even at lowest sampling, or network failed: {last_err}")
    if isinstance(d, list):
        d = d[0] if d else {}
    if "error" in d:
        raise RuntimeError(f"Gemini: {d['error'].get('message', d['error'])}")
    try:
        parts = d["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError):
        text = ""
    if not text:
        raise RuntimeError(f"Gemini returned no text (response: {json.dumps(d)[:200]}). "
                           "The video may be private/age-gated/too long for this model.")
    return text


def _vid_id(s: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", s)
    return m.group(1) if m else s

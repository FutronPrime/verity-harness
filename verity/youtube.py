#!/usr/bin/env python3
"""Resilient, reusable YouTube access built on the maintained yt-dlp engine.

The cascade is intentionally shared by transcript, visual-analysis, and media
playback callers.  YouTube changes frequently; a single hard-coded invocation
silently turns every downstream feature brittle.

Routes, in order:
1. anonymous yt-dlp (least privilege, no account state)
2. optional browser-cookie routes using ``web_safari`` (Chrome, then Safari)

Cookie routes are opt-in through ``allow_browser_cookies=True`` or the portable
``VERITY_YOUTUBE_COOKIE_BROWSERS`` environment variable.  No cookie values are
ever copied into logs or returned to the caller.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Result:
    route: str
    stdout: str
    attempts: tuple[str, ...]


def _cookie_browsers(allow_browser_cookies: bool) -> list[str]:
    raw = os.environ.get("VERITY_YOUTUBE_COOKIE_BROWSERS", "")
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return ["chrome", "safari"] if allow_browser_cookies else []


def command_cascade(url: str, args: Iterable[str] = (), *,
                    allow_browser_cookies: bool = False) -> list[tuple[str, list[str]]]:
    """Return deterministic yt-dlp routes without executing them."""
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp is not installed (https://github.com/yt-dlp/yt-dlp)")
    common = ["yt-dlp", "--no-warnings", *list(args), url]
    routes = [("anonymous", common)]
    for browser in _cookie_browsers(allow_browser_cookies):
        routes.append((
            f"{browser}-cookies-web-safari",
            ["yt-dlp", "--no-warnings", "--cookies-from-browser", browser,
             "--extractor-args", "youtube:player_client=web_safari", *list(args), url],
        ))
    return routes


def run(url: str, args: Iterable[str] = (), *, allow_browser_cookies: bool = False,
        timeout: int = 120) -> Result:
    """Run the first successful route; raise with redacted route evidence."""
    attempted: list[str] = []
    errors: list[str] = []
    for route, command in command_cascade(
            url, args, allow_browser_cookies=allow_browser_cookies):
        attempted.append(route)
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            errors.append(f"{route}: timed out after {timeout}s")
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            return Result(route, proc.stdout, tuple(attempted))
        tail = (proc.stderr or proc.stdout or "empty response").strip().splitlines()[-1]
        errors.append(f"{route}: {tail[:240]}")
    raise RuntimeError("all yt-dlp routes failed | " + " | ".join(errors))


def resolve_media_url(url: str, *, allow_browser_cookies: bool = False) -> dict:
    """Resolve a playable media URL plus provenance without downloading bytes."""
    result = run(
        url,
        ["--dump-single-json", "--skip-download", "-f", "b[protocol^=m3u8]/b"],
        allow_browser_cookies=allow_browser_cookies,
    )
    data = json.loads(result.stdout)
    media_url = data.get("url", "")
    if not media_url:
        raise RuntimeError(f"yt-dlp route {result.route} returned no playable media URL")
    return {
        "title": data.get("title", ""),
        "url": media_url,
        "protocol": data.get("protocol", ""),
        "route": result.route,
        "attempts": list(result.attempts),
    }


def fetch_transcript(url: str, *, allow_browser_cookies: bool = False,
                     timeout: int = 300) -> str:
    """Return the FULL transcript text for a video, robustly. yt-dlp auto-subs first (fast, free);
    if they 429 / are absent, fall back to `futron-gemini-transcribe` (multimodal, full stdout).
    Returns complete text — never a truncated preview. Empty string only if every route genuinely
    fails. Portable: the Gemini fallback is used only when the CLI is on PATH."""
    import re as _re
    import tempfile as _tf
    from pathlib import Path as _P
    # 1) yt-dlp auto/uploaded subtitles → plain text
    try:
        with _tf.TemporaryDirectory() as td:
            res = run(url, ["--skip-download", "--write-auto-sub", "--write-sub",
                            "--sub-lang", "en", "--sub-format", "vtt",
                            "-o", f"{td}/%(id)s.%(ext)s"],
                      allow_browser_cookies=allow_browser_cookies, timeout=timeout)
            vtts = list(_P(td).glob("*.vtt"))
            if vtts:
                raw = vtts[0].read_text(errors="ignore")
                lines, seen = [], set()
                for ln in raw.splitlines():
                    ln = ln.strip()
                    if not ln or "-->" in ln or ln.isdigit() or ln.startswith(("WEBVTT", "Kind:", "Language:")):
                        continue
                    ln = _re.sub(r"<[^>]+>", "", ln)
                    if ln and ln not in seen:
                        seen.add(ln); lines.append(ln)
                text = "\n".join(lines).strip()
                if len(text) > 200:
                    return text
    except Exception:
        pass
    # 2) Gemini fallback — full transcript on STDOUT (the CLI prints the complete text when piped)
    if shutil.which("futron-gemini-transcribe"):
        try:
            proc = subprocess.run(["futron-gemini-transcribe", url],
                                  capture_output=True, text=True, timeout=timeout)
            if proc.returncode == 0 and len(proc.stdout.strip()) > 200:
                return proc.stdout.strip()
        except Exception:
            pass
    return ""

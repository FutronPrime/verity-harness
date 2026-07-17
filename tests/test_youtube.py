#!/usr/bin/env python3
"""Regression tests for the shared YouTube recovery cascade."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verity import youtube


def test_anonymous_is_first_and_cookie_routes_follow(monkeypatch):
    monkeypatch.setattr(youtube.shutil, "which", lambda _: "/usr/local/bin/yt-dlp")
    routes = youtube.command_cascade("https://youtu.be/abcdefghijk",
                                     ["--dump-json"], allow_browser_cookies=True)
    assert [r[0] for r in routes] == [
        "anonymous", "chrome-cookies-web-safari", "safari-cookies-web-safari"]
    assert "--cookies-from-browser" not in routes[0][1]
    assert "youtube:player_client=web_safari" in routes[1][1]


def test_403_automatically_falls_back(monkeypatch):
    monkeypatch.setattr(youtube.shutil, "which", lambda _: "/usr/local/bin/yt-dlp")
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if len(calls) == 1:
            return subprocess.CompletedProcess(command, 1, "", "HTTP Error 403: Forbidden")
        return subprocess.CompletedProcess(command, 0, '{"title":"ok"}\n', "")

    monkeypatch.setattr(youtube.subprocess, "run", fake_run)
    result = youtube.run("https://youtu.be/abcdefghijk", ["--dump-json"],
                         allow_browser_cookies=True)
    assert result.route == "chrome-cookies-web-safari"
    assert result.attempts == ("anonymous", "chrome-cookies-web-safari")
    assert len(calls) == 2


def test_cookie_values_are_not_exposed_on_failure(monkeypatch):
    monkeypatch.setattr(youtube.shutil, "which", lambda _: "/usr/local/bin/yt-dlp")
    monkeypatch.setattr(
        youtube.subprocess, "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, 1, "", "ERROR: failed without cookie contents"),
    )
    try:
        youtube.run("https://youtu.be/abcdefghijk", allow_browser_cookies=True)
    except RuntimeError as exc:
        msg = str(exc)
        assert "chrome-cookies-web-safari" in msg
        assert "--cookies-from-browser" not in msg
    else:
        raise AssertionError("expected all routes to fail")


def test_timeout_advances_to_next_route(monkeypatch):
    monkeypatch.setattr(youtube.shutil, "which", lambda _: "/usr/local/bin/yt-dlp")
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(command, 2)
        return subprocess.CompletedProcess(command, 0, '{"title":"ok"}\n', "")

    monkeypatch.setattr(youtube.subprocess, "run", fake_run)
    result = youtube.run("https://youtu.be/abcdefghijk", ["--dump-json"],
                         allow_browser_cookies=True, timeout=2)
    assert result.route == "chrome-cookies-web-safari"
    assert result.attempts == ("anonymous", "chrome-cookies-web-safari")

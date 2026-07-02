#!/usr/bin/env python3
"""repostream — remote-repo acquisition for vet/audit/adjudicate. CI-safe (no network):
exercises slug parsing, local passthrough, and the truncation-honesty downgrade with a
stubbed materialization."""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verity import repostream
from verity import adjudicate as adj


def test_slug_parsing():
    for ref in ("owner/repo", "https://github.com/owner/repo",
                "github.com/owner/repo.git", "git@github.com:owner/repo.git"):
        assert repostream.slug_of(ref) == "owner/repo", ref
        assert repostream.is_remote(ref)
    # local-ish / non-remote refs must NOT be treated as remote
    for ref in ("./local/dir", "/abs/path", "~/thing", "single", "a/b/c/d"):
        assert repostream.slug_of(ref) == "", ref
        assert not repostream.is_remote(ref)


def test_resolve_local_passthrough():
    d = tempfile.mkdtemp()
    local, cleanup, info = repostream.resolve(d)
    assert local == d and info["remote"] is False
    cleanup()  # no-op, must not raise
    assert os.path.isdir(d), "local dir must NOT be deleted by cleanup"


def test_worth_scanning():
    assert repostream._worth_scanning("setup.py")
    assert repostream._worth_scanning("src/install.sh")
    assert repostream._worth_scanning("Dockerfile")
    assert not repostream._worth_scanning("assets/logo.png")
    assert not repostream._worth_scanning("data/big.parquet")


def test_adjudicate_truncated_stream_is_needs_human(monkeypatch):
    """A clean-but-truncated streamed scan must NOT yield INSTALL — unscanned files remain."""
    tmp = tempfile.mkdtemp()
    monkeypatch.setattr(repostream, "resolve",
                        lambda repo: (tmp, (lambda: None),
                                      {"remote": True, "truncated": True, "files": 5, "slug": "o/r"}))

    class _Safe:
        verdict = "SAFE"
        blockers: list = []
    d = adj.adjudicate("o/r", vet_fn=lambda p: _SafeVet(), audit_fn=lambda p: _Safe())
    assert d.verdict == "NEEDS-HUMAN", d
    assert "stream cap" in d.reason or "unscanned" in d.reason


class _SafeVet:
    verdict = "SAFE-TO-APPLY"
    blockers: list = []


def test_materialize_rejects_path_escape(monkeypatch, tmp_path):
    """SECURITY: absolute / '..' tree paths from an UNTRUSTED repo must not escape dest."""
    tree = {"tree": [
        {"type": "blob", "path": "good.py", "size": 10},
        {"type": "blob", "path": "../evil.py", "size": 10},
        {"type": "blob", "path": "/tmp/verity_abs_evil.py", "size": 10},
    ]}

    def fake_gh_get(url, token, timeout=30):
        return tree if "trees" in url else {"default_branch": "main"}
    monkeypatch.setattr(repostream, "_gh_get", fake_gh_get)

    class _Resp:
        def read(self, n=-1):
            return b"print('x')"
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    monkeypatch.setattr(repostream.urllib.request, "urlopen", lambda *a, **k: _Resp())

    dest = tmp_path / "dest"
    info = repostream.materialize("o/r", str(dest))

    assert (dest / "good.py").exists()                       # safe file landed
    assert not (dest.parent / "evil.py").exists()            # '..' escape blocked
    assert not os.path.exists("/tmp/verity_abs_evil.py")     # absolute escape blocked
    assert info["files"] == 1                                # only the safe one written
    assert info["truncated"] is True                         # escapes => scan incomplete (honest)


def test_adjudicate_untruncated_clean_is_install(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setattr(repostream, "resolve",
                        lambda repo: (tmp, (lambda: None),
                                      {"remote": True, "truncated": False, "files": 20, "slug": "o/r"}))

    class _Safe:
        verdict = "SAFE"
        blockers: list = []
    d = adj.adjudicate("o/r", vet_fn=lambda p: _SafeVet(), audit_fn=lambda p: _Safe())
    assert d.verdict == "INSTALL", d

"""verity repostream — analyze a remote repo WITHOUT cloning it.

The vet / audit / adjudicate gates prove a third-party repo is safe to install. To do
that they walk the source — which previously meant `git clone` (tens to hundreds of MB
per repo, just to read a few code files). This module sparse-materializes ONLY the files
worth scanning (code, scripts, installers, config, docs) via the GitHub tree + raw API,
so a 200MB repo is auditable from a few hundred KB of text. Local-first, low-footprint —
the same ethos as the rest of the harness.

Usage in code:
    path, cleanup, info = resolve("owner/repo")   # remote → temp dir; local path → unchanged
    try:
        ... walk `path` ...
    finally:
        cleanup()                                 # removes the temp materialization (no-op for local)

CLI:
    python3 -m verity stream owner/repo [dest]

SAFETY NOTE: streaming is capped (file count + bytes). If a repo exceeds the cap the
materialization is marked `truncated` and `info["truncated"]` is True — callers that make
a SAFE/INSTALL claim MUST treat a truncated scan as incomplete (never assert safe on
unscanned files). honest-by-construction (R29/R63).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request

_GH_API = "https://api.github.com"
_RAW = "https://raw.githubusercontent.com"

# Suffixes worth scanning for safety (executable/config/doc). Binary/data is skipped — it
# can't carry the install-time code-execution risk vet/audit look for.
_SCAN_SUFFIXES = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".sh", ".bash", ".zsh", ".rb", ".go", ".rs",
    ".java", ".c", ".h", ".cpp", ".cc", ".pl", ".php", ".ps1", ".bat", ".cmd", ".lua",
    ".yml", ".yaml", ".toml", ".cfg", ".ini", ".json", ".md", ".txt", ".cmake", ".mk",
}
# Always-scan filenames (no/odd suffix) that carry install-time execution.
_SCAN_NAMES = {
    "dockerfile", "makefile", "setup.py", "setup.cfg", "pyproject.toml", "package.json",
    "install.sh", "postinstall.js", "preinstall.js", ".npmrc", "rakefile", "gemfile",
}
_MAX_FILES = 600
_MAX_BYTES = 16 * 1024 * 1024
_MAX_FILE = 600 * 1024

# process cache so adjudicate (vet THEN audit on the same slug) materializes only once
_CACHE: dict[str, tuple[str, dict]] = {}


def _token() -> str:
    return os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")


def slug_of(target: str) -> str:
    """Return owner/repo if `target` is a github remote ref, else ''."""
    t = target.strip()
    m = re.match(r"^(?:https?://github\.com/|git@github\.com:|github\.com/)?"
                 r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$", t)
    if not m:
        return ""
    slug = m.group(1)
    # a bare local path like "./foo/bar" also matches owner/repo shape — exclude existing paths
    if os.path.sep in target and os.path.exists(os.path.expanduser(target)):
        return ""
    if target.startswith((".", "/", "~")):
        return ""
    return slug


def is_remote(target: str) -> bool:
    return bool(slug_of(target))


def _gh_get(url: str, token: str, timeout: int = 30):
    hdr = {"User-Agent": "verity-repostream", "Accept": "application/vnd.github+json"}
    if token:
        hdr["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _worth_scanning(path: str) -> bool:
    pp = pathlib.PurePosixPath(path.lower())
    return pp.suffix in _SCAN_SUFFIXES or pp.name in _SCAN_NAMES


def materialize(slug: str, dest: str, *, token: str | None = None) -> dict:
    """Pull the scan-worthy files of `slug` into `dest`. Returns info dict."""
    token = token if token is not None else _token()
    dst = pathlib.Path(dest)
    info = {"slug": slug, "path": str(dst), "files": 0, "bytes": 0,
            "truncated": False, "branch": "", "error": ""}
    try:
        repo = _gh_get(f"{_GH_API}/repos/{slug}", token)
        branch = repo.get("default_branch") or "HEAD"
        tree = _gh_get(f"{_GH_API}/repos/{slug}/git/trees/{branch}?recursive=1", token)
    except Exception as e:
        info["error"] = f"github api: {str(e)[:160]}"
        return info
    info["branch"] = branch
    if tree.get("truncated"):
        info["truncated"] = True  # GitHub itself truncated the tree (huge repo)
    dst.mkdir(parents=True, exist_ok=True)
    blobs = [n for n in tree.get("tree", []) if n.get("type") == "blob"]
    for node in blobs:
        if info["files"] >= _MAX_FILES or info["bytes"] >= _MAX_BYTES:
            info["truncated"] = True
            break
        p = node["path"]
        if not _worth_scanning(p) or int(node.get("size", 0)) > _MAX_FILE:
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    f"{_RAW}/{slug}/{branch}/{urllib.parse.quote(p)}",
                    headers={"User-Agent": "verity-repostream"}), timeout=30) as r:
                data = r.read(_MAX_FILE + 1)
        except Exception:
            continue
        out = dst / p
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        info["files"] += 1
        info["bytes"] += len(data)
    return info


def resolve(target: str):
    """(local_path, cleanup, info). Remote ref → sparse temp materialization; local path →
    returned unchanged with a no-op cleanup. Materialization is process-cached by slug."""
    slug = slug_of(target)
    if not slug:
        return os.path.expanduser(target), (lambda: None), {"slug": "", "remote": False}
    if slug in _CACHE:
        path, info = _CACHE[slug]
        return path, (lambda: None), {**info, "remote": True, "cached": True}
    dest = tempfile.mkdtemp(prefix="verity-stream-")
    info = materialize(slug, dest)
    info["remote"] = True
    _CACHE[slug] = (dest, info)

    def _cleanup():
        _CACHE.pop(slug, None)
        shutil.rmtree(dest, ignore_errors=True)
    return dest, _cleanup, info


def _cli(args: list) -> int:
    if not args:
        print("usage: verity stream <owner/repo> [dest]", flush=True)
        return 2
    slug = slug_of(args[0]) or args[0]
    dest = args[1] if len(args) > 1 else tempfile.mkdtemp(prefix="verity-stream-")
    info = materialize(slug, dest)
    print(json.dumps(info, indent=2))
    return 0 if info["files"] and not info["error"] else 1

"""Pointer-indirection (memory handles) — keep big payloads OUT of context.

When a tool or sub-agent returns a large blob (a scraped page, a 50KB file, a long sub-result), putting
the whole thing in the next prompt burns the window. Instead: STASH it on disk and pass a tiny HANDLE +
a preview. Downstream only resolves the full content if it actually needs it. (arXiv:2511.22729 reports
~7× token cuts on tool-heavy runs.) Pure stdlib; the store is just files under ~/.verity-harness/handles/.
"""
from __future__ import annotations

import hashlib
import os
import re

DIR = os.path.expanduser(os.environ.get("VERITY_HANDLES_DIR", "~/.verity-harness/handles"))
_RE = re.compile(r"verity://h/([0-9a-f]{16})")


def stash(content: str, label: str = "") -> str:
    """Persist content, return a compact handle string. Idempotent by content hash (same blob → same handle)."""
    content = content if isinstance(content, str) else str(content)
    os.makedirs(DIR, exist_ok=True)
    h = hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()[:16]
    p = os.path.join(DIR, h)
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
    return f"verity://h/{h}"


def resolve(handle: str) -> str:
    """Return the full stashed content for a handle (or a marker if it's gone)."""
    m = _RE.search(handle or "")
    if not m:
        return handle                      # not a handle — pass through
    p = os.path.join(DIR, m.group(1))
    try:
        return open(p, encoding="utf-8").read()
    except FileNotFoundError:
        return f"[handle {handle} not found — content expired or never stashed]"


def boundify(content: str, preview_chars: int = 600, threshold: int = 2000, label: str = "") -> str:
    """If content is small, return it as-is. If it's BIG, stash it and return preview + handle, so the
    prompt stays bounded. The downstream agent can `resolve()` the handle when it genuinely needs the rest."""
    content = content if isinstance(content, str) else str(content)
    if len(content) <= threshold:
        return content
    handle = stash(content, label)
    head = content[:preview_chars].rstrip()
    return (f"{head}\n…[+{len(content) - preview_chars:,} more chars stashed at {handle} — "
            f"resolve with `verity handle get {handle}` only if you need the full content]")

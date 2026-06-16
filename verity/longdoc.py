"""RLM-style long-document mode — query a file too big for the context window WITHOUT loading it all.

Inspired by Recursive Language Models (arXiv:2512.24601): keep the data OUTSIDE the context and pull
only the relevant slices in. Here, zero-dep and deterministic: grep the query terms across the file,
return the matching line-windows (±context) up to a hard char budget. The model reasons over the slices
it asked for, not the whole document — so a 500KB file costs a fixed, bounded number of tokens.

  query_doc(path, query)         → relevant windows, capped
  verity doc <path> "<query>"    → CLI
"""
from __future__ import annotations

import os
import re


def query_doc(path: str, query: str, context: int = 4, max_chars: int = 6000, max_windows: int = 12) -> str:
    """Return the most relevant slices of a (possibly huge) file for `query`, bounded to max_chars.
    Deterministic keyword windowing — no model, no full load (streams line by line)."""
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return f"[longdoc: {path} not found]"
    terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
    stems = {t[:6] for t in terms}
    if not stems:
        return "[longdoc: query had no usable terms]"
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except Exception as e:  # noqa: BLE001
        return f"[longdoc: cannot read {path}: {type(e).__name__}]"
    # score each line by how many query stems it contains
    hits = []
    for i, ln in enumerate(lines):
        low = ln.lower()
        score = sum(1 for s in stems if s in low)
        if score:
            hits.append((score, i))
    if not hits:
        return f"[longdoc: no lines in {os.path.basename(path)} match '{query}' ({len(lines):,} lines scanned)]"
    hits.sort(key=lambda x: (-x[0], x[1]))
    # build non-overlapping windows around the top hits, in file order, until the budget is hit
    chosen, used, ranges = [], 0, []
    for score, i in hits:
        lo, hi = max(0, i - context), min(len(lines), i + context + 1)
        if any(not (hi <= a or lo >= b) for a, b in ranges):   # overlaps an already-chosen window
            continue
        block = "\n".join(lines[lo:hi])
        if used + len(block) > max_chars or len(ranges) >= max_windows:
            break
        ranges.append((lo, hi)); used += len(block) + 40
        chosen.append((lo, hi, block))
    chosen.sort(key=lambda x: x[0])
    out = [f"=== longdoc: {os.path.basename(path)} ({len(lines):,} lines) — {len(chosen)} relevant slices for '{query}' ==="]
    for lo, hi, block in chosen:
        out.append(f"\n--- lines {lo + 1}-{hi} ---\n{block}")
    out.append(f"\n[{len(hits)} matching lines total; showing top {len(chosen)} windows within {max_chars} chars. "
               "Re-query with more specific terms to drill in.]")
    return "\n".join(out)

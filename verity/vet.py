#!/usr/bin/env python3
"""`verity vet <repo|skill|file>` — the SAFE-BEFORE-APPLY gate for agents that go
out and find repos/skills/MCP servers and want to use them.

The REUSE-FIRST + proactive-research path (R60) sends agents to fetch third-party
code. That code — especially SKILL.md / MCP tool-descriptions / fetched markdown —
is a documented prompt-injection vector: once installed it becomes the agent's own
instructions. So nothing gets applied until it passes this gate.

vet() walks the target, scans each file with the CORRECT surface calibration
(instruction files strict, docs lenient on doc-noise but strict on HARD injection —
see verity_scan), aggregates, logs an auditable receipt to the ledger, and returns:

  SAFE-TO-APPLY  (exit 0)  — clean; apply it.
  REVIEW         (exit 1)  — doc-noise / suspicious; a human should glance before use.
  BLOCK          (exit 2)  — HARD injection or a HIGH-RISK instruction file; do NOT apply.

  python3 -m verity vet ./some-skill-repo
  python3 -m verity vet ~/.openclaw/integrations/staged/docling
"""
from __future__ import annotations

import os
import pathlib
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verity_scan as vscan

try:
    from . import ledger
except Exception:
    ledger = None

GATE = "vet"
_SCAN_EXT = (".md", ".mdc", ".txt", ".json")
# Directories that are DATA/vendored, not the apply-surface — a parsed-paper test fixture or a
# vendored dep is never loaded as the agent's instructions, so scanning it produces noise, not
# signal. Standard security-scanner practice: skip them.
_SKIP_DIRS = ("/tests/", "/test/", "/testdata/", "/test-data/", "/__tests__/", "/fixtures/",
              "/__fixtures__/", "/groundtruth/", "/data/", "/node_modules/", "/.git/",
              "/vendor/", "/dist/", "/build/", "/__pycache__/", "/.venv/", "/site-packages/")


@dataclass
class VetResult:
    target: str
    verdict: str                       # SAFE-TO-APPLY | REVIEW | BLOCK
    files_scanned: int = 0
    blockers: list = field(default_factory=list)     # (file, scan-verdict, hard, top-finding)
    reviews: list = field(default_factory=list)

    def report(self) -> str:
        icon = {"SAFE-TO-APPLY": "✅", "REVIEW": "🔎", "BLOCK": "🛑"}[self.verdict]
        out = [f"{icon} {self.verdict} — {self.target}  ({self.files_scanned} files scanned)"]
        for f, v, hard, top in self.blockers:
            out.append(f"  🛑 {v} (hard={hard}) {f}" + (f"  ← {top}" if top else ""))
        for f, v, top in self.reviews[:8]:
            out.append(f"  🔎 {v} {f}" + (f"  ← {top}" if top else ""))
        if self.verdict == "BLOCK":
            out.append("  → Do NOT apply. The flagged instruction-surface file would "
                       "become your directives. Review the blocker(s) first.")
        return "\n".join(out)


def _iter_files(p: pathlib.Path):
    if p.is_file():
        yield p
    elif p.is_dir():
        for q in p.rglob("*"):
            s = str(q).replace(os.sep, "/").lower()
            if q.suffix.lower() in _SCAN_EXT and not any(d in s + "/" for d in _SKIP_DIRS):
                yield q


def vet(target: str, *, run: str = "") -> VetResult:
    """Vet a local path OR a remote `owner/repo` (streamed via the GitHub API, no clone)."""
    from . import repostream
    local, cleanup, info = repostream.resolve(target)
    try:
        res = _vet_local(local, run=run)
        if info.get("remote"):
            res.target = info.get("slug") or target
            res.streamed = True
            res.stream_truncated = bool(info.get("truncated"))
            if not info.get("files") and info.get("error"):
                res.verdict = "BLOCK"
                res.blockers.append((res.target, "STREAM-FAILED", 0, info["error"]))
        return res
    finally:
        cleanup()


def _vet_local(target: str, *, run: str = "") -> VetResult:
    p = pathlib.Path(os.path.expanduser(target))
    res = VetResult(target=str(p), verdict="SAFE-TO-APPLY")
    if not p.exists():
        res.verdict = "BLOCK"
        res.blockers.append((str(p), "NOT-FOUND", 0, "path does not exist"))
        return res
    for q in _iter_files(p):
        try:
            txt = q.read_text(errors="replace")
        except Exception:
            continue
        surface = vscan.classify_surface(str(q))
        r = vscan.scan_text(txt, surface=surface)
        res.files_scanned += 1
        hard_top = next((f["label"] for f in r["findings"] if f["label"] in vscan.HARD_LABELS), "")
        top = hard_top or (r["findings"][0]["label"] if r["findings"] else "")
        # BLOCK only on a real HARD injection signal (role-override, exfil, hidden-unicode,
        # conceal-from-user, …) — NOT on accumulated doc-noise, which would false-block
        # reputable repos. Soft/partial findings → REVIEW (a human should glance).
        if r["hard"] >= 5:
            res.blockers.append((str(q), r["verdict"], r["hard"], top))
        elif r["hard"] > 0 or (surface == "instruction" and r["verdict"] == "HIGH-RISK"):
            res.reviews.append((str(q), r["verdict"], top))
    res.verdict = "BLOCK" if res.blockers else "REVIEW" if res.reviews else "SAFE-TO-APPLY"
    if ledger is not None:
        ledger.log(GATE, trigger=str(p)[:200], verdict=res.verdict,
                   detail=f"{res.files_scanned} files; {len(res.blockers)} blockers; "
                          f"{len(res.reviews)} reviews", run=run)
    return res


def _cli(argv: list) -> int:
    if not argv:
        print('usage: verity vet <repo|skill|file>', file=sys.stderr)
        return 2
    r = vet(argv[0])
    print(r.report())
    return 2 if r.verdict == "BLOCK" else 1 if r.verdict == "REVIEW" else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

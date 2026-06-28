#!/usr/bin/env python3
"""`verity adjudicate <repo>` — INTELLIGENT install decision: deterministic pre-filter,
then escalate the GRAY ZONE to reasoned multi-model judgment. The fix for "regex either
false-alarms or misses things."

This is VERITY's own doctrine (v2.1 DETERMINISTIC-VERIFIER-FIRST + v2.2 PANEL+JUDGE) applied
to install safety, and it COMPOSES the evolving base rather than rebuilding:

  • cheap deterministic layer  → `verity vet` (instructions) + `verity audit` (code).
        Clear cases are decided here for free: a real backdoor → AVOID; pure-stdlib → INSTALL.
  • intelligent layer (gray)   → `verity council` (anonymized multi-model) reads the ACTUAL
        flagged findings + code context and decides INSTALL / AVOID / NEEDS-HUMAN with a
        rationale — so "exfiltration pattern" is judged in context (a TTS client calling its
        documented provider = fine; a server POSTing your .env to a pastebin = AVOID).
  • evolution                  → every verdict is logged to `ledger`, which `verity evolve`
        distills into the injected PLAYBOOK. The gate gets smarter each run; it does not reset.

Only genuine backdoors (audit BLOCK) short-circuit to AVOID without spending a judge call.
Graceful: if no LLM backend is reachable, it returns the deterministic REVIEW as NEEDS-HUMAN
(never a false INSTALL, never a hard crash).

  python3 -m verity adjudicate ./some-mcp-server [--council]
Exit: 0 INSTALL · 1 NEEDS-HUMAN · 2 AVOID.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

try:
    from . import ledger
except Exception:
    ledger = None

GATE = "adjudicate"


@dataclass
class Decision:
    verdict: str                       # INSTALL | NEEDS-HUMAN | AVOID
    reason: str = ""
    escalated: bool = False            # did we spend an intelligent-judge call?
    rationale: str = ""                # the judge's reasoning (when escalated)
    evidence: dict = field(default_factory=dict)

    def __str__(self):
        icon = {"INSTALL": "✅", "NEEDS-HUMAN": "🔎", "AVOID": "🛑"}[self.verdict]
        tag = "intelligent-judge" if self.escalated else "deterministic"
        out = [f"{icon} {self.verdict}  ({tag}) — {self.reason}"]
        if self.rationale:
            out.append(f"   rationale: {self.rationale}")
        return "\n".join(out)


def _summarize(vet_res, audit_res) -> str:
    """A compact, judge-ready brief of exactly what the deterministic layer flagged."""
    lines = [f"vet (instructions): {vet_res.verdict}", f"audit (code): {audit_res.verdict}"]
    if getattr(audit_res, "caps", None):
        lines.append("capabilities: " + ", ".join(f"{k}×{len(v)}" for k, v in audit_res.caps.items()))
    for c in getattr(audit_res, "combos", [])[:4]:
        lines.append("flag: " + c)
    for f, v, top in getattr(vet_res, "reviews", [])[:4]:
        lines.append(f"vet-review: {top} in {f.split('/')[-1]}")
    return "\n".join(lines)


_JUDGE_PROMPT = (
    "You are a security reviewer deciding whether a third-party MCP server is safe to install "
    "into an AI agent's runtime. Below is a deterministic scan summary. Judge whether the flagged "
    "items are GENUINELY HARMFUL (a backdoor, secret exfiltration to an unexpected host, "
    "destructive action) or LEGITIMATE-FOR-A-SERVER (calling a documented API, reading its own "
    "config, normal file I/O). Be decisive but conservative on real risk.\n\n"
    "SCAN SUMMARY:\n{brief}\n\n"
    "Reply with one short rationale line, then a final line exactly: "
    "DECISION: INSTALL  (or)  DECISION: AVOID  (or)  DECISION: NEEDS-HUMAN")


def _parse(text: str):
    m = re.search(r"DECISION:\s*(INSTALL|AVOID|NEEDS-HUMAN)", text or "", re.I)
    verdict = m.group(1).upper() if m else "NEEDS-HUMAN"
    rationale = (text or "").strip().split("\n")[0][:200]
    return verdict, rationale


def adjudicate(repo: str, *, vet_fn=None, audit_fn=None, judge_fn=None,
               use_council: bool = False, run: str = "") -> Decision:
    # Compose the evolving base (default to the real modules; injectable for tests).
    if vet_fn is None:
        from .vet import vet as vet_fn
    if audit_fn is None:
        from .audit_code import audit as audit_fn

    vet_res = vet_fn(repo)
    audit_res = audit_fn(repo)

    # ── deterministic clear cases (free) ────────────────────────────────────
    if audit_res.verdict == "BLOCK":
        d = Decision("AVOID", reason=f"runtime backdoor / obfuscated exec: "
                     f"{(audit_res.blockers or ['code'])[0]}", evidence={"layer": "audit"})
        return _log(d, repo, run)
    if vet_res.verdict == "BLOCK":
        d = Decision("AVOID", reason="instruction-file injection (vet BLOCK)",
                     evidence={"layer": "vet"})
        return _log(d, repo, run)
    if audit_res.verdict == "SAFE" and vet_res.verdict in ("SAFE", "SAFE-TO-APPLY"):
        d = Decision("INSTALL", reason="no dangerous capabilities or injection detected")
        return _log(d, repo, run)

    # ── gray zone → escalate to intelligent judgment ────────────────────────
    brief = _summarize(vet_res, audit_res)
    prompt = _JUDGE_PROMPT.format(brief=brief)
    judge = judge_fn or _default_judge(use_council)
    try:
        answer = judge(prompt)
    except Exception as e:
        d = Decision("NEEDS-HUMAN", reason=f"ambiguous + no judge reachable ({e}); "
                     f"deterministic verdict was REVIEW", evidence={"brief": brief})
        return _log(d, repo, run)
    verdict, rationale = _parse(answer)
    d = Decision(verdict, reason="gray zone adjudicated by intelligent judge",
                 escalated=True, rationale=rationale, evidence={"brief": brief})
    return _log(d, repo, run)


def _default_judge(use_council: bool):
    """Return a judge(prompt)->text using VERITY's own backends (council for high-stakes,
    router otherwise). Composes the evolving base; no new model wiring."""
    if use_council:
        from .council import council
        return lambda p: council(p, n=3).final
    from .router import ask
    return lambda p: ask(p).text


def _log(d: Decision, repo: str, run: str) -> Decision:
    if ledger is not None:
        ledger.log(GATE, trigger=str(repo)[:200], verdict=d.verdict,
                   detail=(d.rationale or d.reason)[:400],
                   evidence=("escalated" if d.escalated else "deterministic"), run=run)
    return d


def _cli(argv: list) -> int:
    use_council = "--council" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print("usage: verity adjudicate <repo> [--council]", file=sys.stderr); return 2
    d = adjudicate(args[0], use_council=use_council)
    print(d)
    return 0 if d.verdict == "INSTALL" else 2 if d.verdict == "AVOID" else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

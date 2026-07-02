#!/usr/bin/env python3
"""
verity scan — INGEST-SCAN untrusted content before reuse (prompt-injection detector).

Markdown / MCP-server descriptions / skill .md / fetched web text are a documented
injection vector (Snyk: payload-splitting, delimiter-confusion, role-override hide in .md).
VERITY's REUSE-FIRST path must scan before it trusts. Stdlib-only. Exit 2 = HIGH risk.

SURFACE-AWARE (so agents can AUTO-VET fetched repos/skills without false-blocking the docs
that make up most of a repo): findings split into HARD (real injection) vs SOFT (doc-noise),
and the verdict is calibrated by surface — an INSTRUCTION file (SKILL.md / *.mdc / MCP
tool-description) becomes the agent's own directives (strict), a DOC file (README/changelog/
reference) is documentation (lenient on badges/install-curls/rm-rf/design-doc data-flow,
strict on HARD-ALWAYS signals like role-override + hidden-unicode). See `verity vet` for the
repo-level SAFE-TO-APPLY/REVIEW/BLOCK gate built on this.

Usage:
  verity_scan.py <file|dir> ...        # scan files/dirs (.md/.txt/.json/.mdc), surface auto-detected
  echo "<text>" | verity_scan.py -      # scan stdin (strict instruction surface)
  verity_scan.py --json <path>          # machine-readable verdict (+ hard/soft/surface)
Exit: 0 clean · 1 suspicious · 2 high-risk (block reuse until reviewed).
"""
from __future__ import annotations
import json, re, sys, pathlib, unicodedata

# (pattern, weight, label) — weight sums into a risk score
PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|above|prior|earlier)\s+(instructions|prompts|rules)", 5, "override: ignore-previous"),
    (r"disregard\s+(the\s+)?(system|previous|above)", 5, "override: disregard"),
    (r"\b(you\s+are\s+now|from\s+now\s+on,?\s+you|act\s+as|pretend\s+to\s+be|new\s+(role|persona|system))\b", 4, "role-override"),
    (r"(^|\n)\s*(system|assistant|developer)\s*[:>]", 4, "role-impersonation delimiter"),
    (r"<\/?(system|assistant|im_start|im_end|tool_call)\b", 4, "fake chat/tool delimiter"),
    (r"\b(do\s+not|don'?t)\s+(tell|inform|mention|reveal).{0,20}(user|human|owner)", 5, "conceal-from-user"),
    (r"\b(secretly|silently|without\s+(telling|asking|informing))\b", 3, "covert-action"),
    (r"\b(exfiltrat|leak|send|post|upload|forward|email).{0,30}(api[_\s-]?key|token|secret|credential|password|env|\.env|ssh|private\s*key)", 6, "exfiltration"),
    (r"\b(curl|wget|fetch|http[s]?://)[^\n]{0,80}(\?|=|token|key|webhook|paste|hook\.)", 4, "outbound-callback"),
    (r"\b(rm\s+-rf|sudo|chmod\s+777|:\(\)\{|mkfs|dd\s+if=)", 5, "destructive-shell"),
    (r"\b(print|output|reveal|repeat)\s+(your|the)\s+(system\s+prompt|instructions|rules|hidden)", 5, "prompt-extraction"),
    (r"base64|fromCharCode|atob\(|eval\(|exec\(", 2, "obfuscation/exec"),
    (r"\b(run|call|invoke|use)\s+the\s+[\w-]+\s+(tool|command|mcp|function)\b.{0,40}(delete|send|post|transfer|pay|wire)", 5, "tool-injection→side-effect"),
]
COMPILED = [(re.compile(p, re.I), w, l) for p, w, l in PATTERNS]

# Decorative badge / shield / CI-image hosts: a real exfil never uses these (they can't
# receive data), but their `?style=`/`=` query strings trip the outbound-callback rule and
# produce HIGH-RISK false-positives on ordinary project READMEs. Suppress ONLY the
# outbound-callback finding for these hosts; every other heuristic (token/key/webhook/paste,
# hidden-unicode, covert-action, role-override, …) is untouched.
_BADGE_HOSTS = ("shields.io", "badgen.net", "forthebadge.com", "badge.fury.io",
                "circleci.com", "app.codecov.io", "codecov.io", "img.badgesize",
                "github.com/.*/workflows/", "githubusercontent.com")

def _is_badge(match: str) -> bool:
    m = match.lower()
    return any(h in m for h in _BADGE_HOSTS) or m.rstrip(")\"' ").endswith((".svg", ".png"))

# HARD signals are real prompt-injection no matter where they appear — a project README has
# no legitimate reason to say "ignore all previous instructions" or carry zero-width chars.
# SOFT signals (install curls, "silently fails" in prose, base64 in a code sample) appear
# innocently in DOCUMENTATION but are suspicious in an INSTRUCTION file (skill.md / MCP
# tool-description) that becomes the agent's own directives. Calibrate the verdict by surface
# so agents can AUTO-VET repos/skills: docs don't false-block on doc-noise, instruction files
# stay strict, and a HARD signal flags HIGH-RISK in ANY surface.
# HARD-ALWAYS: no legitimate reason to appear in ANY file — real injection on any surface.
HARD_ALWAYS = {
    "hidden-unicode (zero-width/bidi)", "override: ignore-previous", "override: disregard",
    "role-override", "role-impersonation delimiter", "fake chat/tool delimiter",
    "conceal-from-user", "prompt-extraction",
}
# HARD-INSTRUCTION: an ATTACK when the file becomes the agent's directives (SKILL.md), but
# LEGITIMATE in documentation (a design doc discussing "send the token to the service", an
# uninstall guide with rm -rf, a tool doc describing a delete action). HARD on the
# instruction surface, demoted to soft on the doc surface — so design docs/test-fixtures
# don't false-block, while a malicious skill still does.
HARD_INSTRUCTION = {"exfiltration", "destructive-shell", "tool-injection→side-effect"}
HARD_LABELS = HARD_ALWAYS | HARD_INSTRUCTION
# Filenames whose CONTENT becomes agent instructions → strict surface.
_INSTRUCTION_NAMES = ("skill.md", ".mdc", "agents.md", "claude.md", "cursorrules",
                      "system.md", "prompt.md", "tool", "mcp")
_DOC_NAMES = ("readme", "changelog", "contributing", "license", "code_of_conduct",
              "history", "docs/", "/doc/", ".txt", "notes")

_INSTRUCTION_BASENAMES = ("skill.md", "agents.md", "claude.md", "gemini.md",
                          "cursorrules", ".cursorrules", "system.md", "prompt.md",
                          "persona.md", "instructions.md")

def classify_surface(name: str) -> str:
    """instruction = content becomes the agent's directives (strict, e.g. SKILL.md / *.mdc /
    MCP tool-description); doc = human documentation (lenient on doc-noise, strict on HARD
    injection). Calibrated so an agent can vet a whole REPO without false-blocking on the
    docs/test-data that make up most of it."""
    n = (name or "").lower()
    base = n.rsplit("/", 1)[-1]
    if base in _INSTRUCTION_BASENAMES or base.endswith(".mdc"):
        return "instruction"
    # generic repo content (READMEs, reference docs, test fixtures, json) → doc surface
    if n.endswith((".md", ".txt", ".json", ".rst", ".markdown")):
        return "doc"
    return "instruction"   # stdin / unknown text → safe default = strict

# Zero-width / format chars that are LEGITIMATE (emoji ZWJ sequences, variation selectors)
# — flagging these produced false HARD hits on emoji-rich READMEs (e.g. 👨‍💻 uses U+200D).
_LEGIT_INVIS = {0x200d, 0xfe0e, 0xfe0f}

def scan_text(text, surface: str = "instruction"):
    findings = []
    # invisible / zero-width / bidi control chars (hidden payloads) — always HARD
    invis = [hex(ord(c)) for c in text
             if (unicodedata.category(c) in ("Cf",) or c in "​‎‏‪‮⁦⁩")
             and ord(c) not in _LEGIT_INVIS]
    if invis:
        findings.append({"label": "hidden-unicode (zero-width/bidi)", "weight": 4, "sample": invis[:6]})
    for rx, w, label in COMPILED:
        for m in rx.finditer(text):
            hit = m.group(0)[:80]
            if label == "outbound-callback" and _is_badge(hit):
                continue  # decorative badge/image URL — not an exfil channel
            ln = text[:m.start()].count("\n") + 1
            findings.append({"label": label, "weight": w, "line": ln, "match": hit})
    # On the doc surface, HARD-INSTRUCTION signals (exfil / destructive-shell / tool-side-effect)
    # are demoted to soft — they appear legitimately in design docs, uninstall guides, and tool
    # descriptions. HARD-ALWAYS signals stay hard everywhere.
    _demote = HARD_INSTRUCTION if surface == "doc" else set()
    hard = sum(f["weight"] for f in findings
               if f["label"] in HARD_LABELS and f["label"] not in _demote)
    soft = sum(f["weight"] for f in findings
               if f["label"] not in HARD_LABELS or f["label"] in _demote)
    score = hard + soft
    # A HARD signal (real injection) → HIGH-RISK in any surface. Otherwise threshold by surface:
    # instruction files stay strict (>=6); docs tolerate doc-noise (only soft → cap at SUSPICIOUS).
    if hard >= 5:
        verdict = "HIGH-RISK"
    elif surface == "doc":
        verdict = "HIGH-RISK" if hard >= 4 else "SUSPICIOUS" if (hard or soft >= 8) else "CLEAN"
    else:
        verdict = "HIGH-RISK" if score >= 6 else "SUSPICIOUS" if score >= 3 else "CLEAN"
    return {"verdict": verdict, "score": score, "hard": hard, "soft": soft,
            "surface": surface, "findings": findings}

def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    targets, texts = [], []
    if not args or args == ["-"]:
        texts.append(("<stdin>", sys.stdin.read()))
    else:
        for a in args:
            p = pathlib.Path(a)
            if p.is_dir():
                targets += [q for q in p.rglob("*") if q.suffix.lower() in (".md", ".mdc", ".txt", ".json")]
            elif p.exists():
                targets.append(p)
        for q in targets:
            try: texts.append((str(q), q.read_text(errors="replace")))
            except Exception as e: texts.append((str(q), f"<read-error {e}>"))
    worst, results = 0, []
    for name, txt in texts:
        r = scan_text(txt, surface=classify_surface(name)); r["target"] = name; results.append(r)
        worst = max(worst, 6 if r["verdict"] == "HIGH-RISK" else 3 if r["verdict"] == "SUSPICIOUS" else 0)
        if not as_json:
            print(f"[{r['verdict']:10}] score={r['score']:>2} ({r['surface'][:5]} hard={r['hard']}) {name}")
            for f in r["findings"][:8]:
                print(f"    +{f['weight']} {f['label']}" + (f" L{f.get('line')}: {f.get('match','')}" if f.get('match') else f" {f.get('sample','')}"))
    if as_json: print(json.dumps(results, indent=1))
    sys.exit(2 if worst >= 6 else 1 if worst >= 3 else 0)

if __name__ == "__main__":
    main()

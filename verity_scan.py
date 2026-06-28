#!/usr/bin/env python3
"""
verity scan — INGEST-SCAN untrusted content before reuse (prompt-injection detector).

Markdown / MCP-server descriptions / skill .md / fetched web text are a documented
injection vector (Snyk: payload-splitting, delimiter-confusion, role-override hide in .md).
VERITY's REUSE-FIRST path must scan before it trusts. Stdlib-only. Exit 2 = HIGH risk.

Usage:
  verity_scan.py <file|dir> ...        # scan files/dirs (.md/.txt/.json/.mdc)
  echo "<text>" | verity_scan.py -      # scan stdin
  verity_scan.py --json <path>          # machine-readable verdict
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

def scan_text(text):
    findings = []
    # invisible / zero-width / bidi control chars (hidden payloads)
    invis = [hex(ord(c)) for c in text if unicodedata.category(c) in ("Cf",) or c in "​‎‏‪‮⁦⁩"]
    if invis:
        findings.append({"label": "hidden-unicode (zero-width/bidi)", "weight": 4, "sample": invis[:6]})
    for rx, w, label in COMPILED:
        for m in rx.finditer(text):
            hit = m.group(0)[:80]
            if label == "outbound-callback" and _is_badge(hit):
                continue  # decorative badge/image URL — not an exfil channel
            ln = text[:m.start()].count("\n") + 1
            findings.append({"label": label, "weight": w, "line": ln, "match": hit})
    score = sum(f["weight"] for f in findings)
    verdict = "HIGH-RISK" if score >= 6 else "SUSPICIOUS" if score >= 3 else "CLEAN"
    return {"verdict": verdict, "score": score, "findings": findings}

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
        r = scan_text(txt); r["target"] = name; results.append(r)
        worst = max(worst, r["score"])
        if not as_json:
            print(f"[{r['verdict']:10}] score={r['score']:>2} {name}")
            for f in r["findings"][:8]:
                print(f"    +{f['weight']} {f['label']}" + (f" L{f.get('line')}: {f.get('match','')}" if f.get('match') else f" {f.get('sample','')}"))
    if as_json: print(json.dumps(results, indent=1))
    sys.exit(2 if worst >= 6 else 1 if worst >= 3 else 0)

if __name__ == "__main__":
    main()

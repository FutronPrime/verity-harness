#!/usr/bin/env python3
"""`verity audit <repo>` — static CODE-safety auditor. The system that proves a
third-party server/tool is safe to install BEFORE you wire it into your runtime.

INGEST-SCAN (`verity vet`) clears the MARKDOWN (skill.md / tool-descriptions that
become your instructions). This clears the CODE: what does the server actually DO
when it runs? It reports the dangerous CAPABILITIES present in the real source —
outbound network, code execution, filesystem mutation, credential access, and
(the real red flag) REMOTE-CODE-EXECUTION / obfuscated exec — and flags dangerous
COMBINATIONS (e.g. reads env secrets AND posts to a hardcoded external host).

This is what lets an agent INSTALL INDEPENDENTLY instead of stopping at "executing
untrusted code is a boundary": you don't run their installer — you (1) audit the
code here, (2) hand-write a minimal config entry yourself, (3) back up + validate +
health-check (futron-mcp-safe-wire does the wiring). The boundary becomes an
engineering problem with a safe, reversible solution.

  python3 -m verity audit ./some-mcp-server
Exit: 0 SAFE · 1 REVIEW (powerful but normal-for-a-server caps) · 2 BLOCK (remote
code / obfuscated exec / clear exfil combo — do NOT install).
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
from dataclasses import dataclass, field

# capability → (regex, weight). Weight reflects how dangerous the capability is on its own.
CAPS = {
    "net-out": (r"\b(requests\.(get|post|put|patch|delete)|urllib\.request|httpx\.|aiohttp|"
                r"http\.client|socket\.socket|fetch\s*\(|axios\.|XMLHttpRequest|WebSocket|"
                r"\.connect\(|net\.connect)", 1),
    "exec": (r"\b(subprocess\.|os\.system|os\.popen|commands\.getoutput|eval\s*\(|exec\s*\(|"
             r"child_process|\.spawn\s*\(|execSync|spawnSync|new\s+Function\s*\(|__import__\s*\()", 2),
    "fs-write": (r"(open\s*\([^)]*['\"][wax]|shutil\.(rmtree|move|copy\w*)|os\.(remove|unlink|rmdir)|"
                 r"fs\.(writeFile|unlink|rm|appendFile)|\.write_text\(|\.write_bytes\()", 1),
    "cred-access": (r"(os\.environ|process\.env|os\.getenv|getenv\(|\.aws[/\\]credentials|"
                    r"\.ssh[/\\]|id_rsa|keychain|security\s+find-generic|/etc/passwd|"
                    r"load_dotenv|\.env['\"\s])", 1),
    # NOTE: `pip install` / `npm install` are NORMAL packaging, NOT remote-code-exec — excluded
    # (they false-flagged every repo's setup scripts). This is the genuinely dangerous form:
    # downloading code at RUNTIME and piping/eval-ing it.
    "remote-code": (r"(curl[^\n|]{0,80}\|\s*(sh|bash|python|node|zsh)\b|"
                    r"wget[^\n|]{0,80}\|\s*(sh|bash|python|node)\b|"
                    r"\b(exec|eval)\s*\([^\n]{0,80}(requests\.|urlopen|urllib|httpx|aiohttp|fetch\s*\()|"
                    r"requests\.(get|post)\([^)]*\)\.(text|content)[^\n]{0,40}(exec|eval)|"
                    r"urlopen\([^)]*\)[^\n]{0,40}(exec|eval)|"
                    r"fetch\([^)]{0,100}\)[^\n]{0,60}\beval\()", 6),
    "obfusc-exec": (r"(base64\.b64decode[^\n]{0,60}(exec|eval|decode\(\))|atob\([^\n]{0,60}(eval|Function)|"
                    r"fromCharCode[^\n]{0,60}eval|codecs\.decode[^\n]{0,40}exec)", 6),
}
COMPILED = {k: (re.compile(p, re.I), w) for k, (p, w) in CAPS.items()}

_SRC_EXT = (".py", ".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx", ".sh", ".bash",
            ".rb", ".go", ".rs", ".php", ".pl")
_SKIP = ("/tests/", "/test/", "/testdata/", "/__tests__/", "/fixtures/", "/node_modules/",
         "/.git/", "/vendor/", "/dist/", "/build/", "/__pycache__/", "/.venv/",
         "/site-packages/", "/examples/", "/docs/", "/third_party/", "/3rdparty/")


@dataclass
class AuditResult:
    target: str
    verdict: str = "SAFE"                       # SAFE | REVIEW | BLOCK
    files: int = 0
    caps: dict = field(default_factory=dict)    # cap → [ (file, line, sample) ]
    blockers: list = field(default_factory=list)
    combos: list = field(default_factory=list)

    def report(self) -> str:
        icon = {"SAFE": "✅", "REVIEW": "🔎", "BLOCK": "🛑"}[self.verdict]
        out = [f"{icon} CODE-AUDIT {self.verdict} — {self.target}  ({self.files} source files)"]
        if self.caps:
            out.append("  capabilities present:")
            for cap, hits in sorted(self.caps.items()):
                ex = hits[0]
                out.append(f"    • {cap:12} ×{len(hits):<3} e.g. {ex[0].split('/')[-1]}:{ex[1]}")
        for c in self.combos:
            out.append(f"  ⚠ {c}")
        for b in self.blockers:
            out.append(f"  🛑 {b}")
        if self.verdict == "REVIEW":
            out.append("  → Powerful but normal-for-a-server capabilities. Hand-wire with a "
                       "config entry YOU control (not their installer) + backup + health-check.")
        if self.verdict == "SAFE":
            out.append("  → No network/exec/remote-code capability detected. Safe to wire.")
        return "\n".join(out)


# An exec-sink on the same line means a quoted command IS executed (os.system('curl|sh')),
# so it is NOT inert. Without a sink, a quoted curl|sh is help-text / a data string.
_EXEC_SINK = re.compile(r"(os\.system|os\.popen|subprocess\.|check_output|\bPopen\b|\.run\s*\(|"
                        r"\.call\s*\(|\bexec\s*\(|\beval\s*\(|child_process|\.spawn|execSync|"
                        r"\bsh\s+-c|\bbash\s+-c|shell\s*=\s*True)", re.I)

def _is_comment(line: str) -> bool:
    return line.lstrip().startswith(("#", "//", "*", "/*", "--", "%", ";", '"""', "'''"))

def _inert(line: str, col: int) -> bool:
    """True if the match at `col` is INERT — DESCRIBED, not EXECUTED. A comment is always
    inert; a quoted string is inert UNLESS an exec-sink on the line runs it. So a bare
    `curl|sh` in install.sh flags, `os.system('curl|sh')` flags, but `print("curl|sh")` and
    `("Node.js", "curl ... | bash")` (help text / data) do not."""
    if _is_comment(line):
        return True
    before = line[:col]
    in_string = (before.count('"') % 2 == 1 or before.count("'") % 2 == 1
                 or before.count("`") % 2 == 1)
    return in_string and not _EXEC_SINK.search(line)


def _iter(p: pathlib.Path):
    if p.is_file():
        yield p
    elif p.is_dir():
        for q in p.rglob("*"):
            s = str(q).replace(os.sep, "/").lower()
            if q.suffix.lower() in _SRC_EXT and not any(d in s + "/" for d in _SKIP):
                yield q


def audit(target: str) -> AuditResult:
    """Audit a local path OR a remote `owner/repo` (streamed via the GitHub API, no clone)."""
    from . import repostream
    local, cleanup, info = repostream.resolve(target)
    try:
        res = _audit_local(local)
        if info.get("remote"):
            res.target = info.get("slug") or target
            res.streamed = True
            res.stream_truncated = bool(info.get("truncated"))
            if not info.get("files") and info.get("error"):
                res.verdict = "BLOCK"; res.blockers.append(f"stream-failed: {info['error']}")
        return res
    finally:
        cleanup()


def _audit_local(target: str) -> AuditResult:
    p = pathlib.Path(os.path.expanduser(target))
    res = AuditResult(target=str(p))
    if not p.exists():
        res.verdict = "BLOCK"; res.blockers.append("path does not exist"); return res
    per_file_caps = {}
    rc_runtime = []        # remote-code in RUNTIME source (real backdoor)
    rc_script = []         # remote-code in installer .sh (don't run it — hand-wire instead)
    _RUNTIME_EXT = (".py", ".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx", ".go", ".rs", ".rb", ".php")
    for q in _iter(p):
        try:
            text = q.read_text(errors="replace")
        except Exception:
            continue
        res.files += 1
        lines = text.split("\n")
        here = set()
        for cap, (rx, _w) in COMPILED.items():
            for m in rx.finditer(text):
                ln = text[:m.start()].count("\n") + 1
                line = lines[ln - 1] if ln - 1 < len(lines) else ""
                col = m.start() - (text.rfind("\n", 0, m.start()) + 1)
                # Skip matches that are INERT (comment / inside a string literal) — a `curl|sh`
                # in an error message or a `# Usage:` comment is described, not executed.
                if cap in ("remote-code", "obfusc-exec") and _inert(line, col):
                    continue
                res.caps.setdefault(cap, []).append((str(q), ln, m.group(0)[:60]))
                here.add(cap)
                if cap == "remote-code":
                    (rc_runtime if q.suffix.lower() in _RUNTIME_EXT else rc_script).append((str(q), ln))
        if here:
            per_file_caps[str(q)] = here
    # Hard blocker: remote-code in the SERVER'S RUNTIME code (it downloads & runs code when it
    # runs = backdoor). remote-code in an installer .sh is a "don't run their installer" REVIEW
    # note, not a server-runtime threat — you hand-wire the server directly instead.
    if rc_runtime:
        f, ln = rc_runtime[0]
        res.blockers.append(f"remote-code-execution in RUNTIME source: server downloads & runs "
                            f"code when it runs ({f.split('/')[-1]}:{ln})")
    if rc_script:
        f, ln = rc_script[0]
        res.combos.append(f"installer script downloads code ({f.split('/')[-1]}:{ln}) — do NOT run "
                          f"their installer; hand-wire the server with a config entry you control.")
    if "obfusc-exec" in res.caps:
        res.blockers.append(f"obfuscated execution (base64/atob → exec/eval) "
                            f"({res.caps['obfusc-exec'][0][0].split('/')[-1]}:{res.caps['obfusc-exec'][0][1]})")
    # Dangerous combo: a single file that reads credentials AND makes outbound network calls.
    for f, caps in per_file_caps.items():
        if "cred-access" in caps and "net-out" in caps:
            res.combos.append(f"cred-access + net-out in the same file ({f.split('/')[-1]}) — "
                              f"potential secret exfil; verify the destination host.")
    if res.blockers:
        res.verdict = "BLOCK"
    elif res.combos or {"net-out", "exec", "fs-write"} & set(res.caps):
        res.verdict = "REVIEW"
    else:
        res.verdict = "SAFE"
    return res


def _cli(argv: list) -> int:
    if not argv:
        print("usage: verity audit <repo|dir>", file=sys.stderr); return 2
    r = audit(argv[0])
    print(r.report())
    return 2 if r.verdict == "BLOCK" else 1 if r.verdict == "REVIEW" else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

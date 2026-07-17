#!/usr/bin/env python3
"""verity fixed — a known-fixed-bugs ledger so plans can't silently reintroduce them.

Applied from Sean Kochel's Fable-5 workflow ("maintain a ledger of bugs you've already fixed;
gate plans against it so the agent can't reintroduce a solved problem"). VERITY already logs every
gate decision; this adds the *forward* direction: record a fix once, then `check` any plan/diff/draft
against the ledger before execution — if it looks like it would reintroduce a fixed bug, the gate
fires (exit 2), the same anti-quit / durable-verdict posture the harness uses everywhere else.

  verity fixed record "<id>" "<what was fixed>" [--pattern "<regex that signals a regression>"]
  verity fixed check  "<plan or diff text>"     # exit 2 if it risks reintroducing a fixed bug
  verity fixed list | forget <id>

Ledger: $VERITY_BROKER_HOME/regression-ledger.json (default ~/.verity). Portable, stdlib-only.
"""
from __future__ import annotations
import json, os, re, sys, time, pathlib

HOME = pathlib.Path(os.environ.get("VERITY_BROKER_HOME", str(pathlib.Path.home() / ".verity")))
LEDGER = HOME / "regression-ledger.json"


def _load():
    try: return json.loads(LEDGER.read_text())
    except Exception: return {}

def _save(o):
    LEDGER.parent.mkdir(parents=True, exist_ok=True); LEDGER.write_text(json.dumps(o, indent=1))


def record(bug_id, desc, pattern=""):
    led = _load()
    # default detection pattern = the distinctive words of the description
    if not pattern:
        words = [w for w in re.findall(r"[A-Za-z_][\w.-]{3,}", desc)][:6]
        pattern = r"\b(" + "|".join(re.escape(w) for w in words) + r")\b" if words else re.escape(desc[:40])
    led[bug_id] = {"desc": desc, "pattern": pattern, "recorded": int(time.time())}
    _save(led); print(f"✓ recorded fixed bug '{bug_id}' — regressions matching /{pattern}/ will flag")


def check(text):
    led = _load()
    if not led:
        print("[fixed] ledger empty — nothing to guard against"); return 0
    hits = []
    for bid, r in led.items():
        try:
            m = re.findall(r["pattern"], text, re.I)
        except re.error:
            m = [r["desc"][:20]] if r["desc"][:20].lower() in text.lower() else []
        if m: hits.append((bid, r, len(m)))
    if not hits:
        print(f"[fixed] ✅ clear — no overlap with {len(led)} known-fixed bugs"); return 0
    print(f"🛑 REGRESSION RISK — this plan overlaps {len(hits)} already-fixed bug(s):")
    for bid, r, n in hits:
        print(f"  • {bid} ({n} hit{'s' if n>1 else ''}): {r['desc'][:100]}")
    print("  → Confirm the plan does NOT reintroduce these before executing.")
    return 2


def lst():
    led = _load()
    if not led: print("(regression ledger empty)"); return
    for bid, r in led.items():
        print(f"  {bid:<24} {r['desc'][:80]}")

def forget(bug_id):
    led = _load()
    if led.pop(bug_id, None) is not None: _save(led); print(f"forgot {bug_id}")
    else: print(f"{bug_id} not in ledger")


def _cli(argv):
    if not argv: print(__doc__); return 0
    c, rest = argv[0], argv[1:]
    if c == "record" and len(rest) >= 2:
        pat = rest[rest.index("--pattern")+1] if "--pattern" in rest else ""
        record(rest[0], rest[1], pat)
    elif c == "check" and rest: return check(" ".join(x for x in rest if not x.startswith("--")))
    elif c == "list": lst()
    elif c == "forget" and rest: forget(rest[0])
    else: print(__doc__); return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

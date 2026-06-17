#!/usr/bin/env python3
"""Regression test for the deterministic STOP-guard (hooks/stop_guard.py) — proves the enforcement that
makes the catchable lapses mechanically unrepeatable. Run from the repo root: python3 tests/test_stop_guard.py

Each case feeds the hook a synthetic transcript (last assistant text + recent tool actions) and asserts
BLOCK vs ALLOW. Uses unique session-ids so the per-session block-cap never interferes."""
import json, os, subprocess, tempfile, sys, time

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "stop_guard.py")


def run(text, actions, sid):
    lines = [json.dumps({"type": "assistant", "message": {"role": "assistant",
             "content": [{"type": "tool_use", "name": a, "input": {}}]}}) for a in actions]
    lines.append(json.dumps({"type": "assistant", "message": {"role": "assistant",
                 "content": [{"type": "text", "text": text}]}}))
    p = tempfile.mktemp(suffix=".jsonl")
    open(p, "w").write("\n".join(lines))
    out = subprocess.run([sys.executable, HOOK],
                         input=json.dumps({"transcript_path": p, "session_id": sid}),
                         capture_output=True, text=True).stdout.strip()
    return "BLOCK" if out and '"block"' in out else "ALLOW"


CASES = [
    # (name, last_text, recent_actions, expected)
    ("not-ready→workaround, NO investigation",
     "the publisher is not authenticated, so the clean path is to post through the browser", ["Edit"], "BLOCK"),
    ("not-ready but ran discovery (accounts)",
     "the publisher is not authenticated, so the clean path is to post through the browser",
     ["Bash futron-social-publish accounts"], "ALLOW"),
    ("infra negative, NO logs/repair/search",
     "the model backend is down — it's a global outage, nothing we can do", ["Edit"], "BLOCK"),
    ("infra negative AFTER reading logs",
     "the backend is down", ["Bash tail -f service.log", "Bash launchctl kickstart -k svc"], "ALLOW"),
    ("defer to human, NO automation attempt",
     "only you can log in to do this, you'll have to do it manually", ["Read"], "BLOCK"),
    ("publish to X, NO screening",
     "Posting all of these to your X account now", ["Bash open x.com"], "BLOCK"),
    ("publish AFTER brand screening",
     "Posting all of these to your X account now", ["Bash futron-sets-review --panel marketing"], "ALLOW"),
    ("normal completion",
     "The build passed and tests are green. Committed and pushed.", ["Bash git commit"], "ALLOW"),
]


def main():
    uniq = str(int(time.time()))
    fails = 0
    for i, (name, text, acts, exp) in enumerate(CASES):
        got = run(text, acts, f"t{uniq}_{i}")
        ok = got == exp
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:42} → {got} (expect {exp})")
    print(f"\n{len(CASES)-fails}/{len(CASES)} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

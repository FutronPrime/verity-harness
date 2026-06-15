#!/usr/bin/env python3
"""VERITY stop-guard — a MECHANICAL forcing function against LLM overconfidence.

The injected gate text is advisory: the model can rationalize past it (and did — 2026-06-15, a
QA backend was called a "global outage" without reading one log line). This hook fires on a CODE
condition instead: when an agent tries to END ITS TURN on a premature negative, it BLOCKS the stop
and sends the agent back to investigate. No opt-out, no goodwill required — the VERITY thesis applied
to the model's own reasoning.

Wired as a Claude Code `Stop` / `SubagentStop` hook. Input: hook JSON on stdin
(transcript_path, stop_hook_active). Output: exit 0 to allow, or {"decision":"block","reason":...}
to force continuation. Loop-safe (honors stop_hook_active + a per-session block cap).

Catches TWO failure modes, only when the evidence trail is missing:
  1) UNVERIFIED INFRA/FEASIBILITY NEGATIVE — "it's down / broken / can't be fixed / impossible /
     global outage / environmental" with NO sign of: reading logs, attempting repair/restart, or
     searching the error. → forces logs → repair → search.
  2) PREMATURE DEFERRAL — "only you can / you'll have to / requires manual" with NO sign of an
     automation attempt (CUA / browser-act / computer-use / openclick / playwright). → forces a
     real automation attempt before handing the task back to the human (R55: automate-before-defer).
"""
import json
import os
import re
import sys

MAX_BLOCKS = 2  # per session — never trap the agent in an infinite loop

NEG = re.compile(r"""(?ix)
    \b(it'?s\s+(down|broken|unavailable)|can'?t\s+be\s+(fixed|done)|cannot\s+be\s+(fixed|done)
    | not\s+(possible|fixable|feasible) | unfixable | impossible | no\s+way\s+to
    | global\s+outage | environmental\s+(outage|issue|problem) | nothing\s+(i|we)\s+can\s+do
    | out\s+of\s+(my|our)\s+control | (model|backend|service|api)\s+is\s+(down|unavailable))
""")
DEFER = re.compile(r"""(?ix)
    \b(only\s+you\s+can | you'?ll\s+have\s+to | you\s+(will\s+)?(need|have)\s+to\s+(do|run|manually)
    | requires?\s+(you|your|manual|human|a\s+human) | needs?\s+(you|your\s+input)
    | i\s+can'?t\s+(do|run|access)\s+(this|that|it)\s+(myself|for\s+you) | hand(ing)?\s+(this|it)\s+(back|off)\s+to\s+you)
""")
# evidence the negative was earned
INVESTIGATED = re.compile(r"""(?ix)
    (\btail\b|\bcat\b|\bgrep\b|\bless\b|\.log\b|read.{0,12}log|logs?\b
    | restart|kickstart|reboot|refresh|reinstall|launchctl|systemctl|--force|repair|bounce
    | websearch|web_search|search_|curl\s+http|https?://|github|reddit|stackoverflow|google|youtube|brave|ddgs
    | futron-scrape|x-read|fetch_tweet|agent-reach)
""")
# evidence an automation attempt was made before deferring
AUTOMATION = re.compile(r"""(?ix)
    (cua|browser-act|browser_act|computer-use|computer_use|openclick|playwright|claude-in-chrome
    | futron-claw|axiom|osascript|cdp|oauth-cdp|applescript|--browser-login|automate)
""")


def _tail(path, n=240):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.readlines()[-n:]
    except Exception:
        return []


def _parse(lines):
    """Return (last_assistant_text, recent_actions_blob)."""
    last_text, actions = "", []
    for ln in lines:
        try:
            o = json.loads(ln)
        except Exception:
            continue
        msg = o.get("message") or o
        role = o.get("type") or msg.get("role")
        content = msg.get("content")
        if isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and role in ("assistant", None):
                    last_text = b.get("text", "") or last_text
                if b.get("type") == "tool_use":
                    actions.append((b.get("name", "") or "") + " " +
                                   json.dumps(b.get("input", {}))[:600])
                if b.get("type") == "tool_result":
                    actions.append(json.dumps(b.get("content", ""))[:300])
        elif isinstance(content, str) and role == "assistant":
            last_text = content or last_text
    return last_text, "\n".join(actions[-30:])


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # malformed input → never block
    if data.get("stop_hook_active"):
        sys.exit(0)  # we already nudged once this stop-cycle — don't loop
    tpath = data.get("transcript_path", "")
    sid = data.get("session_id", "x")
    if not tpath or not os.path.exists(tpath):
        sys.exit(0)

    text, actions = _parse(_tail(tpath))
    if not text:
        sys.exit(0)
    tail_text = text[-1600:]  # the conclusion the agent is stopping on

    neg = bool(NEG.search(tail_text))
    defer = bool(DEFER.search(tail_text))
    if not (neg or defer):
        sys.exit(0)

    investigated = bool(INVESTIGATED.search(actions))
    automated = bool(AUTOMATION.search(actions))

    reason = None
    if neg and not investigated:
        reason = ("VERITY stop-guard: you're concluding something is DOWN / BROKEN / IMPOSSIBLE / an "
                  "outage — but the transcript shows no investigation. Before that negative can stand "
                  "you MUST, in order: (1) READ the component's logs, (2) ATTEMPT its repair/restart/"
                  "refresh, (3) SEARCH the exact error (GitHub/Reddit/X/YouTube/Google/SO). "
                  "'Errored/empty/timed-out' is a symptom, not a diagnosis. Go find the root cause, "
                  "then continue. (If you HAVE already done all three and the negative is truly earned, "
                  "state the evidence explicitly and stop.)")
    elif defer and not automated:
        reason = ("VERITY stop-guard: you're handing this back to the user ('only you can…') without "
                  "trying the automation stack. Per automate-before-defer: ATTEMPT it first — CUA "
                  "(futron-claw), browser-act, computer-use, Claude-in-Chrome, openclick, Playwright, "
                  "or a CDP/oauth module. Defer ONLY at the genuine human boundary (password entry, "
                  "2FA, CAPTCHA, biometrics, payment) — and say which one you actually hit.")
    if not reason:
        sys.exit(0)

    # per-session block cap → never trap the agent
    cnt_dir = os.path.expanduser("~/.verity-harness/guard")
    os.makedirs(cnt_dir, exist_ok=True)
    cnt_file = os.path.join(cnt_dir, f"{re.sub(r'[^A-Za-z0-9]', '_', sid)}.cnt")
    n = 0
    try:
        n = int(open(cnt_file).read().strip() or "0")
    except Exception:
        pass
    if n >= MAX_BLOCKS:
        sys.exit(0)  # honored it enough times this session; let the human decide
    open(cnt_file, "w").write(str(n + 1))

    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


if __name__ == "__main__":
    main()

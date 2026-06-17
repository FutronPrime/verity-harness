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
    | out\s+of\s+(my|our)\s+control | (model|backend|service|api)\s+is\s+(down|unavailable)
    | (is|are|isn'?t|aren'?t|not)\s+(currently\s+)?(authenticated|configured|set\s*up|installed|wired|reachable|available)
    | no\s+(api\s+)?(tokens?|creds?|credentials?|auth\b) | doesn'?t\s+exist
    | (credentials?|creds?|tokens?|account)\s+(are|is)?\s*missing | missing\s+(credentials?|creds?|tokens?))
""")
# A "the tool isn't ready, so I'll just work around it" REDIRECT — my most common quiet lapse: reaching
# for a fallback (browser, manual, a different tool) instead of querying the tool's own status first.
WORKAROUND = re.compile(r"""(?ix)
    (the\s+(clean|only|right|best|simplest)\s+(path|way|option)\s+is
    | so\s+(the\s+clean\s+|i'?ll\s+|we'?ll\s+|i\s+have\s+to\s+|we\s+have\s+to\s+).{0,24}(use|post\s+through|go\s+through|via\s+the\s+browser|do\s+it\s+manually)
    | instead\s+(i'?ll|we'?ll|use|let'?s) | fall\s*back\s+to | work\s*around
    | (use|do|go|post|try|switch)\b[^.]{0,40}\binstead\b)
""")
DEFER = re.compile(r"""(?ix)
    \b(only\s+you\s+can | you'?ll\s+have\s+to | you\s+(will\s+)?(need|have)\s+to\s+(do|run|manually)
    | requires?\s+(you|your|manual|human|a\s+human) | needs?\s+(you|your\s+input)
    | i\s+can'?t\s+(do|run|access)\s+(this|that|it)\s+(myself|for\s+you) | hand(ing)?\s+(this|it)\s+(back|off)\s+to\s+you)
""")
# evidence the negative was earned — logs/repair/search OR DISCOVERY (querying the tool's own status,
# health, accounts, help, the system directory, or creds — the check that satisfies a "not ready" claim).
INVESTIGATED = re.compile(r"""(?ix)
    (\btail\b|\bcat\b|\bgrep\b|\bless\b|\.log\b|read.{0,12}log|logs?\b
    | restart|kickstart|reboot|refresh|reinstall|launchctl|systemctl|--force|repair|bounce
    | websearch|web_search|search_|curl\s+http|https?://|github|reddit|stackoverflow|google|youtube|brave|ddgs
    | futron-scrape|x-read|fetch_tweet|agent-reach
    | \baccounts\b|\bhealth\b|\bstatus\b|--list|--query|--help|print-disabled|defaults\s+read
    | futron-system-directory|command\s+-v|which\s+\w|grep[^\n]{0,40}(cred|token|account|auth))
""")
# evidence an automation attempt was made before deferring
AUTOMATION = re.compile(r"""(?ix)
    (cua|browser-act|browser_act|computer-use|computer_use|openclick|playwright|claude-in-chrome
    | futron-claw|axiom|osascript|cdp|oauth-cdp|applescript|--browser-login|automate)
""")
# OUTWARD PUBLISH (post to public) — and the SCREENING that must precede it (brand/persona gate).
PUBLISH = re.compile(r"""(?ix)
    (social-publish\s+post                    # the actual post subcommand (NOT 'accounts'/'health' discovery)
    | \bpost(ing|ed)?\s+(to|the|all|it|this)\b | \btweet(ing|ed)?\b | publish(ing|ed)\s+(to|the|this|it)
    | compose.{0,20}(tweet|post) | x\.com.{0,30}post | (reddit|instagram|facebook|linkedin)\s+post)
""")
SCREENED = re.compile(r"""(?ix)
    (sets-review|test-screening|soul-personality-audit|persona[\s_-]*(screen|audit|panel)|s\.e\.t\.s|screening)
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

    neg = bool(NEG.search(tail_text)) or bool(WORKAROUND.search(tail_text))
    defer = bool(DEFER.search(tail_text))
    publish = bool(PUBLISH.search(tail_text)) or bool(PUBLISH.search(actions))
    if not (neg or defer or publish):
        sys.exit(0)

    investigated = bool(INVESTIGATED.search(actions))
    automated = bool(AUTOMATION.search(actions))
    screened = bool(SCREENED.search(actions)) or bool(SCREENED.search(text))

    reason = None
    if neg and not investigated:
        reason = ("VERITY stop-guard: you're concluding something is DOWN / BROKEN / IMPOSSIBLE / NOT "
                  "AUTHENTICATED / NOT CONFIGURED — or reaching for a WORKAROUND — but the transcript "
                  "shows no investigation. Before that stands you MUST, in order: for infra → (1) READ "
                  "logs, (2) ATTEMPT repair/restart/refresh, (3) SEARCH the exact error. For 'the tool "
                  "isn't ready / I'll just use X instead' → QUERY THE TOOL'S OWN STATUS FIRST (its "
                  "`accounts`/`health`/`status`/`--list`, and `futron-system-directory --query`) — the "
                  "system very likely already has the solution. 'Errored/empty/not-configured' is a "
                  "symptom, not a diagnosis. Investigate, then continue. (If you HAVE already checked and "
                  "the negative is truly earned, state the specific evidence and stop.)")
    elif publish and not screened:
        reason = ("VERITY stop-guard: you're about to PUBLISH / POST outward-facing content without "
                  "running the required BRAND PERSONA SCREENING. Per protocol, run "
                  "`futron-sets-review --panel marketing --text \"<copy>\"` FIRST and confirm it passes, "
                  "and confirm you're posting to the CORRECT account(s) (query `futron-social-publish "
                  "accounts`). Public posts are irreversible — screen, route, then post.")
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

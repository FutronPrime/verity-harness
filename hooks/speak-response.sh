#!/usr/bin/env bash
# VERITY — speak-response Stop hook (Claude Code).
# Voices YOUR Claude Code assistant's replies in the selected persona, so VERITY is an I/O shell over the
# agent you ALREADY run (not a separate chatbot). On each turn it reads the last assistant message from the
# transcript, summarises it into a short persona line, and speaks it.
#
# INSTALL (Claude Code): add to ~/.claude/settings.json under "hooks":
#   "Stop": [ { "matcher": "", "hooks": [
#     { "type": "command", "command": "/ABSOLUTE/PATH/TO/verity-harness/hooks/speak-response.sh" } ] } ]
#
# Other agents (Codex/Gemini/any CLI that prints replies): use `verity voice pipe <cmd>` instead — it wraps
# the command and voices its output, no transcript needed.
#
# Requires: `verity` on PATH (or set VERITY_CMD), the persona+voice configured (verity voice status), and a
# TTS engine reachable. Honors your speak mode; stays silent on empty/non-text turns.
set -uo pipefail

VERITY_CMD="${VERITY_CMD:-python3 -m verity}"
TRANSCRIPT_DIR="${CLAUDE_TRANSCRIPT_DIR:-$HOME/.claude/projects}"

# Newest transcript = the active conversation.
LATEST="$(find "$TRANSCRIPT_DIR" -name '*.jsonl' -type f -maxdepth 4 2>/dev/null | xargs ls -t 2>/dev/null | head -1)"
[ -z "$LATEST" ] && exit 0

# Extract the last assistant text block (Claude Code JSONL: {message:{role,content:[{type:text,text}]}}).
RESPONSE="$(tail -200 "$LATEST" 2>/dev/null | python3 -c "
import sys, json
last = ''
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        e = json.loads(line); m = e.get('message', e)
        if m.get('role') != 'assistant':
            continue
        c = m.get('content', '')
        if isinstance(c, str):
            t = c.strip()
        else:
            t = ' '.join(b.get('text','') for b in c if isinstance(b, dict) and b.get('type')=='text').strip()
        if t:
            last = t
    except Exception:
        pass
print(last[:4000])
" 2>/dev/null)"

[ "${#RESPONSE}" -lt 2 ] && exit 0

# Summarise into a persona line and speak it (best-effort; never block the agent).
$VERITY_CMD voice say --tldr "$RESPONSE" >/dev/null 2>&1 &
exit 0

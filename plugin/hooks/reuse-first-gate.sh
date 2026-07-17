#!/usr/bin/env bash
# VERITY reuse-first-gate — a PreToolUse (Write|Edit) hook that BLOCKS creation of a NEW
# tool/script/daemon until the agent has demonstrably searched for an existing one first.
#
# Why: agents chronically rebuild tools that already exist (a Rule-17 / DRY failure). Docs and
# memory don't fix it — the agent can ignore them. A hard execution-time gate cannot be ignored.
#
# Behavior:
#   • Fires only on Write|Edit.
#   • Guards ONLY the creation of a NEW file (does not exist yet) matching REUSE_GATE_GLOBS.
#   • Allows the write if the recent transcript shows a prior-art search (REUSE_GATE_EVIDENCE).
#   • Otherwise emits {"decision":"block","reason":...} (exit 0) telling the agent to search first.
#   • Fail-open: malformed input / missing deps → allow (never wedge the agent).
#
# Config (env, all optional):
#   REUSE_GATE_GLOBS      ':'-separated case-globs of guarded paths.
#                         default: "*/bin/*:*/.local/bin/*:*LaunchAgents/*.plist"
#   REUSE_GATE_EVIDENCE   extended-regex proving a prior search happened.
#                         default matches system-directory queries, `ls .../bin`, greps, memory search.
#   CLAUDE_PROJECTS_DIR   transcript dir. default: "$HOME/.claude/projects"
#
# Wire in ~/.claude/settings.json:
#   {"hooks":{"PreToolUse":[{"matcher":"Write|Edit",
#     "hooks":[{"type":"command","command":"/path/to/reuse-first-gate.sh","timeout":5}]}]}}
set -euo pipefail

PAYLOAD=$(cat)
GLOBS="${REUSE_GATE_GLOBS:-*/bin/*:*/.local/bin/*:*LaunchAgents/*.plist}"
EVIDENCE_REGEX="${REUSE_GATE_EVIDENCE:-(system-directory.*--query|discover.*--prompt|ls .*/bin|grep .*/bin|grep .*-r|find .*bin|which |memory_search|brain_query|rg .*bin)}"
PROJECTS_DIR="${CLAUDE_PROJECTS_DIR:-$HOME/.claude/projects}"

_field() { printf '%s' "$PAYLOAD" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    if '$1'=='file_path': print((d.get('tool_input') or {}).get('file_path','') or '')
    else: print(d.get('$1','') or '')
except Exception: print('')" 2>/dev/null; }

TOOL_NAME=$(_field tool_name)
FILE_PATH=$(_field file_path)
SESSION_ID=$(_field session_id)

case "$TOOL_NAME" in Write|Edit) ;; *) exit 0 ;; esac
[ -z "$FILE_PATH" ] && exit 0

# Guard only NEW files matching a guarded glob (editing an existing tool is always fine).
SHOULD_GUARD=0
IFS=':' read -ra _globs <<< "$GLOBS"
for g in "${_globs[@]}"; do
    # shellcheck disable=SC2254
    case "$FILE_PATH" in $g) [ ! -e "$FILE_PATH" ] && SHOULD_GUARD=1 ;; esac
done
[ "$SHOULD_GUARD" -eq 0 ] && exit 0

# Look for prior-art search evidence in recent transcripts.
EVIDENCE=0
if [ -n "$SESSION_ID" ] && [ -d "$PROJECTS_DIR" ]; then
    tf=$(find "$PROJECTS_DIR" -name "${SESSION_ID}.jsonl" -type f 2>/dev/null | head -1)
    if [ -n "$tf" ]; then
        n=$(tail -800 "$tf" 2>/dev/null | grep -ciE "$EVIDENCE_REGEX" || true)
        [ "${n:-0}" -gt 0 ] && EVIDENCE=1
    fi
fi
if [ "$EVIDENCE" -eq 0 ] && [ -d "$PROJECTS_DIR" ]; then
    while IFS= read -r tf; do
        [ -z "$tf" ] && continue
        n=$(tail -800 "$tf" 2>/dev/null | grep -ciE "$EVIDENCE_REGEX" || true)
        if [ "${n:-0}" -gt 0 ]; then EVIDENCE=1; break; fi
    done < <(find "$PROJECTS_DIR" -name "*.jsonl" -type f -mmin -15 2>/dev/null | head -25)
fi

[ "$EVIDENCE" -eq 1 ] && exit 0

export FILE_PATH
python3 <<'PY'
import json, os
target = os.environ.get("FILE_PATH", "")
msg = (
    "REUSE-FIRST GATE — you're about to CREATE A NEW TOOL/SCRIPT but haven't shown you searched "
    "for an existing one. Most 'new' tools already exist; rebuilding wastes work and forks logic.\n"
    f"\nNew file: {target}\n\n"
    "Before creating it, run ONE prior-art search (the search itself unlocks this gate):\n"
    "  • your system/tool directory query (e.g. `<sysdir> --query \"<keywords>\"`)\n"
    "  • ls <tooldir>/bin | grep -iE \"<keywords>\"\n"
    "  • grep -r \"<keywords>\" <tooldir>\n\n"
    "If it already exists, USE IT. If genuinely none exists, re-run this write.\n"
)
print(json.dumps({"decision": "block", "reason": msg}))
PY
exit 0

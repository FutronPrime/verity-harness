# VERITY Discipline — Claude Code plugin

Three discipline gates that stop the most expensive AI-coding-agent failure modes:

1. **Reuse-first gate** (hook) — mechanically BLOCKS creating a new tool/script/daemon until the
   agent has searched for an existing one. Kills the "rebuild what already exists" tax.
2. **Search-before-concluding** (skill) — the agent must investigate (logs → docs → web) before
   asserting a negative ("can't / broken / not possible").
3. **Safe-install** (skill + `/verity-scan` command) — vet third-party repos/MCP servers for
   prompt-injection and install-time code execution before running them.

## Install
```
/plugin marketplace add FutronPrime/verity-harness
/plugin install verity-discipline
```
Or point your client at `plugin/.claude-plugin/plugin.json` in this repo.

## What's inside
- `hooks/reuse-first-gate.sh` — PreToolUse(Write|Edit) gate. Env-configurable:
  `REUSE_GATE_GLOBS`, `REUSE_GATE_EVIDENCE`, `CLAUDE_PROJECTS_DIR`. Fail-open. 12 offline tests
  (`tests/test_reuse_gate.py`), validated 56/56 across repeated runs.
- `skills/verity-discipline/SKILL.md` — the three-gate playbook.
- `commands/verity-scan.md` — `/verity-scan` ingest/repo safety scan.
- `verity_scan.py` — the prompt-injection / unsafe-instruction scanner.

## Why it pays for itself
Agents waste tokens rebuilding tools that exist, hallucinate "can't" instead of researching, and
run unvetted third-party code. Each gate turns a recurring, expensive failure into a hard stop.

MIT licensed. Part of the [VERITY harness](https://github.com/FutronPrime/verity-harness).

# Safe-to-install: proving a third-party server is safe, then wiring it reversibly

The proactive answer to a boundary that *feels* like a wall (R62). "Auto-wiring untrusted
MCP servers loads code whose tool-descriptions inject into every session" is a real risk —
but it's a **design problem with a safe solution**, not a stop sign. The solution is a
two-layer proof plus a reversible install, so an agent can install **independently** instead
of either stopping or recklessly running a stranger's installer.

## The two-layer safety proof

A repo you fetched has two distinct attack surfaces; clear both before trusting it.

| Layer | Tool | Threat it clears |
|---|---|---|
| **Instructions** | `verity vet <repo>` | The markdown that becomes your directives — `SKILL.md`, MCP tool-descriptions, fetched text. Surface-aware: instruction files strict, docs lenient on doc-noise, strict on HARD injection (role-override, hidden-unicode). → SAFE-TO-APPLY / REVIEW / BLOCK. |
| **Code** | `verity audit <repo>` | What the server actually DOES when it runs. Reports capabilities (net-out / exec / fs-write / cred-access) and BLOCKS on the real red flags: **remote-code-execution in runtime source** (`curl\|sh`, `exec`/`eval` of a fetched response), **obfuscated exec** (base64→exec), and cred+net exfil combos. → SAFE / REVIEW / BLOCK. |

Both are calibrated against real repos so they don't false-block (which would just train you to
ignore the gate): `pip/npm install`, install-curls in comments/help-strings, badges, emoji ZWJ,
and installer `.sh` scripts are all handled. A real backdoor — `exec(requests.get(url).text)`,
`os.system('curl|sh')`, base64→exec — still BLOCKs. Tests: `test_vet.py` 5/5, `test_audit.py`
10/10, `test_scan_surface.py` 9/9.

## The reversible install (`futron-mcp-safe-wire`)

You never run *their* installer (that's the actual "executing untrusted code" boundary). You
write a config entry **you** control, with a safety net around it:

```
futron-mcp-safe-wire --name <n> --repo <path> --command <cmd> --args ... [--force-reviewed]
```

1. **GATE** — runs `verity vet` + `verity audit`; BLOCK ⇒ abort, REVIEW ⇒ require `--force-reviewed`
   (you read the report first).
2. **BACKUP** — timestamped copy of `~/.claude.json` (instant rollback point).
3. **WRITE** — adds a minimal `mcpServers` entry you specified (command/args you control).
4. **VALIDATE** — the new config must round-trip as valid JSON.
5. **HEALTH-CHECK** — spawns the server and does a real MCP `initialize` handshake; a server that
   doesn't come up cleanly fails here.
6. **ROLLBACK** — any failure restores the backup. The config is never left broken or half-wired.

The "untrusted install" boundary is now a **backed-up, gated, health-checked, instantly-reversible
operation** — proven both ways: a non-responding server was auto-rolled-back with the config left
pristine, and a real install (IBM's `docling-mcp`) went **GREEN end-to-end** — backup → write our
own entry → JSON-validate → live MCP `initialize` handshake confirmed → registered. The obstacle
"it needs a build/install" (R62) is solved by *doing the install*, then wiring the verified entry
ourselves — never running their installer.

## Why this is the R62 template
A boundary with a safe engineerable workaround is a design problem, not a stop. The only true
stops are genuine human gates (password / 2FA / payment / account-creation / destructive /
live-money). Everything else: build the system that makes it safe, then execute. See
[docs/PROVENANCE.md](PROVENANCE.md) row 5.

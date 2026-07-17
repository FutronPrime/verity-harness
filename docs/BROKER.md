# `verity broker` — Just-In-Time Capability Broker

Agents accrete a long tail of repos and skills they need *sometimes*. Installing them all is how you
get disk bloat, credential sprawl, and — worst — unvetted instruction files silently becoming your
agent's directives. The broker keeps them **reachable, not resident**: cataloged in an index, mounted
on demand, gated through `verity vet`, leased with a TTL, and auto-released (disk reclaimed) when the
task is done.

```
find → use (vet → mount → lease) → [work] → release (unmount → reclaim)
```

## Why it's safe by construction
- **Vet gate.** Nothing mounts until `verity vet <clone>` clears it. A `BLOCK` verdict (a high-risk
  instruction-surface — prompt-injection, pipe-to-shell, destructive commands) aborts the mount and
  deletes the clone. Unvetted code never becomes your directives.
- **Stream-first.** A `repo` entry you only need to *read* never clones — it prints its
  `verity stream github <owner/repo> …` command (zero disk). Only skills / executables materialize.
- **Ephemeral.** Every mount is a TTL lease; `verity broker sweep` (wire it to cron/launchd) releases
  expired ones and reclaims the cache. The catalog is the only persistent state.
- **Credential wall.** Entries whose URL implies auth are flagged `🔑needs-key`: the code mounts, but
  the broker never fabricates or injects a key — you supply it to run live.

## Usage
```bash
verity broker add <name> <git-url> [--kind skill|repo|mcp]   # catalog an entry
verity broker find "<need>" [N]                              # search the catalog
verity broker use  <name> [--ttl 60] [--exec]               # VET → mount → lease
verity broker active                                         # what's mounted + time left
verity broker release <name>                                 # unmount + reclaim
verity broker sweep                                          # release expired (cron-safe)
```

## Config (portable — env overrides)
| Env | Purpose | Default |
|---|---|---|
| `VERITY_BROKER_HOME` | state + ephemeral cache root | `~/.verity` |
| `VERITY_BROKER_SKILLS` | where skills symlink while leased | `~/.claude/skills` if present, else `$HOME/skills` |

## Auto-release (launchd example)
```xml
<!-- ~/Library/LaunchAgents/verity.broker-sweep.plist : releases expired leases every 15 min -->
<key>ProgramArguments</key><array>
  <string>/usr/bin/python3</string><string>-m</string><string>verity</string><string>broker</string><string>sweep</string>
</array>
<key>StartInterval</key><integer>900</integer>
```

This is how you make hundreds of capabilities available to an agent **without** installing any of
them: one vetted, self-cleaning mount at the moment a task actually needs it.

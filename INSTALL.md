# Install & requirements

VERITY's core is **pure Python standard library** — ~4,600 lines, zero required third-party packages.
That's deliberate: a discipline layer you can `git clone` and trust has nothing to audit but its own
code. The only heavy resource cost is **optional** (a local model floor, or browser automation), and
you opt into those explicitly.

## Minimum requirements

| You want…                                  | Python | Disk (harness) | RAM      | Extra |
|--------------------------------------------|--------|----------------|----------|-------|
| **Cloud/API only** (an OpenRouter key, etc.) | 3.9+   | ~5 MB          | ~100 MB  | internet |
| **+ sovereign local floor** (Ollama Tier 0) | 3.9+   | + 2–16 GB weights | + 4–20 GB | [Ollama](https://ollama.com) |
| **+ browser/X-article/scrape automation**   | 3.9+   | + ~400 MB      | + ~500 MB | Playwright + Chromium |

- **Python 3.9 or newer** (uses `str.removeprefix`). No `pip install` needed for the core.
- **The harness itself is featherweight** — a thin Python process (~100 MB RSS). It does *not* run a
  model; it routes to one. So "RAM usage" is really *which tier you point it at*:
  - **Cloud tier** (OpenRouter / any OpenAI-compatible endpoint): RAM cost ≈ 0. Just a key + network.
  - **Local floor (Tier 0, optional but recommended for sovereignty):** RAM = your model's footprint.
    Default `llama3.2` (3B) ≈ 3–4 GB; a 7–8B ≈ 6–8 GB; a 26–32B ≈ 16–20 GB. This is the
    can't-be-revoked fallback — size it to what your machine has.
- **Disk:** the package is a few MB. Local model weights (if you use Tier 0) are the real disk cost
  (2–16 GB per model, stored by Ollama, not the repo).
- **OS:** macOS, Linux, or Windows (WSL recommended on Windows for the shell-tool paths).

## Install

```bash
git clone https://github.com/FutronPrime/verity-harness && cd verity-harness
python3 -m verity doctor          # sanity-check: prints tier reachability + what's configured
```

Point it at any model. Cloud (recommended baseline):

```bash
export OPENROUTER_API_KEY=sk-or-...        # or LLM_TIER1_API_KEY / OPENAI_API_KEY
python3 -m verity ask "hello"              # routes through the failover chain
```

Optional sovereign local floor (so a vendor going dark can't stop you):

```bash
# install Ollama, then:
ollama pull llama3.2                        # or any model your RAM fits
# VERITY auto-detects Ollama at 127.0.0.1:11434 as Tier 0
```

Optional automation extras (browser/X-article reading, scrape-past-blockers) — installed on demand:

```bash
python3 -m verity web-setup                 # Playwright + Chromium + cryptography (+ browser-use)
```

## Wire the gates into your coding agents

`verity autostart` injects the discipline gates into the agents you already use. **OpenAI Codex now
ships as its own desktop app (macOS/Windows) and a `codex` CLI** — VERITY wires it via `AGENTS.md`,
the same way it wires Claude Code (`CLAUDE.md` + Stop-hook) and Gemini (`GEMINI.md`):

```bash
python3 -m verity autostart                  # installs the SessionStart inject + per-agent gate files
python3 -m verity autostart --daemon         # also keep the :11500 failover proxy always-on (launchd/systemd)
```

Any OpenAI-compatible client (Codex app/CLI, Cursor, an SDK) can instead point at the proxy and inherit
failover + the overconfidence guard transparently:

```bash
python3 -m verity.server                      # → http://127.0.0.1:11500/v1
export OPENAI_BASE_URL=http://127.0.0.1:11500/v1
```

## Verify it works

```bash
python3 -m verity doctor                      # tiers reachable?
python3 -m verity eval                        # the A/B proof on current-info traps (writes ledger receipts)
python3 -m verity proof                       # read those receipts back
```

## Optional: NotebookLM deep-research (best-effort enrichment, not required)

For source-grounded research over many docs/videos, stand up a NotebookLM sidecar and set
`NOTEBOOKLM_URL` — VERITY's agents will use it, falling back to web search if it's absent (it rides
Google's undocumented API, so it's never a hard dependency — see Rule 29, ≥2 backends):

```bash
pip install notebooklm-py        # teng-lin/notebooklm-py (REST+MCP)  — or jacob-bd/notebooklm-mcp-cli (`nlm`)
export NOTEBOOKLM_URL=http://127.0.0.1:<port>/<research-endpoint>
```

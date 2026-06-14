# Sovereign Harness

**Don't let any single vendor hold your AI hostage.** A 200-line, zero-dependency
harness that makes vendor outages a *non-event*: it prefers a capable cloud API
while it's available, and the instant that cloud is unreachable — outage, rate
limit, account lock, policy change, or a model pulled overnight — it **fails over
to top-tier open-weight models running on hardware you own.**

> A vendor's access can be suspended overnight. It cannot reach into open weights
> you already pulled to local disk. **That** is sovereignty.

In June 2026 a frontier model was suspended globally with ~3 days' notice. Anyone
who'd built on it as a single point of failure was stuck. This harness is the
answer to "what happens to my system if my provider vanishes at 2am?"

## Why it's different

- **Zero dependencies.** stdlib only. The thing that protects you from a vendor
  being yanked shouldn't itself break because a PyPI package was yanked. No
  `pip install`, no supply chain, no bloat.
- **Open weights are the floor.** Tier 0 runs on local [Ollama](https://ollama.com)
  — Qwen, Llama, DeepSeek, Mistral. Capable open models nobody can revoke.
- **Automatic, silent failover.** Your code calls `ask()`; the router decides
  which tier serves. A dead cloud is caught, not crashed.
- **Autonomy loop included.** A safe-by-default think→act→verify loop so the
  harness can *run tasks*, not just answer prompts.

## Architecture

```
TIER 1   cloud API (any OpenAI-compatible endpoint)   ← fast, capable, REVOCABLE
   │     OpenAI / OpenRouter / Together / your gateway    used while available
   ▼     (failover on ANY error)
TIER 0   open weights via Ollama (localhost)          ← SOVEREIGN FLOOR
         qwen2.5 / llama3.1 / deepseek on YOUR disk       un-revocable
```

## Quick start

```bash
# 1. Own your floor: pull a capable open model (one-time)
ollama pull qwen2.5:7b

# 2. (optional) point Tier 1 at any cloud API you like
export LLM_TIER1_URL="https://api.openai.com/v1"
export LLM_TIER1_MODEL="gpt-4o-mini"
export LLM_TIER1_API_KEY="sk-..."        # or set OPENAI_API_KEY

# 3. run it (no install needed — stdlib only)
git clone https://github.com/<you>/sovereign-harness && cd sovereign-harness
python3 -m sovereign_harness tiers
python3 -m sovereign_harness ask "explain failover in one sentence"

# 4. PROVE the sovereignty guarantee — kill the cloud, watch it keep working:
python3 -m sovereign_harness failover-test
#   → Tier 1 (dead port) → fails over → Tier 0 local weights → answers ✅
```

No cloud key at all? It just runs fully local on Tier 0. That's the point.

## Autonomous task loop

```bash
# plan-only (safe — shows what it WOULD do, runs nothing):
python3 -m sovereign_harness loop "summarize the .py files in this repo"

# allowlisted shell (opt-in; only safe commands execute):
python3 -m sovereign_harness loop "count the .py files here" --exec
```

```python
from sovereign_harness import ask, run_goal, AllowlistShellExecutor
r = ask("explain X", system="be concise")
print(r.text, "←", r.tier)              # know which tier served you
run_goal("audit this repo's TODOs", executor=AllowlistShellExecutor())
```

## Use it from Claude Code / Cursor / any agent

Point your agent's model endpoint at this router (run it behind a tiny
OpenAI-compatible shim, or import `ask()` directly) and your agent inherits the
failover floor: when the upstream provider is down, the agent keeps running on
local weights instead of dying.

## Safety posture (non-negotiable)

Models keep their guardrails. This project buys **resilience**, not lawlessness.
It does **not** bypass, disable, or circumvent any model's safety systems, and it
is **not** a tool for accessing restricted or export-controlled models. It runs
**openly available** open-weight models you are entitled to run, with their
alignment intact. Sovereignty ≠ jailbreak.

## Roadmap

- [x] Tiered failover router (proven)
- [x] Safe-by-default autonomy loop (think→act→verify)
- [ ] `secaudit`: defensive code-security review, scoped to repos you own
- [ ] Docker-sandboxed executor adapter (OpenHands / Aider)
- [ ] Streaming + token-budget routing

## License

MIT — see [LICENSE](LICENSE).

---

Built by **FUTRON / AVANI OS**. If a vendor can switch off your intelligence,
it was never yours. Run weights you own.

"""REUSE-FIRST resource library — VERITY's "infinite resource" index.

VERITY's core thesis is: don't reinvent, REUSE what exists. To make that real (not just a slogan),
the harness ships a small CURATED index of high-signal *awesome-lists* and key frameworks. Each
awesome-list is itself a doorway to hundreds of vetted tools — so a tiny seed gives effectively
"infinite" reach: the agent matches a goal to the right list here, then fetches that list LIVE
(`fetch_list`) to find the specific existing tool, BEFORE writing anything from scratch.

Wired into `_preflight` via `reuse_hint(goal)` (same shape as tools.registry_hint): when a goal looks
like build/create/implement, it surfaces the relevant lists so the model checks them first. Pure
stdlib; live-fetch (not stale cache) sidesteps link-rot — a dead entry just returns nothing.
"""
from __future__ import annotations

# Curated, tagged. kind: "meta" (list-of-lists) | "awesome" (domain index) | "tool" (single framework).
# Keep this HIGH-SIGNAL — every entry must be worth an agent's attention. Tags drive goal-matching.
REGISTRY = [
    # ── meta: the list-of-lists (the real "infinite" root) ──────────────────────────────────────
    {"name": "sindresorhus/awesome", "url": "https://github.com/sindresorhus/awesome",
     "kind": "meta", "tags": ["awesome", "list", "index", "anything", "tools", "library"],
     "note": "The awesome-list OF awesome-lists. Start here to find a domain index for almost anything."},

    # ── agents / swarm / orchestration / project-management ─────────────────────────────────────
    {"name": "e2b-dev/awesome-ai-agents", "url": "https://github.com/e2b-dev/awesome-ai-agents",
     "kind": "awesome", "tags": ["agent", "agents", "ai", "autonomous", "orchestration", "swarm", "llm"],
     "note": "Big curated index of AI-agent frameworks & projects — scan before building agent infra."},
    {"name": "VRSEN/agency-swarm", "url": "https://github.com/VRSEN/agency-swarm",
     "kind": "tool", "tags": ["swarm", "agent", "agents", "orchestration", "roles", "multi-agent", "coordinate"],
     "note": "Multi-agent framework: typed roles + shared instructions + tool-passing. Pattern source for swarm.py role design."},
    {"name": "langchain-ai/llmanager", "url": "https://github.com/langchain-ai/llmanager",
     "kind": "tool", "tags": ["project", "manager", "pm", "triage", "routing", "approval", "decision", "agent"],
     "note": "LLM 'manager' that routes/approves requests with memory of prior decisions — pattern for a VERITY planner/triage stage."},
    {"name": "sdi2200262/agentic-project-management", "url": "https://github.com/sdi2200262/agentic-project-management",
     "kind": "tool", "tags": ["project", "manager", "pm", "plan", "task", "breakdown", "memory", "handoff", "agent"],
     "note": "Agentic PM framework (manager + worker agents, memory bank, handoffs) — patterns for swarm planning/handoff."},
    {"name": "desplega-ai/agent-swarm", "url": "https://github.com/desplega-ai/agent-swarm",
     "kind": "tool", "tags": ["swarm", "agent", "multi-agent", "background", "parallel", "orchestration"],
     "note": "Background multi-agent swarm runner — compare to VERITY's parallel sub-agents."},
    {"name": "NirDiamant/GenAI_Agents", "url": "https://github.com/NirDiamant/GenAI_Agents",
     "kind": "awesome", "tags": ["agent", "agents", "tutorial", "patterns", "rag", "planner", "pm", "examples"],
     "note": "Huge tutorial collection of agent patterns (incl. a project-manager-assistant) — borrow techniques, don't rebuild."},

    # ── python / ML / general dev ───────────────────────────────────────────────────────────────
    {"name": "vinta/awesome-python", "url": "https://github.com/vinta/awesome-python",
     "kind": "awesome", "tags": ["python", "library", "package", "stdlib", "framework", "parse", "cli", "web", "data"],
     "note": "Canonical Python library index — check before writing a util that surely already exists."},
    {"name": "lukasmasuch/best-of-ml-python", "url": "https://github.com/lukasmasuch/best-of-ml-python",
     "kind": "awesome", "tags": ["ml", "machine-learning", "python", "model", "nlp", "data", "ranked"],
     "note": "Ranked (by quality/activity) ML-Python libraries — the ranking is the value: pick maintained tools."},

    # ── CLI / TUI / terminal UX ─────────────────────────────────────────────────────────────────
    {"name": "Textualize/rich", "url": "https://github.com/Textualize/rich",
     "kind": "tool", "tags": ["cli", "terminal", "tui", "print", "format", "table", "color", "output", "progress"],
     "note": "Rich terminal output (tables/markdown/progress). Reuse for any pretty CLI before hand-rolling ANSI."},
    {"name": "Textualize/textual", "url": "https://github.com/Textualize/textual",
     "kind": "tool", "tags": ["tui", "terminal", "app", "ui", "interactive", "dashboard", "cli"],
     "note": "Build full TUI apps in Python — reuse for any interactive terminal dashboard."},
    {"name": "batrachianai/toad", "url": "https://github.com/batrachianai/toad",
     "kind": "tool", "tags": ["tui", "terminal", "agent", "coding-agent", "cli", "ui"],
     "note": "Universal TUI front-end for coding agents — relevant prior art for an agent terminal UX."},

    # ── database / data / code-quality ──────────────────────────────────────────────────────────
    {"name": "nocodb/nocodb", "url": "https://github.com/nocodb/nocodb",
     "kind": "tool", "tags": ["database", "db", "spreadsheet", "airtable", "no-code", "ui", "data"],
     "note": "Turn any SQL DB into a smart spreadsheet UI — reuse instead of building a DB admin UI."},
    {"name": "questdb/questdb", "url": "https://github.com/questdb/questdb",
     "kind": "tool", "tags": ["database", "db", "timeseries", "time-series", "metrics", "sql", "fast"],
     "note": "High-perf time-series DB — reuse for metrics/telemetry/ledger-at-scale instead of rolling your own."},
    {"name": "encode/databases", "url": "https://github.com/encode/databases",
     "kind": "tool", "tags": ["database", "db", "async", "sql", "python", "query"],
     "note": "Async DB access for Python — reuse for async SQL rather than hand-managing connections."},
    {"name": "mgramin/database-as-code", "url": "https://github.com/mgramin/database-as-code",
     "kind": "awesome", "tags": ["database", "db", "migration", "schema", "iac", "versioning", "as-code"],
     "note": "Index of database-as-code / migration / schema-versioning tools."},
    {"name": "github/codeql", "url": "https://github.com/github/codeql",
     "kind": "tool", "tags": ["security", "static-analysis", "sast", "code-quality", "vulnerability", "scan", "audit"],
     "note": "Semantic code analysis for vuln/quality — reuse for security/quality gates instead of regex linting."},

    # ── creative coding / design / dev resources ────────────────────────────────────────────────
    {"name": "terkelg/awesome-creative-coding", "url": "https://github.com/terkelg/awesome-creative-coding",
     "kind": "awesome", "tags": ["creative", "graphics", "generative", "shader", "animation", "visual", "art", "canvas"],
     "note": "Creative-coding tools/libraries (generative art, shaders, viz) — for graphics/animation work."},
    {"name": "bradtraversy/design-resources-for-developers", "url": "https://github.com/bradtraversy/design-resources-for-developers",
     "kind": "awesome", "tags": ["design", "ui", "css", "icons", "fonts", "color", "assets", "frontend", "graphics"],
     "note": "Huge index of design assets/tools (icons, fonts, color, CSS) — for any UI/branding/asset need."},

    # ── self-hosting / APIs / cheatsheets (broad reuse) ─────────────────────────────────────────
    {"name": "public-apis/public-apis", "url": "https://github.com/public-apis/public-apis",
     "kind": "awesome", "tags": ["api", "apis", "data-source", "free", "integration", "endpoint"],
     "note": "Index of free public APIs — check before scraping or paying for a data source."},
    {"name": "awesome-selfhosted/awesome-selfhosted", "url": "https://github.com/awesome-selfhosted/awesome-selfhosted",
     "kind": "awesome", "tags": ["selfhost", "self-hosted", "server", "service", "open-source", "deploy", "tool"],
     "note": "Self-hostable open-source alternatives — reuse a service instead of building/paying for SaaS."},

    # ── general dev meta-lists (broad REUSE-FIRST coverage; flagged by the triage agent) ─────────
    {"name": "codecrafters-io/build-your-own-x", "url": "https://github.com/codecrafters-io/build-your-own-x",
     "kind": "awesome", "tags": ["implement", "build", "from-scratch", "tutorial", "how", "internals", "learn"],
     "note": "Step-by-step 'build your own <X>' guides — when you DO have to build, find a proven blueprint first."},
    {"name": "DovAmir/awesome-design-patterns", "url": "https://github.com/DovAmir/awesome-design-patterns",
     "kind": "awesome", "tags": ["design", "pattern", "architecture", "structure", "refactor", "code"],
     "note": "Software design-pattern index across languages/clouds — reach for a known pattern before inventing structure."},
    {"name": "binhnguyennus/awesome-scalability", "url": "https://github.com/binhnguyennus/awesome-scalability",
     "kind": "awesome", "tags": ["scalability", "performance", "architecture", "distributed", "scale", "reliability", "system-design"],
     "note": "Real-world scalability/performance/system-design patterns — for any 'make it scale/faster' goal."},
    {"name": "ripienaar/free-for-dev", "url": "https://github.com/ripienaar/free-for-dev",
     "kind": "awesome", "tags": ["free", "tier", "hosting", "saas", "api", "infra", "deploy", "service"],
     "note": "Free-tier SaaS/infra for developers — check before paying for hosting/APIs/services."},

    # ── desktop/GUI automation — the harness's "hands" (observe→decide→act in any app) ──────────
    {"name": "per-simmons/agent-desktop", "url": "https://github.com/per-simmons/agent-desktop",
     "kind": "tool", "tags": ["desktop", "gui", "automation", "cua", "computer-use", "click", "type",
                              "accessibility", "control", "app", "macos", "hands", "automate", "interact"],
     "note": "VERITY's desktop HANDS — drive any macOS app via the accessibility tree (snapshot→find→"
             "click/type/select/toggle). Reliable structured control, not pixel-clicking. Install: "
             "`npm i -g agent-desktop`; in-harness wrapper: `verity desktop <subcommand>`. Reach for this "
             "for ANY GUI task — opening apps, filling forms, clicking through flows — before deferring to the user."},
]

_BUILD_HINTS = ("build", "create", "implement", "make", "add", "write a", "develop", "design",
                "need a", "find a", "tool for", "library for", "framework", "set up", "integrate",
                "scrape", "parse", "dashboard", "ui ", "database", "agent", "swarm", "animate")


def _match(query: str, n: int = 8):
    """Score entries by tag/name/note overlap with the query words. Returns top-n dicts."""
    q = (query or "").lower()
    words = {w.strip(".,:;!?()[]\"'") for w in q.split() if len(w) > 2}
    scored = []
    for r in REGISTRY:
        hay = " ".join([r["name"].lower(), r["note"].lower(), " ".join(r["tags"])])
        tag_hits = sum(1 for t in r["tags"] if t in q)
        word_hits = sum(1 for w in words if w in hay)
        score = tag_hits * 3 + word_hits
        if score:
            scored.append((score, r))
    scored.sort(key=lambda x: (-x[0], x[1]["name"]))
    return [r for _, r in scored[:n]]


def search(query: str, n: int = 8) -> str:
    """`verity resources <query>` — find curated awesome-lists / frameworks relevant to a goal."""
    hits = _match(query, n) if query.strip() else REGISTRY[:n]
    if not hits:
        return (f"[resources: no curated match for '{query}'] — try the meta-list: "
                "https://github.com/sindresorhus/awesome (then `verity resources --fetch <name>`).")
    lines = [f"REUSE-FIRST resource library — curated matches for '{query}':"]
    for r in hits:
        lines.append(f"  [{r['kind']:7}] {r['name']}\n      {r['note']}\n      {r['url']}")
    lines.append("\nFetch a list's full contents live:  verity resources --fetch <name-or-url>")
    return "\n".join(lines)


def reuse_hint(goal: str, n: int = 4) -> str:
    """REUSE-FIRST hint for _preflight: if the goal looks like building/finding something, surface the
    most relevant existing options so the agent checks them BEFORE reinventing. Empty otherwise (zero cost).
    Mirrors tools.registry_hint — ground the model in 'what already exists' instead of letting it build blind."""
    g = (goal or "").lower()
    if not any(h in g for h in _BUILD_HINTS):
        return ""
    hits = _match(goal, n)
    if not hits:
        return ""
    lines = ["=== REUSE-FIRST: existing tools/lists to CHECK before building (don't reinvent) ==="]
    for r in hits:
        lines.append(f"  • {r['name']} — {r['note']} ({r['url']})")
    lines.append("  → If one fits, use it. `verity resources --fetch <name>` opens the full list.")
    return "\n".join(lines)


def fetch_list(name_or_url: str, max_chars: int = 7000) -> str:
    """Open an awesome-list/framework README LIVE (the 'infinite' depth) — the curated entry points to
    hundreds of tools; this pulls the current contents so the agent can pick the specific existing one.
    Live fetch (not cache) so a dead/moved entry simply returns an error string, never stale data."""
    target = name_or_url
    for r in REGISTRY:
        if name_or_url.lower() in r["name"].lower():
            target = r["url"]
            break
    if "github.com" in target and "/blob/" not in target and "/raw/" not in target:
        # try the rendered README via the GitHub raw default branches
        owner_repo = target.split("github.com/")[-1].strip("/")
        from .tools import fetch
        for branch in ("main", "master"):
            raw = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/README.md"
            out = fetch(raw, max_chars=max_chars)
            if out and "Error" not in out[:40] and len(out) > 200:
                return f"[{owner_repo} README @ {branch}]\n{out}"
    from .tools import fetch
    return fetch(target, max_chars=max_chars)

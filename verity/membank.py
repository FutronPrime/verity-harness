"""VERITY membank — bounded-context persistent memory for ANY LLM agent. Zero dependencies (pure stdlib:
sqlite3 + FTS5), local-first, LLM-agnostic. (Distinct from verity/memory.py, which is the lightweight
task-outcome recall used by the scaffold; membank is the user-facing knowledge store + bounded injection.)

THE PROBLEM (why this exists): an agent's knowledge grows toward infinity, but the context window is
finite. Preloading a flat index that grows O(memories) eventually blows the budget — trimming is a
treadmill, not a fix. The durable answer (convergent across MemGPT, MemoryOS, Mem0, claude-mem,
SuperBrain): keep the ALWAYS-LOADED context O(categories) and let the store grow O(∞) BEHIND RETRIEVAL.
"Storage is solved; injection isn't" — the lever is a fixed-budget retrieval at session start, not a
bigger file.

Design (distilled, zero-dep):
  • Storage: SQLite at ~/.verity-harness/membank.db + an FTS5 index (LIKE fallback if FTS5 absent).
  • capture(): ADD-only (never overwrite — preserves history, à la Mem0), sha256 dedup, regex entity
    extraction. Typed SCOPES route relevance (decision/preference/lesson/project/fact/error).
  • recall(): hybrid rank = FTS5 keyword (BM25) ⊕ recency ⊕ access-count, Jaccard dedup, HARD char-budget
    cap. Returns compact `[id] scope: snippet` lines — store can be huge, the block is fixed.
  • get(): full content for explicit ids (progressive disclosure — pull detail on demand).
  • session_start(): the injection block — durable scopes + recent project memory, ranked, capped. The
    ONLY thing loaded at session start; never grows past budget.
  • bootstrap_lint(): the markdown tier — keep an always-loaded MEMORY.md/CLAUDE.md O(categories).
No LLM call anywhere — summarization, if wanted, is the agent's own job at capture time.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time

DB = os.path.expanduser(os.environ.get("VERITY_MEMBANK_DB", "~/.verity-harness/membank.db"))
SCOPES = ("decision", "preference", "lesson", "project", "fact", "error")
DURABLE = ("preference", "decision", "lesson")     # always-considered at session start
_ENT = re.compile(r"`[^`]+`|\b[A-Z][a-zA-Z0-9]+(?:[A-Z][a-zA-Z0-9]+)+\b|\b[A-Z]{2,}\b|[\w./-]+\.[a-z]{2,4}\b")


def _fts(c) -> bool:
    try:
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _ftscheck USING fts5(x)")
        c.execute("DROP TABLE _ftscheck")
        return True
    except sqlite3.OperationalError:
        return False


def _conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS memories(
        id INTEGER PRIMARY KEY, project TEXT, scope TEXT, content TEXT, entities TEXT,
        hash TEXT UNIQUE, created_at REAL, accessed_at REAL, access_count INTEGER DEFAULT 0)""")
    if _fts(c):
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(content, entities, content='memories', content_rowid='id')")
    return c


def _entities(text: str) -> str:
    seen, out = set(), []
    for m in _ENT.findall(text or ""):
        t = m.strip("`").strip()
        if 2 < len(t) < 40 and t.lower() not in seen:
            seen.add(t.lower()); out.append(t)
    return " ".join(out[:20])


def _project(project: str | None) -> str:
    return project or os.path.basename(os.getcwd()) or "default"


def capture(content: str, scope: str = "fact", project: str | None = None) -> str:
    """ADD-only write. Dedups identical content (hash). Returns a short status line."""
    content = (content or "").strip()
    if not content:
        return "[membank: empty, skipped]"
    if scope not in SCOPES:
        scope = "fact"
    h = hashlib.sha256(f"{_project(project)}|{scope}|{content}".encode()).hexdigest()[:16]
    c = _conn()
    try:
        cur = c.execute("INSERT INTO memories(project,scope,content,entities,hash,created_at,accessed_at) "
                        "VALUES(?,?,?,?,?,?,?)",
                        (_project(project), scope, content, _entities(content), h, time.time(), time.time()))
        rid = cur.lastrowid
        if _fts(c):
            c.execute("INSERT INTO mem_fts(rowid,content,entities) VALUES(?,?,?)", (rid, content, _entities(content)))
        c.commit()
        return f"[membank #{rid} saved · {scope} · {_project(project)}]"
    except sqlite3.IntegrityError:
        return "[membank: duplicate, already stored]"
    finally:
        c.close()


def _rank_rows(rows, query):
    """Hybrid score: keyword overlap ⊕ recency ⊕ access_count ⊕ durable-scope. rows=(id,scope,content,created,acc)."""
    now = time.time()
    qwords = {w for w in re.split(r"\W+", (query or "").lower()) if len(w) > 2}
    # stem to a 6-char prefix so morphological variants match (animation↔animated, deploy↔deployment)
    qstems = {w[:6] for w in qwords}
    scored = []
    for rid, scope, content, created, acc in rows:
        cl = content.lower()
        kw = sum(1 for s in qstems if s in cl) if qstems else 0
        recency = max(0.0, 1.0 - (now - created) / (90 * 86400))      # 90-day linear decay
        score = kw * 3 + recency * 2 + min(acc, 5) * 0.4 + (1 if scope in DURABLE else 0)
        scored.append((score, rid, scope, content, created, acc))
    scored.sort(key=lambda x: -x[0])
    return scored


def _dedup(cands):
    """Drop near-duplicate snippets (Jaccard token overlap > 0.6), keeping the higher-ranked one."""
    kept = []
    for item in cands:
        toks = set(item[3].lower().split())
        if any(len(toks & set(k[3].lower().split())) / max(1, len(toks | set(k[3].lower().split()))) > 0.6 for k in kept):
            continue
        kept.append(item)
    return kept


def recall(query: str, project: str | None = None, budget_chars: int = 2000, k: int = 30) -> str:
    """Bounded retrieval. FTS5 keyword candidates (LIKE fallback) → hybrid rank → dedup → cap to budget."""
    c = _conn()
    try:
        rows = []
        if query and _fts(c):
            try:
                # prefix-stem EVERY query token (`want*` matches wants, `animat*` matches animated) —
                # FTS5 matches whole tokens, so without this, plurals/inflections silently miss.
                toks = [t for t in re.findall(r"\w+", query) if len(t) > 2]
                q = " OR ".join(t[:6] + "*" for t in toks) or "*"
                rows = c.execute(
                    "SELECT m.id,m.scope,m.content,m.created_at,m.access_count FROM mem_fts f "
                    "JOIN memories m ON m.id=f.rowid WHERE mem_fts MATCH ? LIMIT ?", (q, k)).fetchall()
            except sqlite3.OperationalError:
                rows = []
        if not rows:                                    # FTS empty / no FTS → rank a recent window by
            rows = c.execute(                            # keyword (qstems substring-match catches inflections)
                "SELECT id,scope,content,created_at,access_count FROM memories "
                "ORDER BY created_at DESC LIMIT ?", (max(k, 200),)).fetchall()
        ranked = _dedup(_rank_rows(rows, query))
        out, used, ids = [], 0, []
        for _, rid, scope, content, *_ in ranked:
            snippet = content if len(content) <= 160 else content[:157] + "…"
            line = f"[{rid}] {scope}: {snippet}"
            if used + len(line) > budget_chars:
                break
            out.append(line); used += len(line) + 1; ids.append(rid)
        if ids:                                         # access feedback loop (boosts useful memories)
            c.execute(f"UPDATE memories SET access_count=access_count+1, accessed_at=? WHERE id IN ({','.join('?'*len(ids))})",
                      (time.time(), *ids))
            c.commit()
        if not out:
            return f"[membank: nothing relevant to '{query}' — store empty or no match]"
        return ("VERITY membank recall (top, budget %d chars) — `verity memory get <id>` for full:\n" % budget_chars) + "\n".join(out)
    finally:
        c.close()


def get(ids) -> str:
    """Full content for explicit ids (progressive disclosure)."""
    if isinstance(ids, (str, int)):
        ids = [int(x) for x in re.findall(r"\d+", str(ids))]
    if not ids:
        return "[membank: no ids]"
    c = _conn()
    try:
        rows = c.execute(f"SELECT id,scope,project,content,created_at FROM memories WHERE id IN ({','.join('?'*len(ids))})", tuple(ids)).fetchall()
        return "\n\n".join(f"[{r[0]}] {r[1]} · {r[2]}\n{r[3]}" for r in rows) or "[membank: ids not found]"
    finally:
        c.close()


def session_start(project: str | None = None, budget_chars: int = 1500) -> str:
    """The bootstrap INJECTION block — bounded by construction. Durable prefs/decisions + recent project
    memory, ranked, capped. This is the ONLY thing loaded at session start; it never grows past budget."""
    c = _conn()
    try:
        p = _project(project)
        rows = c.execute(
            "SELECT id,scope,content,created_at,access_count FROM memories "
            "WHERE scope IN ('preference','decision','lesson') OR project=? "
            "ORDER BY created_at DESC LIMIT 60", (p,)).fetchall()
        ranked = _dedup(_rank_rows(rows, p))
        out, used = [], 0
        for _, rid, scope, content, *_ in ranked:
            snippet = content if len(content) <= 140 else content[:137] + "…"
            line = f"[{rid}] {scope}: {snippet}"
            if used + len(line) > budget_chars:
                break
            out.append(line); used += len(line) + 1
        n = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        if not out:
            return ""
        return (f"=== VERITY MEMORY ({n} stored; showing top {len(out)} within {budget_chars} chars) ===\n"
                + "\n".join(out) + "\n(recall more: `verity memory recall \"<query>\"`)")
    finally:
        c.close()


def stats() -> str:
    c = _conn()
    try:
        n = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        by = c.execute("SELECT scope,COUNT(*) FROM memories GROUP BY scope ORDER BY 2 DESC").fetchall()
        size = os.path.getsize(DB) if os.path.exists(DB) else 0
        return (f"VERITY membank: {n} memories · {size//1024} KB · {DB}\n"
                + ("  " + " · ".join(f"{s}:{ct}" for s, ct in by) if by else "  (empty)")
                + f"\n  FTS5: {'on' if _fts(c) else 'LIKE-fallback'}")
    finally:
        c.close()


# ── markdown bootstrap discipline (the OTHER tier — keep the always-loaded index O(categories)) ──────
def bootstrap_lint(path: str, max_chars: int = 4000, max_lines: int = 150) -> str:
    """Lint an always-loaded bootstrap memory file (CLAUDE.md / MEMORY.md / AGENTS.md). Flags the
    O(memories) anti-pattern: too many pointer lines, over-budget, fat inline summaries. The fix is
    always the same — move per-item lines into demand-loaded category INDEX files; root keeps only
    category pointers + always-on rules."""
    if not os.path.exists(path):
        return f"[bootstrap-lint: {path} not found]"
    text = open(path, encoding="utf-8", errors="replace").read()
    lines = text.splitlines()
    chars = len(text)
    bullets = [ln for ln in lines if ln.strip().startswith(("- ", "* ", "+ "))]
    fat = [ln for ln in bullets if len(ln) > 160]
    over = chars > max_chars or len(lines) > max_lines
    verdict = "OVER BUDGET" if over else ("WATCH (fat lines)" if fat else "OK")
    msg = [f"bootstrap-lint {path}: {verdict}",
           f"  {chars} chars (limit {max_chars}) · {len(lines)} lines (limit {max_lines}) · {len(bullets)} pointer lines · {len(fat)} fat (>160 chars)"]
    if over or fat:
        msg += ["  FIX (bounded-index — loaded root must be O(categories), not O(items)):",
                "   1. Group pointers into ~6-10 CATEGORIES.",
                "   2. Move each category's lines into a demand-loaded `INDEX-<category>.md` (NOT loaded at",
                "      session start — fetched only when relevant).",
                "   3. Root keeps: always-on rules + one line per category + infra. New items append to the",
                "      category INDEX file, never to root.",
                "   4. Cap category index files ~60 lines; roll up DONE/PARKED items to an archive file.",
                "  (VERITY did exactly this to its own MEMORY.md: 8714→2800 chars, zero data loss.)"]
    return "\n".join(msg)

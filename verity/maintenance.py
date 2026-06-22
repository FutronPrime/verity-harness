#!/usr/bin/env python3
"""Memory maintenance (`verity gc`) — keep the self-evolving stores BOUNDED over the long horizon.

The injection side is already solved (every recall/playbook/routing/strategy inject is hard char-capped,
so nothing can bloat the prompt). This addresses the OTHER axis the user flagged: the append-only stores
growing on DISK over months. Each is bounded here with a retention/cap policy that preserves the
high-value, hard-won data and ages out transient cruft:

  • membank rows   — capped (membank.prune): keep highest recency+access+durable-scope, evict the rest.
  • ledger day-files — keep the last N days (default 120; playbook only reads 30, so coverage is safe).
  • guard .cnt     — per-session overconfidence counters; delete those older than a day (pure litter).
  • discover pool  — cap the strategy population (keep champion + seeds + top-scored).
  • handles        — pointer-indirection blobs older than the retention window.

Idempotent, conservative, and self-reporting. Run manually (`verity gc`) or let autostart call it
occasionally. membank also self-prunes every ~256 writes, so even without gc it can't grow unbounded.
"""
from __future__ import annotations

import os
import pathlib
import time

HOME = pathlib.Path(os.path.expanduser("~/.verity-harness"))


def _prune_ledger(keep_days: int) -> dict:
    d = HOME / "ledger"
    if not d.is_dir():
        return {"removed": 0}
    cutoff = time.time() - keep_days * 86400
    removed = 0
    for f in d.glob("*.jsonl"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink(); removed += 1
        except OSError:
            pass
    return {"removed": removed, "kept_days": keep_days}


def _prune_dir_by_age(sub: str, max_age_days: float, pattern: str = "*") -> dict:
    d = HOME / sub
    if not d.is_dir():
        return {"removed": 0}
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    for f in d.glob(pattern):
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink(); removed += 1
        except OSError:
            pass
    return {"removed": removed}


def _cap_discover(max_pool: int) -> dict:
    try:
        from . import discover as D
    except Exception:  # noqa: BLE001
        return {"capped": 0}
    bank = D._load_bank()
    pop = bank.get("population", [])
    if len(pop) <= max_pool:
        return {"capped": 0, "pool": len(pop)}
    seeds = {s["name"] for s in D.SEED_STRATEGIES}
    champ = (bank.get("champion") or {}).get("name")
    # always keep seeds + champion; fill the rest by highest score (None scores last)
    keep = [s for s in pop if s["name"] in seeds or s["name"] == champ]
    rest = sorted((s for s in pop if s not in keep),
                  key=lambda s: (s.get("score") if s.get("score") is not None else -1), reverse=True)
    new = (keep + rest)[:max_pool]
    bank["population"] = new
    D._save_bank(bank)
    return {"capped": len(pop) - len(new), "pool": len(new)}


def gc(membank_max: int | None = None, ledger_days: int | None = None,
       discover_pool: int | None = None, verbose: bool = True) -> dict:
    """Run all maintenance passes. Conservative defaults; override via args or env."""
    membank_max = membank_max or int(os.environ.get("VERITY_MEMBANK_MAX", "5000"))
    ledger_days = ledger_days or int(os.environ.get("VERITY_LEDGER_KEEP_DAYS", "120"))
    discover_pool = discover_pool or int(os.environ.get("VERITY_DISCOVER_POOL_MAX", "64"))

    report = {}
    try:
        from . import membank
        report["membank"] = membank.prune(membank_max)
    except Exception as e:  # noqa: BLE001
        report["membank"] = {"error": type(e).__name__}
    report["ledger"] = _prune_ledger(ledger_days)
    report["guard_counters"] = _prune_dir_by_age("guard", 1.0, "*.cnt")
    report["handles"] = _prune_dir_by_age("handles", ledger_days)
    report["discover"] = _cap_discover(discover_pool)

    if verbose:
        print("VERITY memory maintenance (gc):")
        mb = report["membank"]
        print(f"  membank   : {mb.get('total','?')} rows, evicted {mb.get('evicted',0)} (cap {membank_max})")
        print(f"  ledger    : removed {report['ledger']['removed']} day-file(s) older than {ledger_days}d")
        print(f"  guard     : removed {report['guard_counters']['removed']} stale session counter(s)")
        print(f"  handles   : removed {report['handles']['removed']} old pointer blob(s)")
        print(f"  discover  : capped {report['discover'].get('capped',0)} strategy(ies) "
              f"(pool {report['discover'].get('pool','?')})")
    return report


if __name__ == "__main__":
    gc()

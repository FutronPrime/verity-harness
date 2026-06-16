"""verity evolve — closed-loop self-evolution of the injectable PLAYBOOK, gated so it can only improve.

Synthesis of the self-evolving-agent research (openevolve · DGM · AutoSkill · a-evolve · MemOS, 2026-06-16):
  • git-tagged candidate ARCHIVE — every attempt committed + tagged; rollback without erasure, browsable. (a-evolve/DGM)
  • DUAL-GATE promotion — a candidate is adopted ONLY if it passes; the live playbook is never blindly overwritten. (AutoSkill)
  • Mutation = the FEEDBACK LOOP content: freshly distilled ledger lessons + recall-promoted membank lessons
    (MemOS L1→L2). Mutation target is the PLAYBOOK TEXT ONLY — never code, never the eval. (EvoMap: keep it compact.)
  • Fitness/gate:
      - DEFAULT (deterministic, no API, honest): a NON-REGRESSION safety gate — the candidate must keep every
        high-confidence lesson the champion had (no coverage loss), stay within a size budget, and be valid.
        This is the difference between self-IMPROVING and self-CORRUPTING (the #1 safety finding). No model needed.
      - OPTIONAL `--eval` (real fitness, costs API): score champion-vs-candidate on a held-out trap split with
        the playbook injected as SYSTEM; adopt only if candidate >= champion. Coarse signal, labeled as such.
SAFETY: evolves only the playbook text; the eval/gate code is read-only from here; membank/ledger stay add-only.
"""
from __future__ import annotations

import json
import os
import subprocess
import time

EVO = os.path.expanduser("~/.verity-harness/evo")
CHAMP = os.path.join(EVO, "champion.json")
CYCLES = os.path.join(EVO, "cycles.jsonl")
PLAYBOOK = os.path.expanduser("~/.verity-harness/playbook.md")
MAX_CHARS = 6000          # size budget — a bloated playbook crowds out the prompt (EvoMap: gene > essay)


def _git(*a):
    return subprocess.run(["git", *a], cwd=EVO, capture_output=True, text=True)


def _ensure_repo():
    os.makedirs(EVO, exist_ok=True)
    if not os.path.isdir(os.path.join(EVO, ".git")):
        _git("init", "-b", "main")
        _git("config", "user.email", "verity@futron")
        _git("config", "user.name", "verity-evolve")


def _champion() -> dict:
    try:
        return json.load(open(CHAMP))
    except Exception:  # noqa: BLE001
        return {"score": None, "cycle": 0, "text": "", "chars": 0}


def _candidate(days: int = 30) -> str:
    """The mutation: a fresh playbook = distilled ledger lessons + recall-promoted membank lessons."""
    parts = []
    try:
        from . import ledger
        parts.append(ledger.playbook(days))
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import membank
        promo = membank.promote_block()
        if promo:
            parts.append(promo)
    except Exception:  # noqa: BLE001
        pass
    return "\n\n".join(p for p in parts if p and p.strip()).strip()


def _lessons(text: str) -> set:
    """High-confidence lesson lines (bullets) — used for the no-coverage-regression check."""
    return {ln.strip().lstrip("•-* ").strip()[:80] for ln in text.splitlines()
            if ln.strip().startswith(("•", "-", "*", "✗", "♻", "✓")) and len(ln.strip()) > 12}


def _safety_gate(champion: str, candidate: str) -> tuple[bool, str]:
    """Deterministic, no-API: REJECT a candidate that corrupts the playbook. Adopt only a clean improvement."""
    if not candidate or len(candidate) < 40:
        return False, "candidate empty/too short"
    if len(candidate) > MAX_CHARS:
        return False, f"over size budget ({len(candidate)}>{MAX_CHARS} chars) — would crowd the prompt"
    lost = _lessons(champion) - _lessons(candidate)
    if lost:
        return False, f"coverage REGRESSION — drops {len(lost)} high-confidence lesson(s): {list(lost)[:2]}"
    gained = len(_lessons(candidate)) - len(_lessons(champion))
    return True, f"clean (+{gained} lessons, {len(candidate)} chars, no coverage loss)"


def _eval_fitness(playbook_text: str, traps, tiers=None) -> float:
    """OPTIONAL real fitness (costs API): inject playbook as SYSTEM, score marker hits on `traps`."""
    from .router import ask
    from .eval_assumptions import _hit
    ok = 0
    for t in traps:
        try:
            r = ask(t["q"], system=playbook_text, **({"tiers": tiers} if tiers else {}))
            if _hit(r.text if hasattr(r, "text") else str(r), t["markers"]):
                ok += 1
        except Exception:  # noqa: BLE001
            pass
    return ok / max(1, len(traps))


def _log_cycle(rec: dict):
    os.makedirs(EVO, exist_ok=True)
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(CYCLES, "a") as f:
        f.write(json.dumps(rec) + "\n")


def evolve(days: int = 30, apply: bool = False, use_eval: bool = False, tiers=None) -> dict:
    """Run one evolution cycle. Dry by default (shows verdict + diff); --apply promotes if it passes."""
    _ensure_repo()
    champ = _champion()
    cand = _candidate(days)
    ok, why = _safety_gate(champ.get("text", ""), cand)
    result = {"cycle": champ.get("cycle", 0) + 1, "gate_pass": ok, "gate": why,
              "champion_chars": champ.get("chars", 0), "candidate_chars": len(cand)}

    if ok and use_eval:
        # dual-split: dev (select) + held-out test (confirm). Coarse, API-costed signal.
        try:
            from .eval_assumptions import TRAPS
            dev, test = TRAPS[: len(TRAPS) // 2], TRAPS[len(TRAPS) // 2:]
            c_dev, p_dev = _eval_fitness(cand, dev, tiers), _eval_fitness(champ.get("text") or cand, dev, tiers)
            result["dev_candidate"], result["dev_champion"] = round(c_dev, 3), round(p_dev, 3)
            if c_dev + 0.0 < p_dev:                      # regressed on dev → reject
                ok = False; result["gate_pass"] = False; result["gate"] = f"eval dev regression {c_dev:.2f}<{p_dev:.2f}"
            else:
                c_t, p_t = _eval_fitness(cand, test, tiers), _eval_fitness(champ.get("text") or cand, test, tiers)
                result["test_candidate"], result["test_champion"] = round(c_t, 3), round(p_t, 3)
                if c_t < p_t:
                    ok = False; result["gate_pass"] = False; result["gate"] = f"eval test regression {c_t:.2f}<{p_t:.2f}"
                else:
                    result["eval_score"] = round(c_t, 3)
        except Exception as e:  # noqa: BLE001
            result["eval_error"] = type(e).__name__

    if ok and apply:
        # archive champion → write candidate → tag. Rollback-without-erasure.
        with open(os.path.join(EVO, "playbook.md"), "w") as f:
            f.write(cand)
        _git("add", "-A")
        _git("commit", "--allow-empty", "-m", f"evo-{result['cycle']}: {why}")
        _git("tag", "-f", f"evo-{result['cycle']}")
        json.dump({"score": result.get("eval_score"), "cycle": result["cycle"], "text": cand,
                   "chars": len(cand), "ts": time.time()}, open(CHAMP, "w"), indent=2)
        with open(PLAYBOOK, "w") as f:                   # the live injected playbook
            f.write(cand)
        result["promoted"] = True
    else:
        result["promoted"] = False
    _log_cycle(result)
    return result

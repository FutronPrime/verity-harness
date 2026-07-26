"""Proactivity gate — the portable core of PROACTIVITY_PROTOCOL.md.

The protocol's whole claim is that proactive agents are graded on the wrong axis: false
alarms are visible and get optimised, Missed-Needed is invisible and does not. An agent
that never proposes has a perfect false-alarm rate and a 100% miss rate.

So this module's job is not "decide when to interrupt." It is **make the misses
countable**. Everything suppressed is written to the ledger as `mn_risk`, which is the
artifact you point at when a miss surfaces later.

Detectors are deliberately NOT included here — they are host-specific. Register your own:

    from verity.proactive import register, gate

    @register
    def stale_backups():
        if backup_age_hours() > 48:
            return [signal("backup", 70, "Backup is 3 days old",
                           "Last snapshot 2026-07-23.", "run `backup now`")]
        return []

    gate()

A detector MUST return a list. If it cannot determine its answer it returns a signal with
`unclear=True` — never an empty list, because empty is indistinguishable from healthy, and
that ambiguity is the exact failure the protocol exists to close.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Callable

STATE = pathlib.Path(os.getenv("VERITY_STATE",
                               str(pathlib.Path.home() / ".verity-harness"))) / "proactive"
LEDGER = STATE / "ledger.jsonl"
CONF = STATE / "config.json"

DEFAULTS = {
    "threshold": 55,
    "reject_penalty": 8,   # strong evidence: he looked and said no
    "ignore_penalty": 3,   # weak evidence: he may simply be busy
    "miss_bonus": 6,       # a miss LOWERS the bar — too quiet, not too loud
    "min_threshold": 25,
    "max_threshold": 85,
}

_DETECTORS: list[Callable[[], list[dict]]] = []


def register(fn: Callable[[], list[dict]]):
    """Decorator. Registers a deterministic detector."""
    _DETECTORS.append(fn)
    return fn


def signal(kind: str, severity: int, title: str, detail: str, action: str,
           unclear: bool = False) -> dict:
    return {"kind": kind, "severity": int(severity), "title": title,
            "detail": detail, "action": action, "unclear": bool(unclear)}


# ── store ───────────────────────────────────────────────────────────────────
def conf() -> dict:
    c = dict(DEFAULTS)
    if CONF.exists():
        try:
            c.update(json.loads(CONF.read_text()))
        except Exception:
            pass
    return c


def save_conf(c: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    CONF.write_text(json.dumps(c, indent=1))


def log(rec: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    rows = []
    for line in LEDGER.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


# ── the loop ────────────────────────────────────────────────────────────────
def observe() -> list[dict]:
    """Run every detector. A crash becomes a signal, never a silence."""
    out: list[dict] = []
    for d in _DETECTORS:
        try:
            got = d()
        except Exception as ex:
            out.append(signal("detector-error", 65, f"{d.__name__} crashed",
                              f"{type(ex).__name__}: {str(ex)[:110]}",
                              "This domain is UNMONITORED until fixed — not healthy.",
                              unclear=True))
            continue
        if not isinstance(got, list):
            out.append(signal("detector-error", 65, f"{d.__name__} returned non-list",
                              f"got {type(got).__name__}",
                              "Detectors must return a list of signals.", unclear=True))
            continue
        out.extend(got)
    return out


def gate(signals: list[dict] | None = None) -> dict:
    """Surface what clears the bar; record everything else as MN-risk.

    Returns {"surfaced": [...], "held": [...], "threshold": int}. The `held` list is the
    point of the whole exercise — without it a miss has no artifact behind it.
    """
    sigs = observe() if signals is None else signals
    thr = conf()["threshold"]
    surfaced = [s for s in sigs if s["severity"] >= thr]
    held = [s for s in sigs if s["severity"] < thr]
    for s in surfaced:
        log({"event": "proposed", "title": s["title"], "severity": s["severity"],
             "kind": s["kind"]})
    for s in held:
        log({"event": "mn_risk", "title": s["title"], "severity": s["severity"],
             "kind": s["kind"], "threshold": thr})
    return {"surfaced": surfaced, "held": held, "threshold": thr}


def record(response: str, title: str) -> int:
    """response ∈ {accept, reject, ignore}. Moves the bar asymmetrically."""
    if response not in ("accept", "reject", "ignore"):
        raise ValueError("response must be accept | reject | ignore")
    log({"event": "response", "response": response, "title": title})
    c = conf()
    if response == "reject":
        c["threshold"] = min(c["max_threshold"], c["threshold"] + c["reject_penalty"])
    elif response == "ignore":
        c["threshold"] = min(c["max_threshold"], c["threshold"] + c["ignore_penalty"])
    save_conf(c)
    return c["threshold"]


def miss(title: str, note: str = "") -> int:
    """Record a Missed-Needed. The only source of recall data that exists.

    Precision is computable from the ledger. Recall is not — a miss enters the record
    only if the person who needed it says so. Lower the bar when one is reported.
    """
    log({"event": "miss", "title": title, "note": note})
    c = conf()
    c["threshold"] = max(c["min_threshold"], c["threshold"] - c["miss_bonus"])
    save_conf(c)
    return c["threshold"]


def calibrate() -> dict:
    rows = ledger()
    resp = [r for r in rows if r.get("event") == "response"]
    acc = sum(1 for r in resp if r["response"] == "accept")
    rej = sum(1 for r in resp if r["response"] == "reject")
    ign = sum(1 for r in resp if r["response"] == "ignore")
    judged = acc + rej
    return {
        "proposed": sum(1 for r in rows if r.get("event") == "proposed"),
        "accepted_CD": acc,
        "rejected_FA": rej,
        "ignored": ign,
        "reported_misses_MN": sum(1 for r in rows if r.get("event") == "miss"),
        "suppressed_mn_risk": sum(1 for r in rows if r.get("event") == "mn_risk"),
        "threshold": conf()["threshold"],
        # deterministic
        "precision": (acc / judged) if judged else None,
        # NOT computable — stated explicitly so no dashboard invents it
        "recall": None,
        "recall_note": "Unknowable from this ledger. A miss appears only if reported. "
                       "A low false-alarm rate with zero reported misses describes an "
                       "UNMEASURED system, not a healthy one.",
    }


def report(res: dict | None = None) -> str:
    """Human-readable gate output. Never prints 'all clear'."""
    res = res or gate()
    lines = [f"[gate] threshold {res['threshold']} · "
             f"{len(res['surfaced'])} surfaced · {len(res['held'])} held"]
    if not res["surfaced"] and not res["held"]:
        lines.append("  no signals — meaning these detectors found nothing THEY CAN SEE. "
                     "That is not the same as nothing being wrong.")
        return "\n".join(lines)
    for s in sorted(res["surfaced"], key=lambda x: -x["severity"]):
        lines.append(f"\n  ── {s['title']}  [{s['severity']}]"
                     f"{'  (UNCLEAR)' if s.get('unclear') else ''}")
        lines.append(f"     {s['detail']}")
        lines.append(f"     → {s['action']}")
    if res["held"]:
        lines.append(f"\n  {len(res['held'])} held below the bar, recorded as MN-RISK:")
        for s in res["held"]:
            lines.append(f"     · {s['title']} ({s['severity']})")
    return "\n".join(lines)

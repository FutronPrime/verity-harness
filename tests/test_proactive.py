#!/usr/bin/env python3
"""ADVERSARIAL regression suite for the proactivity gate (verity/proactive.py).

The gate's whole reason to exist is that the error it guards against is INVISIBLE — an agent
that stays quiet passes every response-inspecting check. So the properties below are not
niceties, they are the protocol:

  1. A crashing detector must produce a SIGNAL, never a silence. (An empty list is
     indistinguishable from a healthy system — that ambiguity is the bug.)
  2. Everything suppressed must be written to the ledger as `mn_risk`, or a miss discovered
     later has no artifact behind it.
  3. Responses must move the bar ASYMMETRICALLY — reject is strong evidence, ignore is weak.
  4. A reported miss must LOWER the bar. Evidence of a miss means too quiet, not too loud.
  5. `calibrate()` must refuse to report a recall number. It cannot know one, and a dashboard
     that invents it re-creates the exact blindness this module exists to remove.
  6. Reporting must never say "all clear."

Run from repo root:  python3 tests/test_proactive.py   (exit 0 = all pass)
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Isolate state BEFORE importing the module — it resolves paths at import time.
_TMP = tempfile.mkdtemp(prefix="verity-proactive-test-")
os.environ["VERITY_STATE"] = _TMP

from verity import proactive as P  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


def fresh():
    """Reset the ledger and bar between cases so results cannot leak."""
    if P.LEDGER.exists():
        P.LEDGER.unlink()
    P.save_conf(dict(P.DEFAULTS))
    P._DETECTORS.clear()


print("1. a crashing detector becomes a signal, not a silence")
fresh()


@P.register
def _boom():
    raise RuntimeError("simulated detector failure")


sigs = P.observe()
check("crash produces exactly one signal", len(sigs) == 1, f"got {len(sigs)}")
check("crash signal is marked unclear", sigs and sigs[0].get("unclear") is True)
check("crash signal names the detector", sigs and "_boom" in sigs[0]["title"])
check("crash signal says UNMONITORED, not healthy",
      sigs and "UNMONITORED" in sigs[0]["action"])

print("\n2. a detector returning a non-list is caught (not silently skipped)")
fresh()


@P.register
def _wrongtype():
    return None


sigs = P.observe()
check("non-list return produces a signal", len(sigs) == 1, f"got {len(sigs)}")
check("non-list signal is unclear", sigs and sigs[0].get("unclear") is True)

print("\n3. suppressed signals are recorded as mn_risk")
fresh()


@P.register
def _low_and_high():
    return [P.signal("x", 90, "loud thing", "d", "a"),
            P.signal("x", 10, "quiet thing", "d", "a")]


res = P.gate()
check("one surfaced", len(res["surfaced"]) == 1, f"got {len(res['surfaced'])}")
check("one held", len(res["held"]) == 1, f"got {len(res['held'])}")
rows = P.ledger()
kinds = [r["event"] for r in rows]
check("ledger has a 'proposed' row", "proposed" in kinds)
check("ledger has an 'mn_risk' row — the suppressed signal left evidence",
      "mn_risk" in kinds)
mn = [r for r in rows if r["event"] == "mn_risk"][0]
check("mn_risk row names the suppressed item", mn["title"] == "quiet thing")
check("mn_risk row records the bar it lost to", mn.get("threshold") == 55)

print("\n4. responses move the bar asymmetrically")
fresh()
base = P.conf()["threshold"]
after_ignore = P.record("ignore", "t")
check("ignore raises the bar a little", after_ignore == base + 3,
      f"{base} -> {after_ignore}")
fresh()
after_reject = P.record("reject", "t")
check("reject raises it more than ignore", after_reject == base + 8,
      f"{base} -> {after_reject}")
check("reject penalty > ignore penalty",
      P.DEFAULTS["reject_penalty"] > P.DEFAULTS["ignore_penalty"])
fresh()
after_accept = P.record("accept", "t")
check("accept does not move the bar", after_accept == base, f"{base} -> {after_accept}")

print("\n5. a reported miss LOWERS the bar")
fresh()
after_miss = P.miss("should have told me the gate was down")
check("miss lowers the bar", after_miss < base, f"{base} -> {after_miss}")
check("miss is logged", any(r["event"] == "miss" for r in P.ledger()))

print("\n6. the bar is clamped at both ends")
fresh()
for _ in range(40):
    P.record("reject", "t")
check("bar cannot exceed max", P.conf()["threshold"] == P.DEFAULTS["max_threshold"])
fresh()
for _ in range(40):
    P.miss("m")
check("bar cannot fall below min", P.conf()["threshold"] == P.DEFAULTS["min_threshold"])

print("\n7. calibrate refuses to invent a recall number")
fresh()
P.record("accept", "a")
P.record("reject", "b")
c = P.calibrate()
check("precision IS computed", c["precision"] == 0.5, f"got {c['precision']}")
check("recall is explicitly None", c["recall"] is None)
check("recall_note explains why", "reported" in (c["recall_note"] or "").lower())
check("low-FA-zero-MN is called UNMEASURED, not healthy",
      "UNMEASURED" in (c["recall_note"] or ""))
check("calibrate output is JSON-serialisable", bool(json.dumps(c)))

print("\n8. reporting never claims 'all clear'")
fresh()
txt = P.report()
low = txt.lower()
check("no 'all clear'", "all clear" not in low)
check("no 'no issues'", "no issues" not in low)
check("empty sweep is phrased as a limit of the detectors",
      "they can see" in low or "THEY CAN SEE" in txt)

print("\n9. an invalid response is rejected, not silently ignored")
fresh()
try:
    P.record("maybe", "t")
    check("invalid response raises", False, "no exception")
except ValueError:
    check("invalid response raises", True)

print()
if FAILED:
    print(f"FAILED {len(FAILED)}: {', '.join(FAILED)}")
    sys.exit(1)
print("all proactivity-gate checks passed")

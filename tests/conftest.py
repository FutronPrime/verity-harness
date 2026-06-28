#!/usr/bin/env python3
"""Test isolation for the VERITY suite.

Several tests monkeypatch module-level globals to stay offline/deterministic —
e.g. ``test_edge_cases`` sets ``ledger.log = lambda *a, **k: None`` and
``membank.capture = ...`` to exercise the swarm DAG without side effects, and
others rebind ``ledger.LEDGER_DIR`` / ``membank.DB`` / ``looplib.CACHE`` to a
temp path. None of them restore the original afterward, so the mutation LEAKS
into later test files: the persist tests then read a ledger whose ``log`` is a
no-op (0 records) and fail — but only when run in the same process, after the
polluter. That made the suite order-dependent (green in isolation, red as a
whole), which is exactly the flakiness CI must not ship.

Fix: an autouse fixture that snapshots the namespace of every module these tests
rebind, then restores it after each test. Every test runs against pristine
module state regardless of collection order. No product code changes — the
leak is purely a test-hygiene problem.
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest

# Make `import verity...` work from a bare checkout (no install step in CI).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Modules whose module-level attributes (functions, DB paths, cache paths) are
# rebound by individual tests. Snapshot + restore the full namespace of each.
_GUARDED = (
    "verity.ledger",
    "verity.membank",
    "verity.looplib",
    "verity.swarm",
    "verity.scaffold",
    "verity.coordinate",
    "verity.discover",
    "verity.persist",
)


@pytest.fixture(autouse=True)
def _isolate_module_globals():
    """Restore each guarded module's namespace after every test."""
    saved = {}
    for name in _GUARDED:
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue  # module optional / unimportable in this env — skip it
        saved[name] = dict(mod.__dict__)
    yield
    for name, snap in saved.items():
        mod = sys.modules.get(name)
        if mod is None:
            continue
        cur = mod.__dict__
        # drop names a test added, then rebind originals (functions + paths)
        for key in [k for k in cur if k not in snap]:
            del cur[key]
        cur.update(snap)

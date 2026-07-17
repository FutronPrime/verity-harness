#!/usr/bin/env python3
"""Tests for hooks/reuse-first-gate.sh — the PreToolUse gate that blocks rebuilding tools
that already exist. Deterministic: each case runs the hook under an isolated projects dir
with a hand-crafted transcript, so BLOCK vs ALLOW is fully reproducible (no network)."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent.parent / "hooks" / "reuse-first-gate.sh")


def _run(payload: dict, evidence: str | None) -> str:
    """Run the hook; return 'BLOCK' or 'ALLOW'. `evidence` seeds the transcript."""
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "projects" / "p"
        proj.mkdir(parents=True)
        sid = payload.get("session_id", "s")
        line = ({"type": "tool_use", "name": "Bash", "input": {"command": evidence}}
                if evidence else {"type": "text", "text": "just building, no search"})
        (proj / f"{sid}.jsonl").write_text(json.dumps(line) + "\n")
        env = {**os.environ, "CLAUDE_PROJECTS_DIR": str(Path(td) / "projects")}
        out = subprocess.run(["bash", HOOK], input=json.dumps(payload),
                             capture_output=True, text=True, env=env, timeout=15).stdout
    return "BLOCK" if '"decision": "block"' in out else "ALLOW"


def _pl(tool, path, sid):
    return {"tool_name": tool, "tool_input": {"file_path": path}, "session_id": sid}


BIN = "/opt/futron/bin"  # a guarded */bin/* path that does NOT exist on disk (so it's "new")
SYS_Q = "futron-system-directory --query foo"
LS_BIN = "ls /opt/futron/bin | grep foo"


def test_new_bin_tool_no_search_blocks():
    assert _run(_pl("Write", f"{BIN}/brand-new-tool", "s1"), None) == "BLOCK"


def test_new_bin_tool_with_sysdir_query_allows():
    assert _run(_pl("Write", f"{BIN}/brand-new-tool", "s2"), SYS_Q) == "ALLOW"


def test_new_bin_tool_with_ls_bin_evidence_allows():
    assert _run(_pl("Write", f"{BIN}/brand-new-tool", "s3"), LS_BIN) == "ALLOW"


def test_edit_existing_file_always_allows(tmp_path):
    existing = tmp_path / "bin" / "already-here"
    existing.parent.mkdir(); existing.write_text("#!/bin/sh\n")
    assert _run(_pl("Write", str(existing), "s4"), None) == "ALLOW"


def test_new_plist_daemon_no_search_blocks():
    assert _run(_pl("Write", "/Users/x/Library/LaunchAgents/com.foo.bar.plist", "s5"), None) == "BLOCK"


def test_unrelated_file_allows():
    assert _run(_pl("Write", "/tmp/notes.txt", "s6"), None) == "ALLOW"


def test_non_write_tool_allows():
    assert _run(_pl("Bash", f"{BIN}/brand-new-tool", "s7"), None) == "ALLOW"


def test_new_bin_subdir_no_search_blocks():
    assert _run(_pl("Write", f"{BIN}/sub/deep-new-tool", "s8"), None) == "BLOCK"


def test_path_with_spaces_no_search_blocks():
    assert _run(_pl("Write", f"{BIN}/new tool with spaces", "s9"), None) == "BLOCK"


def test_malformed_payload_fails_open():
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "CLAUDE_PROJECTS_DIR": td}
        out = subprocess.run(["bash", HOOK], input="not-json", capture_output=True,
                             text=True, env=env, timeout=15).stdout
    assert '"decision": "block"' not in out  # fail-open


def test_empty_file_path_allows():
    assert _run(_pl("Write", "", "s11"), None) == "ALLOW"


def test_edit_verb_on_new_bin_blocks():
    # Edit (not just Write) of a non-existent guarded path is also gated.
    assert _run(_pl("Edit", f"{BIN}/another-new", "s12"), None) == "BLOCK"

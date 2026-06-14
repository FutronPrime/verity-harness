#!/usr/bin/env python3
"""Sandboxed + delegating executors — the OpenHands-pattern integration.

VERITY's gates wrap an Executor (loop.py: `run(action)->str`). ShellExecutor runs
on your host (fine for trusted local work). For UNTRUSTED / heavier autonomous work
you want isolation — the pattern OpenHands (github.com/All-Hands-AI/OpenHands, 76.5k★)
is built on: run the agent's actions inside a container the agent can't escape.

  DockerExecutor   — per-command isolation in a throwaway container (VERIFIED working
                     path; the concrete sandbox VERITY's roadmap wanted).
  run_with_openhands — delegate a WHOLE goal to the OpenHands agent, then let VERITY
                     verify the result ("OpenHands does it, Verity checks it").

Honest tagging (Verity discipline applied to its own code):
  • DockerExecutor  = VERIFIED — plain `docker run`, testable here.
  • OpenHands CLI invocation = GUESS — exact flags vary by OpenHands version; this
    degrades gracefully and tells you to confirm the command for your install.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class DockerExecutor:
    """Run each action in an isolated, throwaway Docker container (OpenHands-style
    sandbox). The agent can touch /work (your mounted cwd) but not the rest of your
    host. For maximum safety on untrusted tasks set network='none'."""
    image: str = "python:3.12-slim"
    timeout_s: int = 90
    cwd: str | None = None
    network: str = "bridge"   # 'none' = no network (safest); 'bridge' = allow (installs/fetch)
    max_output: int = 6000

    def run(self, action: str) -> str:
        if not shutil.which("docker"):
            return ("[docker not installed — sandboxed execution needs Docker. Install "
                    "Docker Desktop, or use ShellExecutor for trusted local work.]")
        workdir = self.cwd or os.getcwd()
        cmd = ["docker", "run", "--rm", "--network", self.network,
               "-v", f"{workdir}:/work", "-w", "/work", self.image, "sh", "-c", action]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_s)
            body = (out.stdout + out.stderr)[:self.max_output]
            return body or f"[ok] (no output, exit {out.returncode})"
        except subprocess.TimeoutExpired:
            return f"[timeout] container exceeded {self.timeout_s}s"
        except Exception as e:  # noqa: BLE001
            return f"[docker error: {type(e).__name__}: {e}]"


def run_with_openhands(goal: str, timeout: int = 900) -> str:
    """Delegate a full goal to the OpenHands autonomous coding agent (sandboxed),
    return its output so VERITY's gates can verify it. Requires OpenHands installed
    (`pip install openhands-ai`) + Docker.

    GUESS: the CLI flags below (`--task`) are version-dependent — confirm with
    `openhands --help` for your install. Degrades gracefully if absent/wrong."""
    binary = shutil.which("openhands") or shutil.which("openhands-ai")
    if not binary:
        return ("[OpenHands not installed — `pip install openhands-ai` (needs Docker). "
                "github.com/All-Hands-AI/OpenHands. Then VERITY can delegate goals to it "
                "and verify the result.]")
    for args in (["--task", goal], ["-t", goal], [goal]):  # try common shapes
        try:
            out = subprocess.run([binary, *args], capture_output=True, text=True, timeout=timeout)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout[:8000]
        except (subprocess.TimeoutExpired, OSError):
            continue
    return ("[OpenHands present but the invocation shape is unconfirmed for this version "
            "— run `openhands --help` and set the right flags, then retry.]")

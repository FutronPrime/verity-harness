#!/usr/bin/env python3
"""Autonomy loop — think → act → verify, on top of the sovereign router.

Design goals:
  - Long-horizon: keep stepping toward a goal until done or budget exhausted.
  - Safe by default: the model NEVER executes arbitrary shell unless you opt in.
    The default executor is PLAN-ONLY (records intended actions, runs nothing).
  - Sovereign: all reasoning goes through the tiered router, so the loop keeps
    running even if the cloud tier is revoked.

Plug a real sandbox (OpenHands/Aider/Docker) by implementing Executor.run().
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Protocol

from .router import ask, Reply


# ─── Executor abstraction ────────────────────────────────────────────────────

class Executor(Protocol):
    def run(self, action: str) -> str:
        """Execute one action, return observed result text."""
        ...


@dataclass
class PlanOnlyExecutor:
    """SAFE DEFAULT — records intended actions, executes nothing. Use this to
    watch what an autonomous run *would* do before you ever let it touch a shell.
    """
    planned: list[str] = field(default_factory=list)

    def run(self, action: str) -> str:
        self.planned.append(action)
        return f"[plan-only] recorded (not executed): {action}"


@dataclass
class AllowlistShellExecutor:
    """Opt-in real execution, but ONLY commands whose first token is allowlisted.
    Anything else is refused. This is a deliberate safety floor — not a sandbox.
    For untrusted/long-horizon autonomy, prefer a Docker-backed executor.
    """
    allow: tuple[str, ...] = ("ls", "cat", "grep", "rg", "find", "wc", "head",
                              "tail", "git", "python3", "echo", "pwd")

    def run(self, action: str) -> str:
        import shlex, subprocess
        try:
            parts = shlex.split(action)
        except ValueError:
            return "[refused] unparseable command"
        if not parts or parts[0] not in self.allow:
            return f"[refused] '{parts[0] if parts else ''}' not in allowlist {self.allow}"
        try:
            out = subprocess.run(parts, capture_output=True, text=True, timeout=30)
            return (out.stdout + out.stderr)[:4000] or "[ok] (no output)"
        except subprocess.TimeoutExpired:
            return "[timeout] command exceeded 30s"
        except Exception as e:  # noqa: BLE001
            return f"[error] {type(e).__name__}: {e}"


# ─── The loop ────────────────────────────────────────────────────────────────

_STEP_SYS = """You are an autonomous task-runner. Work toward the GOAL one step \
at a time. Respond ONLY with a JSON object, no prose around it:
{"thought": "<brief reasoning>", "action": "<a single shell command, or empty \
if done>", "done": <true|false>, "summary": "<final answer, only when done>"}
Keep actions minimal and safe. Set done=true when the goal is achieved."""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class Step:
    n: int
    thought: str
    action: str
    observation: str
    tier: str


@dataclass
class LoopResult:
    goal: str
    done: bool
    summary: str
    steps: list[Step] = field(default_factory=list)


def _parse_step(text: str) -> dict:
    m = _JSON_RE.search(text)
    if not m:
        return {"thought": text[:200], "action": "", "done": True,
                "summary": text[:500]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"thought": text[:200], "action": "", "done": True,
                "summary": text[:500]}


def run_goal(goal: str, executor: Executor | None = None, max_steps: int = 8,
             verbose: bool = True) -> LoopResult:
    """Drive a goal to completion (or budget) through think→act→verify."""
    ex = executor if executor is not None else PlanOnlyExecutor()
    import os
    transcript = (f"WORKING DIRECTORY: {os.getcwd()}\n"
                  f"(commands run from here; prefer relative paths)\n"
                  f"GOAL: {goal}\n")
    result = LoopResult(goal=goal, done=False, summary="")

    for n in range(1, max_steps + 1):
        reply: Reply = ask(transcript, system=_STEP_SYS, verbose=False)
        step = _parse_step(reply.text)
        thought = str(step.get("thought", ""))[:300]
        action = str(step.get("action", "")).strip()
        done = bool(step.get("done", False))

        if verbose:
            print(f"\n[step {n}] ({reply.tier}) think: {thought}")

        if done or not action:
            result.done = True
            result.summary = str(step.get("summary", thought))
            if verbose:
                print(f"[done] {result.summary}")
            break

        obs = ex.run(action)
        if verbose:
            print(f"[step {n}] act: {action}\n[step {n}] obs: {obs[:300]}")
        result.steps.append(Step(n=n, thought=thought, action=action,
                                 observation=obs, tier=reply.tier))
        transcript += f"\nSTEP {n}: {action}\nRESULT: {obs[:1500]}\n"

    if not result.done:
        result.summary = "(max steps reached without explicit completion)"
    return result

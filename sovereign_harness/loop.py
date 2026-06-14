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
    """Opt-in real execution, but ONLY commands whose first token is allowlisted,
    run WITHOUT a shell (no pipes/redirects). Maximum-paranoia mode. Most real
    agentic work needs pipes/cd/compound commands — use ShellExecutor for that.
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


# Clearly-catastrophic patterns blocked regardless of model. A DENYLIST (not a
# narrow allowlist) is how real coding agents run — it permits the pipes/cd/find
# that agents naturally use, while stopping the handful of truly destructive ops.
_DENY = [
    r"\brm\s+-rf?\s+(/|~|\$HOME|\*)",      # rm -rf / ~ * $HOME
    r"\b(mkfs|fdisk|dd)\b",                 # disk wipers
    r">\s*/dev/(sd|disk|nvme)",             # overwrite raw disk
    r":\(\)\s*\{.*\};:",                    # fork bomb
    r"\bcurl\b.*\|\s*(sudo\s+)?(sh|bash)",  # curl | sh
    r"\bwget\b.*\|\s*(sudo\s+)?(sh|bash)",  # wget | sh
    r"\b(shutdown|reboot|halt)\b",
    r"\bchmod\s+-R?\s*777\s+/",
    r"\bgit\b.*\bpush\b.*\b(--force|-f)\b", # force-push
]
import re as _re
_DENY_RE = [_re.compile(p) for p in _DENY]


@dataclass
class ShellExecutor:
    """Real shell execution (pipes, cd, &&, find -exec all work) with a denylist
    of catastrophic operations. This is the practical default for trusted LOCAL
    agentic work — the same posture as OpenHands/Aider on a dev box.

    For UNTRUSTED or multi-user deployments, wrap in Docker instead (subclass and
    override run() to exec inside a container).
    """
    timeout_s: int = 30
    cwd: str | None = None
    max_output: int = 6000

    def run(self, action: str) -> str:
        import subprocess
        for rx in _DENY_RE:
            if rx.search(action):
                return f"[blocked] command matches a catastrophic-op denylist pattern"
        try:
            out = subprocess.run(action, shell=True, capture_output=True, text=True,
                                 timeout=self.timeout_s, cwd=self.cwd)
            body = (out.stdout + out.stderr)[:self.max_output]
            return body or "[ok] (no output, exit %d)" % out.returncode
        except subprocess.TimeoutExpired:
            return f"[timeout] command exceeded {self.timeout_s}s"
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


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_F_ACTION = re.compile(r'"action"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
_F_SUMMARY = re.compile(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
_F_THOUGHT = re.compile(r'"thought"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
_F_DONE = re.compile(r'"done"\s*:\s*(true|false)', re.I)


def parse_step_json(text: str) -> dict:
    """Extract a step dict from possibly-messy LLM output. NEVER raises.

    Robust to: markdown ```json fences, prose around the JSON, and — critically
    for weak models — UNTERMINATED strings / truncated JSON (salvages action,
    done, summary field-by-field). This was the eval's scaffold-Kimi killer.
    """
    s = text.strip()
    fence = _FENCE_RE.search(s)
    if fence:
        s = fence.group(1).strip()
    m = _JSON_RE.search(s)
    candidate = m.group(0) if m else s
    # 1. clean parse
    for attempt in (candidate, s):
        try:
            d = json.loads(attempt)
            if isinstance(d, dict):
                return d
        except (json.JSONDecodeError, TypeError):
            pass
    # 2. field-level salvage from malformed/truncated JSON
    d: dict = {}
    if (a := _F_ACTION.search(candidate)):
        d["action"] = a.group(1).replace('\\"', '"').replace("\\n", "\n")
    if (dn := _F_DONE.search(candidate)):
        d["done"] = dn.group(1).lower() == "true"
    if (sm := _F_SUMMARY.search(candidate)):
        d["summary"] = sm.group(1).replace('\\"', '"')
    if (th := _F_THOUGHT.search(candidate)):
        d["thought"] = th.group(1).replace('\\"', '"')
    if d:
        d.setdefault("done", not d.get("action"))  # no action salvaged → treat as done
        return d
    # 3. last resort: treat whole text as a final answer
    return {"thought": text[:200], "action": "", "done": True, "summary": text[:500]}


def _parse_step(text: str) -> dict:  # back-compat alias
    return parse_step_json(text)


def run_goal(goal: str, executor: Executor | None = None, max_steps: int = 8,
             tiers=None, verbose: bool = True) -> LoopResult:
    """Drive a goal through a NAIVE think→act loop — NO verification gate. This is
    the 'optimistic agent loop' baseline: it accepts the first 'done' it's given."""
    ex = executor if executor is not None else PlanOnlyExecutor()
    import os
    _kw = {"tiers": tiers} if tiers else {}
    transcript = (f"WORKING DIRECTORY: {os.getcwd()}\n"
                  f"(commands run from here; prefer relative paths)\n"
                  f"GOAL: {goal}\n")
    result = LoopResult(goal=goal, done=False, summary="")

    for n in range(1, max_steps + 1):
        reply: Reply = ask(transcript, system=_STEP_SYS, verbose=False, **_kw)
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

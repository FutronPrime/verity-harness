"""Sovereign Harness — vendor-independent autonomous LLM orchestration.

Safety posture (non-negotiable): models keep their guardrails. This project buys
RESILIENCE (no single-vendor dependency), not lawlessness. It does not bypass,
disable, or circumvent any model's safety systems.
"""
from .router import ask, chat, Reply, AllTiersFailed
from .config import TIERS, summary
from .loop import run_goal, PlanOnlyExecutor, AllowlistShellExecutor

__all__ = ["ask", "chat", "Reply", "AllTiersFailed", "TIERS", "summary",
           "run_goal", "PlanOnlyExecutor", "AllowlistShellExecutor"]
__version__ = "0.1.0"

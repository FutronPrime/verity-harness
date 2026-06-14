"""VERITY — vendor-independent autonomous LLM orchestration.

Safety posture (non-negotiable): models keep their guardrails. This project
buys RESILIENCE (no single-vendor dependency), not lawlessness. The capability
that got Fable 5 suspended is the one thing we deliberately do NOT replicate.
"""
from .loop import run_goal
from .router import ask, chat, Reply, AllTiersFailed
from .config import TIERS, summary

__all__ = ["run_goal", "ask", "chat", "Reply", "AllTiersFailed", "TIERS", "summary"]
__version__ = "0.1.0"

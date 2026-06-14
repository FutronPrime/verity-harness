#!/usr/bin/env python3
"""CLI for the Sovereign Harness.

  python3 -m sovereign_harness tiers              # show routing order
  python3 -m sovereign_harness ask "your prompt"  # route a prompt (verbose trail)
  python3 -m sovereign_harness failover-test      # prove Tier1→Tier0 failover
  python3 -m sovereign_harness loop "<goal>"      # autonomous loop (plan-only)
  python3 -m sovereign_harness loop "<goal>" --exec   # loop w/ allowlisted shell
"""
import sys

from .config import summary, TIERS, Tier
from .router import ask, chat, AllTiersFailed
from .loop import run_goal, PlanOnlyExecutor, AllowlistShellExecutor


def _cmd_ask(prompt: str):
    try:
        r = ask(prompt, verbose=True)
    except AllTiersFailed as e:
        print(f"\nSOVEREIGN FAILURE — every tier down:\n{e}", file=sys.stderr)
        sys.exit(1)
    print("\n--- reply ---")
    print(r.text)
    print(f"\n[served by {r.tier} / {r.model} in {r.latency_s:.1f}s]")
    print("trail:", " | ".join(r.attempts))


def _cmd_failover_test():
    """Simulate the cloud being yanked: point Tier 1 at a dead port, confirm the
    router drops to Tier 0 (local weights) and still answers."""
    dead = Tier(name="tier1-cloud(SIMULATED-DOWN)", protocol="openai",
                base_url="http://127.0.0.1:9/v1", model="x", timeout_s=3)
    tiers = [dead] + [t for t in TIERS if t.name == "tier0-local"]
    print("Simulating vendor suspension: Tier 1 pointed at a dead port.")
    print("Expectation: router fails over to Tier 0 (owned weights) and answers.\n")
    try:
        r = chat([{"role": "user", "content": "Reply with exactly: SOVEREIGN-OK"}],
                 tiers=tiers, verbose=True)
    except AllTiersFailed as e:
        print(f"\nFAILED — local floor unreachable:\n{e}", file=sys.stderr)
        sys.exit(1)
    print("\n--- reply ---")
    print(r.text.strip())
    print(f"\n[PROOF] cloud was down, yet {r.tier} ({r.model}) served in {r.latency_s:.1f}s")


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "tiers":
        print(summary())
    elif cmd == "ask":
        if not rest:
            print("usage: ask \"<prompt>\"", file=sys.stderr); sys.exit(2)
        _cmd_ask(" ".join(rest))
    elif cmd == "failover-test":
        _cmd_failover_test()
    elif cmd == "loop":
        if not rest:
            print("usage: loop \"<goal>\" [--exec]", file=sys.stderr); sys.exit(2)
        live = "--exec" in rest
        goal = " ".join(x for x in rest if x != "--exec")
        ex = AllowlistShellExecutor() if live else PlanOnlyExecutor()
        print(f"[loop] executor={'allowlist-shell' if live else 'PLAN-ONLY (safe)'}\n")
        r = run_goal(goal, executor=ex, verbose=True)
        print(f"\n=== result ===\ndone={r.done}  steps={len(r.steps)}\n{r.summary}")
    else:
        print(f"unknown command: {cmd}", file=sys.stderr); sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])

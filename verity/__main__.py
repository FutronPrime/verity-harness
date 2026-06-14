#!/usr/bin/env python3
"""CLI for the Verity Router.

  python3 -m verity tiers              # show routing order
  python3 -m verity ask "your prompt"  # route a prompt (verbose trail)
  python3 -m verity failover-test      # prove Tier1→Tier0 failover
  python3 -m verity providers [name]   # how to wire FREE LLM access
  python3 -m verity solve "<goal>"     # full discipline scaffold (real shell)
"""
import sys

from .config import summary, TIERS, Tier
from .router import ask, chat, AllTiersFailed
from .loop import run_goal, PlanOnlyExecutor, AllowlistShellExecutor, ShellExecutor


def _cmd_tiers():
    print(summary())


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
    """Simulate the cloud being yanked: point Tier 1 at a dead port, confirm
    the router silently drops to Tier 0 (local weights) and still answers."""
    dead_tier1 = Tier(name="tier1-cloud(SIMULATED-DOWN)", protocol="openai",
                      base_url="http://127.0.0.1:9/v1", model="claude-opus",
                      timeout_s=3)
    tiers = [dead_tier1] + [t for t in TIERS if t.name == "tier0-local"]
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
    print("trail:", " | ".join(r.attempts))


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "tiers":
        _cmd_tiers()
    elif cmd == "ask":
        if not rest:
            print("usage: ask \"<prompt>\"", file=sys.stderr); sys.exit(2)
        _cmd_ask(" ".join(rest))
    elif cmd == "failover-test":
        _cmd_failover_test()
    elif cmd == "providers":
        from .providers import setup_guide
        print(setup_guide(rest[0] if rest else None))
    elif cmd == "capabilities":
        from .tools import capabilities_guide
        print(capabilities_guide())
    elif cmd == "doctor":
        from .doctor import run
        sys.exit(0 if run() == 3 else 1)
    elif cmd == "solve":
        if not rest:
            print("usage: solve \"<goal>\" [--discover]   (--discover = find existing tools first)",
                  file=sys.stderr); sys.exit(2)
        disc = "--discover" in rest
        goal = " ".join(x for x in rest if x != "--discover")
        from .scaffold import run_verified
        r = run_verified(goal, executor=ShellExecutor(), discover=disc, verbose=True)
        print(f"\n=== result ===\ndone={r.done} verified={r.verified_steps} "
              f"failed={r.failed_steps}\n{r.summary}")
    elif cmd == "loop":
        if not rest:
            print("usage: loop \"<goal>\" [--exec]   (--exec = allowlisted shell, else plan-only)",
                  file=sys.stderr); sys.exit(2)
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

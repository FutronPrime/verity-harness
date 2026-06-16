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


def _cmd_web_setup():
    """Build the OPTIONAL walled-web reader venv (~/.verity-harness/venv) with Playwright +
    cryptography + Chromium. The harness CORE stays zero-dependency / pure-stdlib; this is an
    opt-in extra that enables reading auth-walled X Articles (the bare x.com/i/article/<id>
    permalink) through your own logged-in browser session. VERITY auto-detects this venv via
    tools._playwright_python(), so no PATH or env wiring is needed afterward."""
    import os
    import subprocess
    import sys
    import venv
    target = os.path.expanduser("~/.verity-harness/venv")
    binp = os.path.join(target, "Scripts" if os.name == "nt" else "bin")
    py = os.path.join(binp, "python.exe" if os.name == "nt" else "python")
    print(f"[web-setup] creating optional reader venv at {target} …")
    if not os.path.exists(py):
        venv.create(target, with_pip=True)
    subprocess.run([py, "-m", "pip", "install", "-q", "--upgrade", "pip"], check=False)
    print("[web-setup] installing playwright + cryptography …")
    r = subprocess.run([py, "-m", "pip", "install", "-q", "playwright", "cryptography"])
    if r.returncode != 0:
        print("[web-setup] pip install failed — see output above.", file=sys.stderr); sys.exit(1)
    print("[web-setup] downloading Chromium (one-time, ~170MB; shared across installs) …")
    subprocess.run([py, "-m", "playwright", "install", "chromium"], check=False)
    # AGENTIC AUTOMATION (the 'automate through blockers' arsenal): browser-use drives a real browser
    # to click/fill/navigate/log-in so long, multi-step tasks finish — the open-source CUA the discipline
    # gates tell the agent to reach for. Best-effort; the reader path above works without it.
    print("[web-setup] installing browser-use (agentic browser automation) …")
    subprocess.run([py, "-m", "pip", "install", "-q", "browser-use"], check=False)
    import shutil as _sh
    if _sh.which("npm"):
        print("[web-setup] installing openclick (accessibility-driven clicking, npm) …")
        subprocess.run(["npm", "install", "-g", "openclick"], check=False)
    else:
        print("[web-setup] (npm not found — skip openclick; browser-use covers agentic automation)")
    print("[web-setup] done ✅")
    print("  • Read walled X Articles:  python3 -m verity x-read \"https://x.com/i/article/<id>\"")
    print("    (be logged into x.com in Chrome — the cookie is auto-decrypted, never uploaded)")
    print("  • Agentic automation now available to the agent: browser-use (drive a browser to click/")
    print("    fill/login & get past blockers), plus openclick if npm was present. `verity capabilities`")
    print("    surfaces these so the agent USES them instead of giving up on an interactive page.")


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
    elif cmd in ("models", "registry"):
        # AUTHORITATIVE model lookup — read the live OpenRouter registry instead of guessing current
        # model ids from stale training. The right way to answer 'what's the newest X model'.
        from .tools import model_registry
        q = rest[0] if rest else ""
        if not q:
            print('usage: models <substring>   e.g. models deepseek | models claude-opus | models gemini\n'
                  '(reads the live OpenRouter /models registry — ground truth for current model ids)',
                  file=sys.stderr); sys.exit(2)
        print(model_registry(q, n=60))
    elif cmd == "playbook":
        # 'make any model think like Fable' — distill an injectable playbook from THIS harness's own
        # verified history (the assumptions it caught + the tools it found). --inject writes the file
        # the autostart context-inject appends every session.
        from . import ledger
        days = next((int(x) for x in rest if x.isdigit()), 30)
        if "--inject" in rest:
            p = ledger.write_playbook(days)
            print(f"[playbook] wrote {p} ({len(p.read_text())} chars) — autostart injects it each session.")
        else:
            print(ledger.playbook(days))
    elif cmd == "doctor":
        from .doctor import run
        sys.exit(0 if run() == 3 else 1)
    elif cmd == "proof":
        # The receipt: did the harness's gates actually fire, and what did they catch?
        from .ledger import proof
        days = int(rest[0]) if rest and rest[0].isdigit() else 1
        print(proof(days))
    elif cmd == "eval":
        # A/B: naive vs harness on assumption-trap questions. The delta = proof of difference.
        # --models "a,b,c" runs the A/B across SEVERAL models → proof the lift generalizes (rigor).
        if "--flagship" in rest:
            # the proof on enterprise + top-open models people actually deploy
            from .eval_assumptions import run_models, FLAGSHIP_MODELS
            run_models(FLAGSHIP_MODELS)
        elif "--models" in rest:
            i = rest.index("--models")
            models = [m.strip() for m in (rest[i + 1] if i + 1 < len(rest) else "").split(",") if m.strip()]
            # no explicit list → DEFAULT_MODELS (current set people actually run, not retired ids)
            from .eval_assumptions import run_models
            run_models(models or None)
        else:
            from .eval_assumptions import run as _eval
            _eval()
    elif cmd == "tasks":
        # GAIA/Seal-0-shaped GOAL benchmark: multi-step goals via the full agentic harness.
        # --swarm = run the harness arm through the multi-agent SWARM (coordination proof).
        # --models "a,b,c" = per-model A/B table.
        sw = "--swarm" in rest
        if "--models" in rest:
            i = rest.index("--models")
            ms = [m.strip() for m in (rest[i+1] if i+1 < len(rest) else "").split(",") if m.strip()]
            from .eval_tasks import run_models as _tm
            _tm(ms or None, harness_exec="--exec" in rest, use_swarm=sw)
        else:
            from .eval_tasks import run as _tasks
            _tasks(harness_exec="--exec" in rest, use_swarm=sw)
    elif cmd == "swebench":
        # SWE-Bench-style: test-scored bug fixing (the coding axis Fable 5 is ranked on).
        # --models "a,b,c" = per-model A/B table.
        if "--models" in rest:
            i = rest.index("--models")
            ms = [m.strip() for m in (rest[i+1] if i+1 < len(rest) else "").split(",") if m.strip()]
            from .eval_swebench import run_models as _sm
            _sm(ms or None)
        else:
            from .eval_swebench import run as _swe
            _swe()
    elif cmd in ("research-eval", "trending"):
        # RESEARCH benchmark: force the model to read the COMMUNITY (Reddit/X/GitHub/HN) for
        # trending/real-world knowledge it can't recall. --models "a,b,c" for a per-model table.
        if "--models" in rest:
            i = rest.index("--models")
            ms = [m.strip() for m in (rest[i+1] if i+1 < len(rest) else "").split(",") if m.strip()]
            from .eval_research import run_models as _rm
            _rm(ms or None)
        else:
            from .eval_research import run as _re
            _re()
    elif cmd == "autostart":
        # Wire VERITY to silently start with your agent (sync + proxy floor), no UI.
        from .autostart import main as _auto
        _auto(rest[0] if rest else "--print")
    elif cmd == "stop":
        # Stop the background proxy (close-on-exit / manual). No lingering RAM.
        from .server import stop
        print(stop())
    elif cmd == "dashboard":
        # Open the status face: proxy state, failover chain, live gate receipt, scorecard.
        from .dashboard import serve
        serve(open_browser="--no-open" not in rest)
    elif cmd == "swarm":
        # Multi-agent swarm: planner → researchers → executors → critic → synthesizer (gated).
        if not rest:
            print('usage: swarm "<goal>" [--exec]   (--exec = allowlisted shell for sub-tasks)',
                  file=sys.stderr); sys.exit(2)
        live = "--exec" in rest
        goal = " ".join(x for x in rest if x != "--exec")
        from .swarm import run_swarm
        ex = AllowlistShellExecutor() if live else None
        r = run_swarm(goal, executor=ex, verbose=True)
        print("\n=== FINAL (swarm) ===\n" + r.final)
    elif cmd == "solve":
        if not rest:
            print("usage: solve \"<goal>\" [--discover] [--gate \"<test/build/lint cmd>\"] "
                  "[--deadline <seconds>]\n"
                  "  --gate     objective completion gate: 'done' is rejected until this exits 0\n"
                  "             (a passing test, not the model's opinion — defeats Ralph-Wiggum loops)\n"
                  "  --deadline wall-clock hard stop in seconds (a loop with no kill-switch runs "
                  "until it burns the budget)", file=sys.stderr); sys.exit(2)
        disc = "--discover" in rest
        gate_cmd = None
        deadline = None
        toks = list(rest)
        for flag, setter in (("--gate", "gate"), ("--deadline", "deadline")):
            if flag in toks:
                i = toks.index(flag)
                val = toks[i + 1] if i + 1 < len(toks) else None
                if val is None:
                    print(f"{flag} needs a value", file=sys.stderr); sys.exit(2)
                if setter == "gate":
                    gate_cmd = val
                else:
                    try:
                        deadline = float(val)
                    except ValueError:
                        print("--deadline must be a number (seconds)", file=sys.stderr); sys.exit(2)
                del toks[i:i + 2]
        goal = " ".join(x for x in toks if x != "--discover")
        from .scaffold import run_verified
        r = run_verified(goal, executor=ShellExecutor(), discover=disc,
                         gate_cmd=gate_cmd, deadline_s=deadline, verbose=True)
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
    elif cmd in ("x-read", "read-x", "tweet"):
        if not rest:
            print("usage: x-read <x.com URL or tweet id>   (reads tweets AND long-form Articles, "
                  "no API key; bare /i/article/<id> needs a one-time cookie — it tells you how)",
                  file=sys.stderr); sys.exit(2)
        from .tools import fetch_tweet
        print(fetch_tweet(rest[0]))
    elif cmd in ("web-setup", "x-setup"):
        _cmd_web_setup()
    else:
        print(f"unknown command: {cmd}", file=sys.stderr); sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])

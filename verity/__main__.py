#!/usr/bin/env python3
"""CLI for the Verity Router.

  python3 -m verity tiers              # show routing order
  python3 -m verity ask "your prompt"  # route a prompt (verbose trail)
  python3 -m verity failover-test      # prove Tier1→Tier0 failover
  python3 -m verity providers [name]   # how to wire FREE LLM access
  python3 -m verity solve "<goal>"     # full discipline scaffold (real shell)
  python3 -m verity assimilate digest  # WATCH video for intel: scout channels → see (Gemini) → brief
"""
import json
import os
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
    elif cmd == "resources":
        # REUSE-FIRST resource library — curated awesome-lists + frameworks the agents consult
        # before reinventing. `resources <query>` searches; `resources --fetch <name>` opens a list live.
        from . import resources as _res
        if rest and rest[0] == "--fetch":
            if len(rest) < 2:
                print("usage: resources --fetch <name-or-url>", file=sys.stderr); sys.exit(2)
            print(_res.fetch_list(rest[1]))
        else:
            print(_res.search(" ".join(rest)))
    elif cmd == "memory":
        # Bounded-context persistent memory (membank): infinite store behind a fixed-budget injection.
        #   memory capture "<text>" [--scope decision|preference|lesson|project|fact|error]
        #   memory recall "<query>"        memory get <ids>        memory session-start
        #   memory stats                   memory lint <path-to-MEMORY.md|CLAUDE.md>
        from . import membank as _mb
        sub = rest[0] if rest else "stats"
        argrest = rest[1:]
        if sub == "capture":
            scope = "fact"
            if "--scope" in argrest:
                i = argrest.index("--scope"); scope = argrest[i + 1] if i + 1 < len(argrest) else "fact"
                argrest = argrest[:i] + argrest[i + 2:]
            print(_mb.capture(" ".join(argrest), scope=scope))
        elif sub == "recall":
            print(_mb.recall(" ".join(argrest)))
        elif sub == "get":
            print(_mb.get(" ".join(argrest)))
        elif sub in ("session-start", "session_start", "inject"):
            print(_mb.session_start())
        elif sub == "lint":
            if not argrest:
                print("usage: memory lint <path-to-MEMORY.md|CLAUDE.md|AGENTS.md>", file=sys.stderr); sys.exit(2)
            print(_mb.bootstrap_lint(argrest[0]))
        else:
            print(_mb.stats())
    elif cmd in ("eval-memory", "memory-proof"):
        # PROOF the memory + reuse-first layers work AND improve the system (deterministic; --llm adds A/B).
        from .eval_memory import run as _memrun
        jp = None
        if "--json" in rest:
            i = rest.index("--json"); jp = rest[i + 1] if i + 1 < len(rest) else "memory-proof.json"
        _memrun(with_llm="--llm" in rest, json_path=jp)
    elif cmd == "evolve":
        # Closed-loop self-evolution of the playbook, gated so it can only improve (never self-corrupt).
        #   evolve            → dry run (show the gate verdict + candidate)
        #   evolve --apply    → promote the candidate if it passes the non-regression safety gate
        #   evolve --eval     → also score champion-vs-candidate on a held-out trap split (costs API)
        from . import evolve as _evo
        r = _evo.evolve(apply="--apply" in rest, use_eval="--eval" in rest)
        print(f"[evolve] cycle {r['cycle']} · gate {'PASS' if r['gate_pass'] else 'REJECT'} — {r['gate']}")
        for k in ("dev_candidate", "dev_champion", "test_candidate", "test_champion", "eval_score", "eval_error"):
            if k in r:
                print(f"  {k}: {r[k]}")
        print(f"  promoted: {r['promoted']}" + ("" if r["promoted"] else "  (dry run — add --apply to adopt)"))
    elif cmd == "handle":
        # Pointer-indirection: resolve a stashed big-payload handle on demand.  handle get <verity://h/..>
        from . import handles as _h
        if rest and rest[0] == "get" and len(rest) > 1:
            print(_h.resolve(rest[1]))
        else:
            print("usage: handle get <verity://h/...>", file=sys.stderr); sys.exit(2)
    elif cmd == "doc":
        # RLM-style long-doc query: pull only relevant slices of a huge file.  doc <path> "<query>"
        from .longdoc import query_doc
        if len(rest) < 2:
            print('usage: doc <path> "<query>"', file=sys.stderr); sys.exit(2)
        print(query_doc(rest[0], " ".join(rest[1:])))
    elif cmd in ("video", "transcribe", "watch"):
        # Transcribe/analyse a video — NO captions required (Gemini multimodal). RULE 7: never skip a video.
        #   verity video <youtube_url> [--summary] [--model gemini-2.5-flash]
        from .video import transcribe
        url = next((a for a in rest if not a.startswith("--")), "")
        if not url:
            print('usage: verity video <youtube_url> [--summary] [--model <id>]', file=sys.stderr); sys.exit(2)
        model = "gemini-2.5-flash"
        if "--model" in rest:
            i = rest.index("--model")
            model = rest[i + 1] if i + 1 < len(rest) else model
        try:
            print(transcribe(url, model=model, summary=("--summary" in rest)))
        except RuntimeError as e:
            print(f"[video] {e}", file=sys.stderr); sys.exit(1)
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
    elif cmd == "demo":
        # The fun head-to-head: same model builds a real app (Tetris by default) RAW vs through the
        # harness (build → run headless → read console errors → fix → repeat). Artifacts in ./demo-out/.
        task = next((a for a in rest if not a.startswith("--")), None)
        if "--models" in rest:   # robust spread across many models, each its own demo-out/<slug>/
            i = rest.index("--models")
            ms = [m.strip() for m in (rest[i+1] if i+1 < len(rest) else "").split(",") if m.strip()]
            from .demo import run_models as _dm
            _dm(ms, task=task)
        else:
            from .demo import run as _demo
            model = None
            if "--model" in rest:
                i = rest.index("--model"); model = rest[i+1] if i+1 < len(rest) else None
            _demo(task=task, model=model)
    elif cmd == "mascot":
        # Launch the desktop pet (Truth Hawk / VERI) — a silent sign VERITY is installed + watching.
        import shutil, subprocess, pathlib
        appdir = pathlib.Path(__file__).resolve().parent.parent / "desktop-mascot"
        if not shutil.which("npm"):
            print("The desktop mascot needs Node/npm + Electron. Install Node, then:\n"
                  f"  cd {appdir} && npm install && npm start", file=sys.stderr); sys.exit(1)
        if not (appdir / "node_modules").exists():
            print("[mascot] first run — installing Electron (one-time)…")
            subprocess.run(["npm", "install"], cwd=str(appdir))
        print("[mascot] launching the Truth Hawk — right-click the tray 'V' to switch/hide.")
        subprocess.Popen(["npm", "start"], cwd=str(appdir))
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
    elif cmd == "promptos":
        # Print the portable Synapse_COR prompt-software orchestrator. Drop it into ANY blank LLM
        # (local or frontier) and it orchestrates to VERITY's contract — model-agnostic, fork-able.
        # Set VERITY_PROMPTOS=1 to make the swarm planner run on it.
        from .promptos import ORCHESTRATOR_PROMPT
        print(ORCHESTRATOR_PROMPT)
    elif cmd == "coordinate":
        # The learned ROUTING cheat-sheet (distilled from this harness's own swarm runs). Show it, or
        # --promote to distill recent history → ~/.verity-harness/routing.md (the planner reviews it
        # before every decomposition). This is the 'learn' half of coordination, no weights.
        from . import coordinate as _coord
        if "--promote" in rest:
            ok, msg = _coord.promote_routing()
            print(("✓ " if ok else "✗ ") + msg)
        else:
            cs = _coord.learned_routing()
            print(cs or "[routing cheat-sheet empty — fills as you run `verity swarm` on real goals]")
    elif cmd == "discover":
        # Evolutionary search over COORDINATION STRATEGIES (ADAS/AFlow paradigm, frozen model + evaluator).
        # --propose: model mutates a new candidate (no eval). --eval [--apply]: full propose→measure→gate→promote.
        from . import discover as _disc
        if "--eval" in rest:
            print(__import__("json").dumps(
                _disc.discover(propose="--no-propose" not in rest, use_eval=True, apply="--apply" in rest),
                indent=2))
        elif "--propose" in rest:
            print(__import__("json").dumps(_disc.discover(propose=True, use_eval=False, apply=False), indent=2))
        else:
            bank = _disc._load_bank()
            champ = bank.get("champion")
            print(f"strategy bank — {len(bank['population'])} strategies, cycle {bank.get('cycle', 0)}")
            print(f"champion: {champ['name'] if champ else '(none yet — run discover --eval --apply)'}")
            for s in bank["population"]:
                sc = f"  [score {s['score']:.3f}]" if s.get("score") is not None else ""
                print(f"  · {s['name']}{sc}")
    elif cmd == "learn":
        # Subject acquisition loop: search web/GitHub for skills/repos/docs on a subject → distill →
        # PERSIST to per-user memory (recalled automatically in future tasks). On-the-job training.
        if not rest:
            print('usage: learn "<subject>" [--rounds N] [--show]', file=sys.stderr); sys.exit(2)
        from . import learn as _learn
        if "--show" in rest:
            print(_learn.show(" ".join(x for x in rest if x != "--show")))
        else:
            rounds = 1
            r2 = list(rest)
            if "--rounds" in r2:
                i = r2.index("--rounds")
                try:
                    rounds = int(r2[i + 1]); del r2[i:i + 2]
                except (IndexError, ValueError):
                    del r2[i:i + 1]
            subj = " ".join(x for x in r2 if not x.startswith("--"))
            res = _learn.learn(subj, rounds=rounds, verbose=True)
            print("\n" + ("✓ learned + persisted: " + subj if res["learned"]
                          else "✗ " + res.get("msg", "nothing learned")))
    elif cmd == "looplib":
        # Forward Future's Loop Library — vetted agentic-workflow recipes. Sync the catalog, search it,
        # read a full recipe, or seed the discovery strategy bank with human-vetted loops.
        from . import looplib as _ll
        if "--sync" in rest:
            print(_ll.sync())
        elif "--seed-discover" in rest:
            from . import discover as _D
            bank = _D._load_bank(); have = {s["name"] for s in bank["population"]}
            added = [s for s in _ll.seed_strategies(n=12, allow_fetch=True) if s["name"] not in have]
            bank["population"] += added; _D._save_bank(bank)
            print(f"✓ seeded {len(added)} Loop-Library strategies into the discovery population "
                  f"({len(bank['population'])} total)")
        elif rest and rest[0] == "get":
            print(_ll.render(_ll.get(rest[1]) if len(rest) > 1 else None))
        elif rest:
            hits = _ll.match(" ".join(rest), n=8, allow_fetch=True)
            print("\n".join(f"  [{lp.get('slug')}] {lp.get('title')} — {str(lp.get('useWhen',''))[:90]}"
                            for lp in hits) or "[no matching loops — run `verity looplib --sync`]")
        else:
            ls = _ll.loops(allow_fetch=True)
            print(f"Loop Library — {len(ls)} loops. `verity looplib <query>`, `… get <slug>`, `… --seed-discover`.")
            for lp in ls[:50]:
                print(f"  {lp.get('number')} [{lp.get('category',{}).get('slug')}] {lp.get('slug')}: {lp.get('title')}")
    elif cmd == "gc":
        # Memory maintenance — keep the self-evolving stores BOUNDED over the long horizon (membank rows,
        # ledger day-files, guard counters, discovery pool). Injection is already char-capped; this caps DISK.
        from . import maintenance
        maintenance.gc(verbose=True)
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
        # AUTO-ESCALATE multi-part goals to the SWARM. Measured: the single-agent loop REGRESSES on
        # complex/coordination goals (esp. on weaker models — it loses the thread over many steps),
        # while the swarm (decompose → grunt-workers retrieve → critic → synthesize) completes them.
        # A no-gate complex goal routes to the swarm; a goal with an objective --gate stays single-loop
        # (the gate IS the discipline there). Force either with `verity swarm` / `--no-swarm`.
        from .swarm import should_swarm
        if "--no-swarm" not in toks and not gate_cmd and should_swarm(goal):
            print("[solve] multi-part goal → escalating to the multi-agent swarm (more reliable here).")
            from .swarm import run_swarm
            res = run_swarm(goal, executor=ShellExecutor() if "--exec" in toks else None, verbose=True)
            print(f"\n=== result (swarm) ===\n{res.final}")
        else:
            from .scaffold import run_verified
            r = run_verified(goal, executor=ShellExecutor(), discover=disc,
                             gate_cmd=gate_cmd, deadline_s=deadline, verbose=True)
            print(f"\n=== result ===\ndone={r.done} verified={r.verified_steps} "
                  f"failed={r.failed_steps}\n{r.summary}")
    elif cmd == "synthesize":
        if not rest:
            print("usage: synthesize \"<goal>\" [--build] [--gate \"<verify cmd>\"] [--deadline <s>]\n"
                  "  Builds whatever DIGITAL capability the goal needs: decompose → reuse-first discover →\n"
                  "  plan → [build if missing] → verify → register. Plan-only unless --build + --gate given\n"
                  "  (the gate is the objective 'it works' test — no claiming done without it).",
                  file=sys.stderr); sys.exit(2)
        build = "--build" in rest
        gate = deadline = None
        toks = list(rest)
        for flag in ("--gate", "--deadline"):
            if flag in toks:
                i = toks.index(flag)
                val = toks[i + 1] if i + 1 < len(toks) else None
                if val is None:
                    print(f"{flag} needs a value", file=sys.stderr); sys.exit(2)
                if flag == "--gate":
                    gate = val
                else:
                    try: deadline = float(val)
                    except ValueError:
                        print("--deadline must be seconds", file=sys.stderr); sys.exit(2)
                del toks[i:i + 2]
        goal = " ".join(x for x in toks if x != "--build")
        from .synthesize import synthesize
        synthesize(goal, build=build, gate=gate, deadline=deadline, verbose=True)
    elif cmd in ("synth-list", "synthesized"):
        from .synthesize import list_capabilities
        print(list_capabilities())
    elif cmd == "desktop":
        # VERITY's desktop HANDS — passthrough to agent-desktop (observe→act on any macOS app via the
        # accessibility tree). Lets the harness drive GUIs autonomously instead of deferring to the user.
        import shutil as _sh, subprocess as _sp
        ad = _sh.which("agent-desktop") or os.path.expanduser("~/.npm-global/bin/agent-desktop")
        if not os.path.exists(ad) and not _sh.which("agent-desktop"):
            print("agent-desktop not installed (VERITY's desktop hands). Install: npm i -g agent-desktop\n"
                  "Then: verity desktop snapshot | find | click | type | select | screenshot | ...",
                  file=sys.stderr); sys.exit(2)
        if not rest:
            print("usage: verity desktop <snapshot|find|click|type|select|screenshot|...>  (wraps agent-desktop)\n"
                  "  observe→act loop for any macOS app. Learn it: verity desktop skills get desktop",
                  file=sys.stderr); sys.exit(2)
        sys.exit(_sp.run([ad, *rest]).returncode)
    elif cmd == "voice":
        from . import voice as _v
        sub = rest[0] if rest else "status"
        if sub == "say":
            words = [w for w in rest[1:] if w != "--tldr"]
            if not words:
                print("usage: verity voice say [--tldr] \"<text>\"", file=sys.stderr); sys.exit(2)
            r = _v.say(" ".join(words), verbose=True, force=True, tldr=("--tldr" in rest))
            if not r.get("spoke"):
                print(f"[voice] did not speak: {r.get('reason','')}", file=sys.stderr)
        elif sub == "pipe":
            # wrap a CLI agent and speak its replies as persona TL;DRs: verity voice pipe <cmd> [args...]
            print(json.dumps(_v.pipe(rest[1:]), indent=2))
        elif sub == "listen":
            # default = press-ENTER (reliable, mic-only); --ptt = hold key (needs Input Monitoring); --vad = hands-free
            print(json.dumps(_v.listen(ptt=("--ptt" in rest), vad=("--vad" in rest)), indent=2))
        elif sub == "dictate":
            # VOICE INPUT into your REAL assistant: mic -> Whisper -> types into the focused app.
            # --ptt hold-key (seamless) · --vad hands-free · --submit press Return after · --app "<Name>" target app
            _app = None
            if "--app" in rest:
                _i = rest.index("--app")
                _app = rest[_i + 1] if _i + 1 < len(rest) else None
            print(json.dumps(_v.dictate(ptt=("--ptt" in rest), vad=("--vad" in rest),
                                        submit=("--submit" in rest), app=_app), indent=2))
        elif sub == "train":
            if len(rest) < 3:
                print("usage: verity voice train <style> <clip-path>  (style = standard|lcars|aisha|avani|…)\n"
                      "  registers a rights-clean clip YOU supply as that style's voice (sources nothing).",
                      file=sys.stderr); sys.exit(2)
            print(json.dumps(_v.train(rest[1], rest[2]), indent=2))
        elif sub == "watch":
            _v.watch()
        else:
            print(_v.status())
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
    elif cmd in ("council", "panel"):
        # COUNCIL-MODE eval (researched from karpathy/llm-council): N tiers answer →
        # anonymized blind cross-ranking → chairman synthesis. Stronger panel+judge.
        #   verity council [--members N] "<question>"
        from . import council as _council
        sys.exit(_council._cli(rest))
    elif cmd in ("persist", "cant-check", "dont-quit"):
        # R60 PERSISTENCE GATE — block a "can't / wait for you" conclusion unless
        # the ledger proves real multi-source research (or a human gate is named).
        #   verity persist "<draft conclusion>"            → gate it (exit 2 = BLOCKED)
        #   verity persist note <source> "<query>" [found] → log a research receipt
        from . import persist as _persist
        sys.exit(_persist._cli(rest))
    elif cmd in ("assimilate", "watch-learn", "assim"):
        # FUTRON Assimilation Loop: Scout (YouTube RSS) → Filter (triage vs goals) →
        # Assimilate (claude-watch: scene frames + transcript) → Synthesize (membank).
        # Turns video into queryable knowledge, triage-first so a backlog can't nuke tokens.
        from . import assimilate as _assim
        _assim.cli(rest)
    else:
        print(f"unknown command: {cmd}", file=sys.stderr); sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])

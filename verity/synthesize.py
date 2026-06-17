"""Capability-Synthesis — VERITY builds whatever DIGITAL capability a goal needs.

The Architect's "Prompt Software Generator" reborn as a harness loop, grounded by VERITY's own gates:

    DECOMPOSE → DISCOVER (reuse-first, triple-checked) → PLAN → [BUILD if missing] → VERIFY → REGISTER

The thesis: an agent shouldn't stop at "I don't have a tool for that." It should look hard for an
existing one (installed tools, curated OSS, the web), and if none exists after a real search, design and
BUILD the missing tool/workflow, verify it works, and register it so it's reused next time. Bounded only by:
  • hardware/tech that doesn't exist,
  • scientific law/equation not yet understood (still research + attempt, then report honestly),
  • anything the safety rules deem unsafe/prohibited.
Everything else digital is in scope. Pure stdlib + VERITY internals (scaffold/resources/tools/router).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time

from . import resources, tools

CAP_DIR = pathlib.Path(os.path.expanduser("~/.verity-harness/capabilities"))

# ── Safety boundary — the ONLY digital things VERITY won't help build (aligns with the system rules) ──
_UNSAFE = re.compile(r"""(?ix)
    ( malware | ransomware | keylogger | spyware | rootkit | botnet | \bddos\b | denial[\s-]of[\s-]service
    | exfiltrat | steal\s+(credentials|passwords|data) | crack\s+(password|license|drm) | bypass\s+(auth|2fa|drm|paywall)
    | phish | spoof\s+identity | forge\s+(document|signature) | bio[\s-]?weapon | explosive | \bnerve\s+agent\b
    | child\s+(porn|sexual) | csam | mass[\s-]surveillance\s+of )
""")


def _slug(s: str, n: int = 48) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:n] or "goal"


def _shim_ask(system: str, prompt: str, timeout: int = 180) -> str:
    """Live fallback when the router's tiers are down: the local OAuth shim (OpenAI-compatible, :11445).
    Same endpoint VERITY's persona screening uses — reliably up via DJ's flat-fee frontier subscription."""
    import json as _json
    import urllib.request
    url = os.getenv("FUTRON_SHIM_URL", "http://127.0.0.1:11445/v1/chat/completions")
    body = _json.dumps({"messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": prompt}], "temperature": 0.3}).encode()
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = _json.loads(resp.read())
        return (data.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
    except Exception:
        return ""


def safety_check(goal: str) -> str | None:
    """Return a refusal reason if the goal is in the prohibited set, else None."""
    if _UNSAFE.search(goal or ""):
        return ("[SYNTHESIS BLOCKED — safety boundary] This goal falls in the prohibited set "
                "(malware/exploitation/weapons/abuse/illegal surveillance). VERITY will not help build it. "
                "Everything else digital is in scope.")
    return None


def _prior_capabilities(goal: str, n: int = 5) -> list[dict]:
    """Compounding loop: have we already synthesized something for a similar goal? (reuse our own past builds)"""
    if not CAP_DIR.exists():
        return []
    words = {w for w in re.split(r"\W+", (goal or "").lower()) if len(w) > 3}
    hits = []
    for f in CAP_DIR.glob("*.json"):
        try:
            rec = json.loads(f.read_text())
        except Exception:
            continue
        hay = (rec.get("goal", "") + " " + " ".join(rec.get("capabilities", []))).lower()
        score = sum(1 for w in words if w in hay)
        if score:
            hits.append((score, rec))
    hits.sort(key=lambda x: -x[0])
    return [r for _, r in hits[:n]]


def discover(goal: str) -> dict:
    """Reuse-first discovery — surface what ALREADY exists before proposing to build (triple-check sources)."""
    reuse = resources.reuse_hint(goal, n=6)            # curated OSS / awesome-lists
    try:
        registry = tools.registry_hint(goal, n=25)     # installed VERITY/system tools
    except Exception:
        registry = ""
    prior = _prior_capabilities(goal)
    return {"reuse": reuse, "registry": registry, "prior": prior}


_PLAN_SYS = (
    "You are VERITY's Capability-Synthesis planner. Given a GOAL and a reuse-first DISCOVERY context, "
    "produce a TIGHT, executable plan to give the agent the capability to accomplish the goal. RULES: "
    "(1) REUSE-FIRST — if an existing tool in DISCOVERY fits, the plan is to USE it (name it); only propose "
    "BUILDING what genuinely has no existing option. (2) For each thing to BUILD, give: name, one-line purpose, "
    "inputs→outputs, the concrete steps, dependencies (PREFER zero-dep/stdlib or a named existing library), and "
    "the OBJECTIVE VERIFICATION gate (a command/test whose pass means it works — not an opinion). (3) Flag any "
    "step that needs a genuine human boundary (credentials, payment, irreversible/outward action). (4) If the goal "
    "needs nonexistent hardware or not-yet-understood science, say so and propose the research to attempt it. "
    "Output concise markdown with sections: REUSE (use these existing), BUILD (gaps + specs + verify-gate), "
    "RISKS/BOUNDARIES, FIRST STEP."
)


def _plan_prompt(goal: str, capabilities: list[str], disc: dict) -> str:
    prior = ""
    if disc["prior"]:
        prior = "PRIOR VERITY-BUILT CAPABILITIES (reuse if they fit):\n" + "\n".join(
            f"  • {r.get('goal','?')} → {r.get('slug','')}" for r in disc["prior"]) + "\n\n"
    return (
        f"GOAL: {goal}\n\n"
        f"DECOMPOSED CAPABILITIES NEEDED:\n" + "\n".join(f"  - {c}" for c in capabilities) + "\n\n"
        f"{prior}"
        f"DISCOVERY — installed tools to REUSE:\n{disc['registry'] or '  (none surfaced)'}\n\n"
        f"DISCOVERY — curated OSS / awesome-lists to REUSE:\n{disc['reuse'] or '  (none surfaced)'}\n\n"
        f"Now produce the plan."
    )


def synthesize(goal: str, build: bool = False, gate: str | None = None,
               deadline: float | None = None, verbose: bool = True) -> dict:
    """Run the capability-synthesis loop for a goal. Plan-only by default; --build executes a verified build."""
    blocked = safety_check(goal)
    if blocked:
        if verbose:
            print(blocked)
        return {"goal": goal, "blocked": blocked}

    # 1. DECOMPOSE
    try:
        from .scaffold import decompose
        capabilities = decompose(goal) or [goal]
    except Exception:
        capabilities = [goal]
    if verbose:
        print(f"[synthesize] goal: {goal}")
        print(f"[synthesize] capabilities: {capabilities}")

    # 2. DISCOVER (reuse-first, triple-checked)
    disc = discover(goal)
    if verbose:
        print("[synthesize] discovery done (installed + OSS + prior builds)")

    # 3. PLAN (LLM, grounded in discovery — sovereign router first, OAuth shim as a live fallback)
    user_prompt = _plan_prompt(goal, capabilities, disc)
    plan = ""
    try:
        from .router import ask
        try:
            plan = ask(user_prompt, system=_PLAN_SYS) or ""
        except TypeError:
            plan = ask(_PLAN_SYS + "\n\n" + user_prompt) or ""
    except Exception:
        plan = ""
    if not plan.strip():
        plan = _shim_ask(_PLAN_SYS, user_prompt) or (
            "[plan generation unavailable: no LLM tier reachable — router tiers down AND OAuth shim "
            "(:11445) unreachable. Discovery context saved below; re-run when a model tier is up.]")
    if verbose:
        print("\n=== CAPABILITY PLAN ===\n" + plan + "\n")

    # 4. BUILD (optional — only with an OBJECTIVE gate, so 'done' is earned not claimed)
    built = None
    if build:
        if not gate:
            print("[synthesize] --build needs --gate \"<verify cmd>\" (objective completion gate). Skipping build.")
        else:
            from .scaffold import run_verified
            from .loop import ShellExecutor
            r = run_verified(goal, executor=ShellExecutor(), gate_cmd=gate,
                             deadline_s=deadline, verbose=verbose)
            built = {"done": r.done, "verified_steps": r.verified_steps,
                     "failed_steps": r.failed_steps, "summary": r.summary}

    # 5. REGISTER (compounding — future discovery reuses this)
    rec = {"goal": goal, "slug": _slug(goal), "ts": int(time.time()),
           "capabilities": capabilities, "plan": plan,
           "reuse": disc["reuse"], "registry_excerpt": disc["registry"][:1500], "built": built}
    try:
        CAP_DIR.mkdir(parents=True, exist_ok=True)
        (CAP_DIR / f"{rec['slug']}.json").write_text(json.dumps(rec, indent=2))
        if verbose:
            print(f"[synthesize] registered → {CAP_DIR / (rec['slug'] + '.json')}")
    except Exception as e:
        if verbose:
            print(f"[synthesize] register failed: {e}")
    return rec


def list_capabilities() -> str:
    """`verity capabilities` — list previously synthesized capabilities (the compounding registry)."""
    if not CAP_DIR.exists() or not any(CAP_DIR.glob("*.json")):
        return "No synthesized capabilities yet. Build one: verity synthesize \"<goal>\""
    lines = ["Synthesized capabilities (reused by future `verity synthesize` discovery):"]
    for f in sorted(CAP_DIR.glob("*.json")):
        try:
            r = json.loads(f.read_text())
            built = "✓ built" if (r.get("built") or {}).get("done") else "plan"
            lines.append(f"  [{built:7}] {r.get('goal','?')}  ({f.name})")
        except Exception:
            continue
    return "\n".join(lines)

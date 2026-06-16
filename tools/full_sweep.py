#!/usr/bin/env python3
"""Comprehensive multi-model × multi-capability A/B sweep — writes structured results incrementally
(crash-safe) to /tmp/verity-sweep.json. Each cell = same model, harness off (naive) vs on; lift = delta.

Bounded by design (cost-aware): accuracy on all reachable models; coding/memory/research/coordination on
representative subsets (the expensive ones). Per-model + per-eval try/except so one failure never kills
the run. Honest: only gradeable A/B evals here — non-gradeable capabilities are mapped separately in the README.
"""
import json, os, sys, time, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verity.config import Tier
from verity import eval_assumptions, eval_swebench, eval_research, eval_tasks

OUT = "/tmp/verity-sweep.json"
KEY = os.environ.get("OPENROUTER_API_KEY", "")
OR = "https://openrouter.ai/api/v1"

# reachable models (probed live) — (display, openrouter_slug_or_local, is_local)
MODELS = [
    ("claude-opus-4.8", "anthropic/claude-opus-4-8", False),
    ("gpt-5.5", "openai/gpt-5.5", False),
    ("gemini-3.1-pro", "google/gemini-3.1-pro-preview", False),
    ("glm-5.1", "z-ai/glm-5.1", False),
    ("gpt-4o-mini", "openai/gpt-4o-mini", False),
    ("gemini-2.5-flash", "google/gemini-2.5-flash", False),
    ("llama-3.3-70b", "meta-llama/llama-3.3-70b-instruct", False),
    ("gemma-4-31b", "google/gemma-4-31b-it", False),
    ("local-qwen-4b", "huihui_ai/qwen3.5-abliterated:4b", True),
]
# which axes per model (cost-bounded): A=accuracy C=coding M=memory R=research X=coordination(swarm)
PLAN = {
    # cost-bounded: A/C/M are cheap-ish across models; the EXPENSIVE axes (R=research tool-calls,
    # X=multi-agent swarm) run ONLY on cheap gpt-4o-mini as the representative — so the overnight run
    # can't burn hours/$$ on a flagship swarm. Coordination/research lift also has prior verified runs.
    "claude-opus-4.8": "ACM", "gpt-5.5": "ACM", "gemini-3.1-pro": "ACM", "glm-5.1": "AC",
    "gpt-4o-mini": "ACMRX", "gemini-2.5-flash": "A", "llama-3.3-70b": "AC",
    "gemma-4-31b": "A", "local-qwen-4b": "ACM",
}


def tier(slug, local):
    if local:
        return Tier(name="local", protocol="openai", base_url="http://127.0.0.1:11434/v1", model=slug, timeout_s=90)
    return Tier(name="cloud", protocol="openai", base_url=OR, model=slug, api_key=KEY, timeout_s=90)


def cell(fn, t, **kw):
    try:
        r = fn(tiers=[t], verbose=False, **kw)
        return {"naive": r.get("naive_correct", r.get("naive_pass", 0)),
                "harness": r.get("harness_correct", r.get("harness_pass", 0)),
                "total": r.get("traps", r.get("tasks", r.get("total", 0))),
                "lift": r.get("lift", 0)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"[:120]}


def main():
    results = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "axes": {
        "A": "accuracy (current-knowledge traps)", "C": "coding (test-scored)",
        "M": "memory (continuity A/B)", "R": "research (forced social search)",
        "X": "coordination (multi-agent swarm)"}, "models": {}}

    def save():
        json.dump(results, open(OUT, "w"), indent=2)

    for disp, slug, local in MODELS:
        t = tier(slug, local)
        axes = PLAN.get(disp, "A")
        results["models"][disp] = {}
        for ax in axes:
            print(f"[sweep] {disp} · {ax} …", flush=True)
            t0 = time.time()
            if ax == "A":
                c = cell(eval_assumptions.run, t)
            elif ax == "C":
                c = cell(eval_swebench.run, t)
            elif ax == "M":
                # memory: deterministic proofs are model-independent; here we grade the LLM A/B for THIS model
                c = _mem_ab(t)
            elif ax == "R":
                c = cell(eval_research, t) if callable(getattr(eval_research, "__call__", None)) else cell(eval_research.run, t)
            elif ax == "X":
                c = cell(eval_tasks.run, t, use_swarm=True)
            else:
                continue
            c["secs"] = round(time.time() - t0, 1)
            results["models"][disp][ax] = c
            save()
            print(f"[sweep] {disp} · {ax} → {c}", flush=True)
    results["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save()
    print(f"[sweep] DONE → {OUT}", flush=True)


def _mem_ab(t):
    """Per-model memory continuity A/B (without vs with injected bounded block)."""
    import tempfile, importlib
    os.environ["VERITY_MEMBANK_DB"] = os.path.join(tempfile.mkdtemp(), "mb.db")
    from verity import membank
    importlib.reload(membank)
    from verity.router import chat
    secret = "The internal FUTRON build token for project ZephyrX is ZX-7741-QODA."
    membank.capture(secret, scope="fact", project="zephyrx")
    q = "What is the internal FUTRON build token for project ZephyrX? Reply with ONLY the token."
    tok = "ZX-7741-QODA"

    def txt(r):
        return r.text if hasattr(r, "text") else str(r)
    try:
        no_mem = txt(chat([{"role": "user", "content": q}], tiers=[t]))
        inj = membank.session_start(project="zephyrx", budget_chars=1500)
        with_mem = txt(chat([{"role": "user", "content": inj + "\n\n" + q}], tiers=[t]))
        return {"naive": int(tok in no_mem), "harness": int(tok in with_mem), "total": 1,
                "lift": int(tok in with_mem) - int(tok in no_mem)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}"[:80]}


if __name__ == "__main__":
    main()

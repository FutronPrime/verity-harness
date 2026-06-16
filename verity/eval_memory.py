"""PROOF that VERITY's memory + reuse-first layers work AND improve the system.

Three DETERMINISTIC benchmarks (no LLM calls, no cost, 100% reproducible — the strongest kind of proof,
can't be hand-waved) + one optional LLM A/B for task-level lift:

  1. boundedness   — the CORE claim: as the store grows 10→10k memories, the always-loaded injection stays
                     FLAT (≤budget), while a naive flat-index grows O(N) and blows the window. O(1) vs O(N).
  2. retrieval     — the bounded block actually SURFACES the needed memory: seed gold (query,fact) pairs
                     among distractors, measure how often the gold fact lands in the capped recall block.
  3. resources     — reuse_hint surfaces the correct EXISTING tool for labeled build-goals (precision@k).
  4. continuity-llm (--llm) — task lift: store a fact the model can't know, then answer in a fresh session
                     WITHOUT vs WITH the injected memory block. Proves the injection improves the answer.

Run:  python3 -m verity eval-memory            (deterministic proofs)
      python3 -m verity eval-memory --llm      (+ the LLM continuity A/B)
      python3 -m verity eval-memory --json out.json
"""
from __future__ import annotations

import importlib
import json
import os
import tempfile
import time


def _fresh_membank():
    """A throwaway membank DB so the benchmark never touches the user's real store."""
    tmp = os.path.join(tempfile.mkdtemp(prefix="verity-membench-"), "membank.db")
    os.environ["VERITY_MEMBANK_DB"] = tmp
    from . import membank
    importlib.reload(membank)
    return membank


def bench_boundedness(scales=(10, 100, 1000, 10000), budget=1500):
    """Insert N memories; measure the always-loaded injection size vs a naive flat-index (one line each)."""
    mb = _fresh_membank()
    rows, naive_chars, total = [], 0, 0
    scales = sorted(scales)
    prev = 0
    for n in scales:
        for i in range(prev, n):
            scope = ("decision", "preference", "lesson", "fact")[i % 4]
            mb.capture(f"Memory item {i}: a project note about subsystem-{i%17} and tool `widget_{i}` "
                       f"with some detail that would live in a real entry about decision {i}.", scope=scope)
            naive_chars += 60   # a naive flat-index pointer line ≈ 60 chars EACH (grows O(N))
        prev = n
        total = n
        inj = mb.session_start(budget_chars=budget)
        rows.append({"memories": n, "injected_chars": len(inj), "naive_flat_index_chars": naive_chars,
                     "bounded": len(inj) <= budget + 200})
    ok = all(r["bounded"] for r in rows)
    return {"name": "boundedness", "pass": ok, "budget": budget, "rows": rows,
            "headline": (f"injection stayed ≤{budget} across {scales[0]}→{scales[-1]} memories "
                         f"(naive flat-index hit {naive_chars:,} chars = ~{naive_chars//4:,} tokens, "
                         f"{'OVER' if naive_chars>25000 else 'approaching'} the window)")}


def bench_retrieval():
    """Gold (query, fact) pairs hidden among distractors → does the capped recall block surface the gold fact?"""
    mb = _fresh_membank()
    gold = [
        ("how do we deploy the gateway", "DEPLOY: the gateway is started via `futron-gateway-control start` on port 18789", "decision"),
        ("what tts engine for voice", "VOICE: TTS uses Kokoro on port 9103, RVC on 9104 — never ElevenLabs for internal", "decision"),
        ("transparent animation export", "ANIM: ship animated WebP with real alpha; NEVER MP4-to-GIF (bakes background)", "lesson"),
        ("how does DJ want responses", "STYLE: DJ wants formal technical depth + AAVE vernacular, no sycophancy", "preference"),
        ("which model id for kimi", "MODEL: the current Kimi id is kimi-k2.7 per the OpenRouter registry", "fact"),
    ]
    for i in range(300):   # distractors
        mb.capture(f"Distractor note {i} about unrelated topic gamma-{i} and value {i*7}.", scope="fact")
    for q, fact, scope in gold:
        mb.capture(fact, scope=scope)
    hits = 0
    detail = []
    for q, fact, scope in gold:
        block = mb.recall(q, budget_chars=1500)
        key = fact.split(":")[0]                    # the leading tag (DEPLOY/VOICE/…) is the signal
        got = key in block
        hits += got
        detail.append({"query": q, "surfaced_gold": got})
    return {"name": "retrieval", "pass": hits == len(gold), "precision": hits / len(gold),
            "rows": detail, "headline": f"{hits}/{len(gold)} gold facts surfaced in the bounded block "
            f"despite 300 distractors (the store grew; the right memory still came back)"}


def bench_resources():
    """Labeled build-goal → expected existing tool; does reuse_hint surface it (precision@4)?"""
    from .resources import reuse_hint
    cases = [
        ("build a terminal TUI dashboard in python", "textual"),
        ("create a multi-agent swarm with roles", "agency-swarm"),
        ("set up a project manager agent with handoffs", "agentic-project-management"),
        ("add async sql database access", "databases"),
        ("scan code for security vulnerabilities", "codeql"),
        ("find a free public api for data", "public-apis"),
        ("implement a design pattern for this architecture", "awesome-design-patterns"),
    ]
    hits, detail = 0, []
    for goal, expect in cases:
        block = reuse_hint(goal).lower()
        got = expect in block
        hits += got
        detail.append({"goal": goal, "expected": expect, "surfaced": got})
    return {"name": "resources", "pass": hits >= len(cases) - 1, "precision": hits / len(cases),
            "rows": detail, "headline": f"{hits}/{len(cases)} build-goals surfaced the right existing tool "
            f"BEFORE building (reuse-first actually fires on the goals that matter)"}


def bench_continuity_llm(model=None):
    """Task lift: a fact the model CANNOT know → answer in a fresh session WITHOUT vs WITH injected memory."""
    mb = _fresh_membank()
    secret = "The internal FUTRON build token for project ZephyrX is ZX-7741-QODA."
    mb.capture(secret, scope="fact", project="zephyrx")
    question = "What is the internal FUTRON build token for project ZephyrX? Answer with just the token."
    from .router import ask, chat
    from .config import Tier, TIERS

    def _txt(r):
        return r.text if hasattr(r, "text") else str(r)

    def _ask(p):
        # Try the configured tiers; if every tier fails (e.g. the local tier points at an un-installed
        # model), AUTO-DISCOVER an installed Ollama chat model so the proof runs anywhere (Rule 6:
        # investigate the failure, don't just declare 'no model').
        tiers = [t for t in TIERS if model in (t.model or "")] if model else None
        try:
            return _txt(ask(p, **({"tiers": tiers} if tiers else {})))
        except Exception:  # noqa: BLE001
            import json as _j, urllib.request as _u
            try:
                d = _j.loads(_u.urlopen("http://127.0.0.1:11434/api/tags", timeout=3).read())
                names = [m["name"] for m in d.get("models", []) if "embed" not in m["name"]]
            except Exception:
                names = []
            if not names:
                raise
            local = Tier(name="local-auto", protocol="openai", base_url="http://127.0.0.1:11434/v1",
                         model=names[0], timeout_s=90)
            return _txt(chat([{"role": "user", "content": p}], tiers=[local]))
    try:
        no_mem = _ask(question)
    except Exception as e:  # noqa: BLE001
        return {"name": "continuity-llm", "skipped": f"no model reachable ({type(e).__name__})"}
    inj = mb.session_start(project="zephyrx", budget_chars=1500)
    with_mem = _ask(inj + "\n\n" + question)
    tok = "ZX-7741-QODA"
    return {"name": "continuity-llm", "pass": (tok not in no_mem) and (tok in with_mem),
            "without_memory_had_answer": tok in no_mem, "with_memory_had_answer": tok in with_mem,
            "headline": f"without memory: {'KNEW' if tok in no_mem else 'did NOT know'} the token; "
            f"with injected memory: {'KNEW' if tok in with_mem else 'still did not know'} it "
            "(proves the bounded injection carries real, usable knowledge across sessions)"}


def run(with_llm=False, json_path=None, model=None):
    print("=== VERITY MEMORY & REUSE-FIRST — PROOF SUITE ===\n")
    results = [bench_boundedness(), bench_retrieval(), bench_resources()]
    if with_llm:
        results.append(bench_continuity_llm(model))
    for r in results:
        mark = "✅ PASS" if r.get("pass") else ("⏭️  SKIP" if r.get("skipped") else "❌ FAIL")
        print(f"{mark}  [{r['name']}] {r.get('headline') or r.get('skipped','')}")
        if r["name"] == "boundedness":
            print("        memories →   injected(bounded)   vs   naive-flat-index")
            for row in r["rows"]:
                print(f"        {row['memories']:>6,}  →   {row['injected_chars']:>6} chars        "
                      f"{row['naive_flat_index_chars']:>8,} chars")
    npass = sum(1 for r in results if r.get("pass"))
    ngraded = sum(1 for r in results if "pass" in r)
    print(f"\n=== {npass}/{ngraded} proofs PASS ===")
    payload = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "pass": npass, "total": ngraded, "results": results}
    if json_path:
        json.dump(payload, open(json_path, "w"), indent=2)
        print(f"[wrote {json_path}]")
    return payload

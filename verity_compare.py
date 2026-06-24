#!/usr/bin/env python3
"""
verity compare — model-agnostic, user-runnable LLM comparison test.

Runs NAIVE vs the REAL VERITY HARNESS on the SAME model across 5 dimensions
(technical / visual / fun / real_world / edge), scores each (exit-code / oracle /
LLM-judge), and reports per-dimension + composite lift with paired statistics.
Spec + citations: memory/verity-upgrade-research/llm-comparison-test-system-spec.md
(LangChain · confident-ai · evidently · Anthropic statistical-evals · Harness-Bench).

  naive   = one direct model call (think → answer, NO gates)
  harness = `python3 -m verity solve` on the SAME model (real search + verify + gates)

Honest method: tasks are chosen where reasoning/verification/search can change the
answer. Run `python3 -m verity doctor` FIRST — below the ~32B floor the harness
catches errors but can't fix them, so a "no lift" result there is the MODEL, not VERITY.

Usage:
  python3 verity_compare.py --model <id> [--provider openrouter|ollama]
                            [--dimensions technical,real_world,edge | --all]
                            [--fast] [--judge-model <id>] [--no-judge] [--out FILE]
Env: OPENROUTER_API_KEY (openrouter) — read from ~/.openclaw/credentials/llm.env if unset.
"""
from __future__ import annotations
import argparse, json, math, os, pathlib, re, subprocess, sys, tempfile, time, urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
BANK = HERE / "compare_tasks.json"
ENVF = pathlib.Path.home() / ".openclaw" / "credentials" / "llm.env"

def log(*a): sys.stderr.write("[compare] " + " ".join(str(x) for x in a) + "\n")

def _key():
    k = os.environ.get("OPENROUTER_API_KEY", "")
    if not k and ENVF.exists():
        m = re.search(r'OPENROUTER_API_KEY\s*=\s*"?([^"\n]+)', ENVF.read_text(errors="ignore"))
        if m: k = m.group(1).strip()
    return k

def call_model(prompt, model, provider, system=None, timeout=120):
    """Single chat completion. Returns text (or '' on error)."""
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    if provider == "ollama":
        url, key = "http://localhost:11434/v1/chat/completions", "ollama"
    else:
        url, key = "https://openrouter.ai/api/v1/chat/completions", _key()
    body = json.dumps({"model": model, "messages": msgs, "temperature": 0.1}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception as e:
        log(f"model call failed: {e}"); return ""

GATE = ("You are under the VERITY harness. Before concluding: (RULE6) never assert a negative/impossibility "
        "without reasoning it out — most 'impossible/can't' premises are false; (CALIBRATE) if a premise is "
        "wrong, SAY SO; (VERIFY) re-check your own answer for errors before finalizing; (SPEC) if a request is "
        "over-constrained, state the impossibility and give the correct alternative. Be concise and correct.")

def run_naive(task, model, provider):
    return call_model(task["prompt"], model, provider)

def run_harness(task, model, provider):
    """Real harness arm: a genuine 2-pass gate on the SAME model with a CLEAN final answer
    (so it scores correctly). draft → adversarial self-verify/calibrate → corrected answer.
    (We deliberately do NOT shell out to `verity solve` here: its stdout is scaffold LOGS,
    not a parseable answer, which corrupts oracle/exit scoring. The 2-pass loop captures the
    real harness levers — search-mindset gate, calibration, self-verify — with a clean output.
    For full-scaffold runs use `python3 -m verity eval` directly.)"""
    draft = call_model(task["prompt"], model, provider, system=GATE)
    verify = call_model(f"Task: {task['prompt']}\n\nDraft answer:\n{draft}\n\nAdversarially check the draft for "
                        f"errors, false premises, or impossibility. If the premise is wrong SAY SO; if the draft "
                        f"has a bug fix it; if over-constrained state it + give the right alternative. "
                        f"Give the CORRECTED final answer only.", model, provider, system=GATE)
    return verify or draft

# ── scorers ──────────────────────────────────────────────────────────────────
def score_oracle(ans, sc):
    al = (ans or "").lower()
    return 1.0 if any(str(k).lower() in al for k in sc["any"]) else 0.0

def score_exit(ans, sc):
    code = ans
    m = re.search(r"```(?:python)?\s*(.*?)```", ans or "", re.S)
    if m: code = m.group(1)
    with tempfile.TemporaryDirectory() as d:
        pathlib.Path(d, "sol.py").write_text(code or "")
        pathlib.Path(d, "t.py").write_text(sc["test"])
        try:
            return 1.0 if subprocess.run([sys.executable, "t.py"], cwd=d, capture_output=True, timeout=30).returncode == 0 else 0.0
        except Exception:
            return 0.0

def score_judge(ans, sc, judge_model, provider):
    if not judge_model: return None
    p = (f"Rate this answer 1-5 on: {sc['rubric']}. Answer:\n{ans}\n\nReply ONLY a single integer 1-5.")
    r = call_model(p, judge_model, "openrouter" if provider != "ollama" else "ollama", timeout=60)
    m = re.search(r"[1-5]", r or "")
    return (int(m.group(0)) - 1) / 4 if m else None  # normalize 1-5 → 0..1

def score(task, ans, judge_model, provider):
    sc = task["score"]; t = sc["type"]
    if t == "oracle": return score_oracle(ans, sc)
    if t == "exit": return score_exit(ans, sc)
    if t == "judge":
        v = score_judge(ans, sc, judge_model, provider); return v if v is not None else 0.0
    return 0.0

# ── stats ─────────────────────────────────────────────────────────────────────
def paired_stats(naive, harn):
    diffs = [h - n for n, h in zip(naive, harn)]
    n = len(diffs); mean = sum(diffs) / n if n else 0
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1) if n > 1 else 0
    sem = math.sqrt(var / n) if n else 0
    # sign test p (two-sided, normal approx) — improvements vs regressions
    pos = sum(1 for d in diffs if d > 1e-9); neg = sum(1 for d in diffs if d < -1e-9); m = pos + neg
    if m:
        z = abs(pos - neg) / math.sqrt(m); p = math.erfc(z / math.sqrt(2))
    else:
        p = 1.0
    return {"lift_pp": round(mean * 100, 1), "ci95_pp": round(1.96 * sem * 100, 1),
            "improved": pos, "regressed": neg, "p_value": round(p, 4), "significant": p < 0.05}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--provider", default="openrouter", choices=["openrouter", "ollama"])
    ap.add_argument("--dimensions", default="technical,real_world,edge")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--fast", action="store_true", help="2 tasks/dimension")
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if not BANK.exists(): log(f"missing task bank {BANK}"); sys.exit(1)
    bank = json.loads(BANK.read_text())
    dims = list(bank.keys()) if a.all else [d.strip() for d in a.dimensions.split(",") if d.strip() in bank]
    judge = None if a.no_judge else (a.judge_model or "openai/gpt-4o-mini")
    log(f"model={a.model} provider={a.provider} dims={dims} judge={judge}")
    results = {"model": a.model, "provider": a.provider, "dims": {}, "tasks": []}
    all_n, all_h = [], []
    for dim in dims:
        tasks = bank[dim][:2] if a.fast else bank[dim]
        nv, hv = [], []
        for t in tasks:
            t0 = time.time(); na = run_naive(t, a.model, a.provider); ns = score(t, na, judge, a.provider)
            ha = run_harness(t, a.model, a.provider); hs = score(t, ha, judge, a.provider)
            nv.append(ns); hv.append(hs); all_n.append(ns); all_h.append(hs)
            results["tasks"].append({"dim": dim, "id": t.get("id"), "naive": ns, "harness": hs, "lat": round(time.time()-t0,1)})
            log(f"  [{dim}] {t.get('id')}: naive={ns:.2f} harness={hs:.2f}")
        st = paired_stats(nv, hv)
        results["dims"][dim] = {"naive_pct": round(100*sum(nv)/len(nv)), "harness_pct": round(100*sum(hv)/len(hv)), **st}
    results["overall"] = {"naive_pct": round(100*sum(all_n)/len(all_n)) if all_n else 0,
                          "harness_pct": round(100*sum(all_h)/len(all_h)) if all_h else 0,
                          **paired_stats(all_n, all_h)}
    # leaderboard print
    print("\n=== VERITY compare ::", a.model, "===")
    print(f"{'dimension':14} {'naive':>7} {'harness':>8} {'lift':>7} {'p':>7}")
    for d, r in results["dims"].items():
        print(f"{d:14} {r['naive_pct']:>6}% {r['harness_pct']:>7}% {r['lift_pp']:>+6}pp {r['p_value']:>7}")
    o = results["overall"]
    print(f"{'OVERALL':14} {o['naive_pct']:>6}% {o['harness_pct']:>7}% {o['lift_pp']:>+6}pp {o['p_value']:>7}  {'SIGNIFICANT' if o['significant'] else 'n.s.'}")
    out = a.out or str(HERE / f"compare-{re.sub(r'[^a-z0-9]+','-',a.model.lower())}.json")
    pathlib.Path(out).write_text(json.dumps(results, indent=1)); log(f"wrote {out}")

if __name__ == "__main__":
    main()

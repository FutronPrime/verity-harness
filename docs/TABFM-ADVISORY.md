# TabFM advisory route scoring (OPTIONAL dependency)

> **STATUS 2026-07-19: SHELVED — proven prototype.** Benchmarked PROMISING (3/3 zero-shot wins
> vs untuned HistGB) but impractical on current hardware (~12GB weights, ~3s/row CPU). Weights
> and venv reclaimed; receipts keep accumulating at zero cost. Re-integrate when disk/hardware
> allow or via TabPFN-v2/TabICL (commercial-friendly, far smaller) — install recipe below is
> the full rebuild (~15 min).

Zero-shot in-context learning over the proxy's own dispatch history — no trained model, no
tuning. Labeled receipt rows are the context; new dispatches are the question.

## Pieces
1. **Receipts** (built-in, no dependency): `verity/server.py` appends one JSONL row per
   completion to `~/.verity-harness/receipts.jsonl` — ts, ok, model, tier, guarded, n_msgs,
   prompt_chars, reply_chars, latency_ms. Disable with `VERITY_RECEIPTS=off`.
2. **Scorer** (optional): Google TabFM v1.0.0 via `futron-tabfm-probe` — install per
   `requirements-tabfm.txt`. Evals receipts on a chronological 70/30 split vs a majority
   baseline; report → `~/.openclaw/logs/tabfm-probe-report.md`.

## Ground rules (measured on Apple Silicon CPU, 2026-07-19)
- **Batch advisory ONLY.** ~3s/row CPU; 100-row eval = 2–10 min. Never score per-request inline.
- Local benchmark: beat untuned HistGradientBoosting **3/3** (breast_cancer +0.030, wine +0.014,
  digits +0.110; mean +0.051) — zero-shot. Independent eval (devYRPauli/tabfm-evaluation)
  showed it beating *tuned* XGBoost on small/mid tables.
- Limits: ≤500 features, ≤10 classes, ~10K-row ceiling; probe caps context at newest 2000 rows.
- **License**: weights are NON-COMMERCIAL v1.0 (and the README doesn't say so — HF card does).
  Internal advisory use only. Commercial path: TabPFN-v2 (Apache-2.0) / TabICL-v2 (BSD-3),
  e.g. via DataZooDE/anofox-tabfm (DuckDB+ONNX, CoreML backend).
- Regression head = separate ~6GB download (`--with-reg` on the benchmark); classification-only
  by default.

## Promotion gate
Advisory stays advisory until BOTH: (1) probe beats majority baseline on ≥40 real receipts,
(2) its route picks beat the live cascade heuristic over a real window. Then (and only then)
wire its output as pre-dispatch hints — never as the authority.

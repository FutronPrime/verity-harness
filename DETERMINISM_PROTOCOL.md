# DETERMINISM PROTOCOL — you cannot buy it with a temperature setting

Adopt alongside `OVS_PROTOCOL.md` (grading) and `PROACTIVITY_PROTOCOL.md` (when to speak
unbidden). This one governs how a run becomes **dependable** — repeatable enough to build on.

## The claim that has to go first

**`temperature=0` is not deterministic, and believing it is has been the root of more flaky
agent behaviour than any prompt bug.**

> Sampling 1,000 completions from Qwen3-235B at temperature 0 produced **80 distinct outputs**,
> first diverging at token 103. Greedy decoding is deterministic *given identical logits* — the
> logits are not identical. Thinking Machines traced it to missing **batch invariance** in
> RMSNorm, matrix multiplication and attention: the serving stack groups requests into
> different batches over time, the reduction order changes, the numerics change, and greedy
> decoding forks. Batch-invariant kernels restore bit-identical output across 1,000 runs at
> roughly **61.5% throughput cost**.
> <https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/>

The operational consequence is the whole protocol: **that fix requires owning the inference
server.** Against a hosted API you do not control batching, so bit-level reproducibility is not
purchasable at any price. Determinism must therefore come from **architecture**, and every
claim of "we set temperature to 0" should be read as *"we did nothing."*

## Tier 1 — TRUE determinism (mathematical guarantee)

Available only where the named layer sits between the model and the output.

| technique | mechanism | tool | guarantee |
|---|---|---|---|
| Constrained decoding | mask invalid tokens to −∞ at each step | Outlines | schema-valid output, always |
| Grammar-bounded generation | validate tokens against a grammar in real time | LMQL, GBNF | structural validity |
| Structure/content separation | framework emits the JSON skeleton; model fills only leaves | Jsonformer | 100% syntactic JSON |
| Fixed seed + deterministic kernels | `torch.manual_seed`, `use_deterministic_algorithms(True)`, CUDA controls | local models only | run-to-run identity at fixed batch |
| Batch-invariant inference | batch-invariant RMSNorm / matmul / attention | self-hosted only | identical across batch sizes |
| Formal verification | discharge the claim to a solver | Z3, Lean 4 | proof, not sampling |

FUTRON note: local lanes go through the HTTP API with **GBNF grammars** — never by parsing
`ollama run` stdout, which is a display surface with ANSI codes and wrap-redraw, not a data
channel. That lesson has its own file.

## Tier 2 — consistency heuristics (statistical, no guarantee)

These are what remain against a hosted API. **Label them as heuristics wherever they are
reported.** Presenting a voted result as a determined one is the same category error as
printing a heuristic score as a judgment.

- **Validate-and-reask** — Guardrails: validators plus an `on_fail` policy of
  `exception | reask | fix | filter | refrain`, bounded by `num_reasks`. No guarantee content
  ever passes.
- **Runtime judges** — Steer: `JsonJudge` (structure), `SlopJudge` (Shannon entropy, catches
  the smooth AI register), safety and ambiguity guards, <5ms, local-first. Catch → teach → fix.
- **Voting / consensus** — MAKER: generate candidates, first-to-ahead-by-*k*. Empirically drove
  a **million-step task to zero errors** by decomposing into atomic steps and voting each one.
  Redundancy management, not model quality, is what bought the reliability.
- **Decomposition** — ROMA: DAG of atomic subtasks so an error is isolated rather than
  propagated. Isolation, not prevention.
- **Symbolic narrowing** — Matryoshka: confine the model to a rigid S-expression DSL, type-check
  commands *before* execution, keep large results behind handles so the model never sees or
  hallucinates about data it has not read (97%+ token savings). Trade expressive freedom for
  predictability.
- **Compile against a metric** — DSPy: stop hand-tuning prompts; define a metric and let the
  optimizer fit prompts and demonstrations. Moves variance from the prompt to a measured
  artifact.

## The procedure

1. **BLUEPRINT FIRST, MODEL SECOND.** Define the workflow — decomposition, control flow,
   execution guarantees — *before* choosing which model fills each slot. Determinism emerges
   from architectural constraint; picking a stronger model does not add any.
   (arXiv 2508.02721.)

2. **PUT THE HARDEST CONSTRAINT AT THE LOWEST AVAILABLE TIER.** Grammar beats validator beats
   judge beats retry beats hope. Reach for Tier 2 only for what Tier 1 cannot express.

3. **NEVER LET A FALLBACK RENDER IN THE SHAPE OF A RESULT.** The degraded path must be
   structurally distinguishable — different exit code, absent score, different output type. A
   warning line above an otherwise-normal verdict is skimmed past. See the sets-review evidence
   in `PROACTIVITY_PROTOCOL.md`.

4. **SEPARATE DETERMINISTIC FROM JUDGED IN EVERY REPORTED NUMBER.** One aggregate spanning both
   hides outages inside an average. Report the counts and the judgments in different columns,
   always.

5. **A PROXY IS NOT THE THING.** Log the measurement and the claim separately, and never let
   the first stand in for the second.

   > **Measured 2026-07-26.** A resolver scanned post replies for the linked repo, accepting any
   > host matching `.ai/ .io/ .dev/ .sh/`. That is the shape of most advertisement
   > destinations, and every link on the page is in the DOM — promoted slots included. It
   > attached the same two unrelated products to three different posts and kept three URLs that
   > still carried their `twclid` click IDs. **14 of 22 reply-derived links were wrong (~64%)**
   > and rendered in the same chip as the correct ones. The metric "artifacts found: 5" looked
   > exactly like progress. *"The scraper returned a link"* is a proxy for *"I found the repo."*

6. **PERSIST WHAT WAS LEARNED, NOT WHAT HAPPENED.** ACE's Skillbook: store validated strategies
   rather than raw traces (≈49% token reduction). A growing transcript is not memory; a curated,
   pruned strategy set is.

7. **VERIFY BY OPENING THE ARTIFACT.** The count of rows written is not the page rendering. A
   structural check on the output object is worth more than any assertion about the process
   that produced it.

## Sources

- Thinking Machines Lab, *Defeating Nondeterminism in LLM Inference* — batch invariance.
- *Blueprint First, Model Second* (arXiv 2508.02721) — determinism from architecture.
- *Solving a Million-Step LLM Task with Zero Errors* (arXiv 2511.09030) — MAKER; decomposition
  plus first-to-ahead-by-*k* voting.
- Guardrails <https://github.com/guardrails-ai/guardrails> · DSPy
  <https://github.com/stanfordnlp/dspy> · Steer <https://github.com/imtt-dev/steer> ·
  Matryoshka <https://github.com/yogthos/Matryoshka> · Outlines, LMQL, Jsonformer.

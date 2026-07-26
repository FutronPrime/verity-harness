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
| Batch-invariant inference | batch-invariant RMSNorm / matmul / attention | **vLLM** ([`batch_invariance`](https://docs.vllm.ai/en/latest/features/batch_invariance)) · **SGLang** ([deterministic inference](https://docs.sglang.io/advanced_features/deterministic_inference.html)) — self-hosted only | identical across batch sizes |
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

8. **NEVER READ HISTORY AS STATE.** The most common form of rule 5 in practice, and the one
   that keeps getting rebuilt. Before treating a value as *current*, ask what it is a record
   **of**:

   | proxy | what it actually is | correct reading |
   |---|---|---|
   | `launchctl` STATUS column | **last exit** | require `pid != "-"`; a running service is healthy whatever its last exit was |
   | a cached snapshot file | the world at write time | re-observe by default; make `--cached` explicit *and* print its age |
   | "last N lines of a log" | position, not time | gate on `st_mtime` — a crash loop is by definition still writing |
   | rows written | the process | open the artifact |

   > **Measured 2026-07-26.** Four instances in one session, **three of them inside the module
   > written to catch exactly this class.** It reported a healthy daemon as failing (last-exit
   > column), then kept reporting the fault 30 seconds after it was fixed (cached snapshot),
   > then flagged a crash loop from a log that had stopped being written 14 hours earlier
   > (line position). Writing the protocol did not prevent the protocol's own implementation
   > from committing the error three times — which is the argument for the deterministic test,
   > not the doctrine.

9. **A FALSE ALARM IS A BUG REPORT AGAINST THE DETECTOR, NOT NOISE TO TUNE OUT.** Raising a
   threshold to silence an FA hides the reading error that caused it and lowers real coverage
   at the same time. Fix the column.


10. **A LINTER THAT MISSES ITS OWN FIXTURE CERTIFIES THE CODE IT CANNOT READ.** Every
    check here ships with three fixtures: a known-bad that must be caught, a
    reference-correct file that must be clean, and *the linter itself*, which must not
    flag its own documentation. Talking about a pattern is not committing it.

    > **Measured 2026-07-26.** `futron-rule11-lint` cleared the real, historical
    > `futron-sets-review` — the file whose failure the rule was written from — because
    > its "honest degrade branch" pattern accepted `if used_fallback: print("⚠ …")`.
    > That is a warning line above an otherwise-identical verdict: **the linter accepted
    > the exact thing R11 forbids.** Fixed by requiring the branch to actually suppress
    > or replace the verdict (early return / exit 2 / UNAVAILABLE), not merely print.
    > Regression fixture is now the pre-fix backup itself: catch the historical bug,
    > clear the fixed version.

11. **DO NOT TUNE A LINTER TO ZERO.** Tuning to silence is the same error as reading a
    silent detector as healthy. The honest end state is *precise on the patterns it
    claims, explicit about its limits* — so these tools print "these checks found
    nothing **they can see**", never "all clear". First R11 sweep: 198 findings, ~90% of
    them the token `timeout=` in a kwarg. A linter that is 90% noise is one nobody runs,
    so each false alarm was fixed as a detector defect until the signal was real —
    198 → 26 → 14, with the fixtures re-run at every step.

## Sources

- Thinking Machines Lab, *Defeating Nondeterminism in LLM Inference* — batch invariance.
- *Blueprint First, Model Second* (arXiv 2508.02721) — determinism from architecture.
- *Solving a Million-Step LLM Task with Zero Errors* (arXiv 2511.09030) — MAKER; decomposition
  plus first-to-ahead-by-*k* voting.
- Guardrails <https://github.com/guardrails-ai/guardrails> · DSPy
  <https://github.com/stanfordnlp/dspy> · Steer <https://github.com/imtt-dev/steer> ·
  Matryoshka <https://github.com/yogthos/Matryoshka> · Outlines, LMQL, Jsonformer.

# Council-mode evaluation — researched, ported, and why it upgrades VERITY

A worked example of the [persistence gate's](PERSISTENCE-GATE.md) own doctrine —
**research a real resource, read its source, port the technique, prove it** — applied
to harden VERITY's high-stakes evaluation gate.

## The research trail (provenance)

1. **Source:** the X-bookmark assimilation matrix flagged `karpathy/llm-council`
   (target: `VERITY/HARNESS`) with the action *"extract the multi-LLM review +
   chairman synthesis pattern; integrate into VERITY as a council-mode eval."*
2. **Read it:** fetched `github.com/karpathy/llm-council` README. The mechanism is
   three stages, and the README is explicit about *why* the middle stage matters:
   > "the LLM identities are anonymized so that the LLM can't play favorites when
   > judging their outputs."
3. **Diagnosed the gap in VERITY:** VERITY's existing v2.2 PANEL+JUDGE gate asked N
   backends and had a judge fuse them — but the judges were **not blind**. A model
   judging a pool that includes its own answer self-prefers, so "fusion" quietly
   inherits the strongest model's bias instead of correcting it. That is the exact
   failure karpathy's anonymization step removes.
4. **Ported it** onto VERITY's sovereign tiers (not a new dependency): `verity/council.py`.

## The three stages (as implemented)

| Stage | llm-council | VERITY `council.py` |
|---|---|---|
| 1. Initial responses | each member answers | each distinct-model **tier** answers (`router.chat([..], tiers=[tier])`) |
| 2. **Anonymized cross-eval** | members rank others, identities hidden | each member ranks the **others only**, responses relabeled `A/B/C` and rotated; **no name/model leaks into the prompt** (regression-tested) |
| 3. Chairman synthesis | chairman fuses answers + rankings | top tier synthesizes from the **Borda-aggregated** consensus order |

Aggregation is a **Borda count** over every blind ranking → a robust consensus that
no single model dictates. Rank variance becomes a **disagreement score**: high spread
⇒ the council is split ⇒ the v2.2 rule "disagreement = uncertainty → escalate, don't
ship" now has a number behind it instead of a vibe.

## Why this is a real upgrade (not a reskin)

- **Removes self-preference bias** — the measurable defect in the old gate. Stage-2
  prompts are verified identity-free (`tests/test_council.py::test_ranking_is_blind`).
- **Sovereign** — members are VERITY tiers, so council-mode rides the same cloud→local
  failover. It degrades to whatever tiers are up; with one tier it returns that answer
  (no crash).
- **Cheaper-to-trust than a frontier single-shot** — karpathy's own finding (and
  VERITY's v2.2 note) is that a fused panel of mid models can beat one top model on
  hard questions at lower true-$; council-mode operationalizes that for high-stakes
  steps without a frontier dependency.

## Usage

```bash
python3 -m verity council "Should FUTRON route model X for trading-signal synthesis?"
python3 -m verity council --members 4 "<hard architecture question>"
```

Output: each member's answer, the blind-peer **consensus** (best→worst), the
**disagreement** score (≥0.5 ⇒ ESCALATE), and the **chairman's synthesized** final.

## Tests

`python3 tests/test_council.py` — 4/4: three-stage flow + consensus, **blind-ranking
(no identity leak)**, disagreement computed on a split, single-member graceful
degrade. Sits alongside the panel of deterministic gates (`test_stop_guard.py` 38/38,
`test_persist.py` 5/5).

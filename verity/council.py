#!/usr/bin/env python3
"""Council-mode evaluation (R-v2.2 PANEL+JUDGE, upgraded) — researched from
karpathy/llm-council, ported onto VERITY's sovereign tiers.

WHY this exists / what it upgrades
----------------------------------
VERITY already had a PANEL+JUDGE gate for high-stakes steps: ask N backends, a
judge fuses, disagreement ⇒ escalate. The gap: the judges were NOT blind — a
model judging a pool that includes its own answer self-prefers, so the "fusion"
inherits the strongest model's bias instead of correcting it.

karpathy/llm-council (researched 2026-06-28, README) formalizes the fix in three
stages, the middle one being the key:

  Stage 1 — Initial responses : every council member answers independently.
  Stage 2 — ANONYMIZED cross-evaluation : each member ranks the OTHERS' answers
            with identities hidden ("Response A/B/C", shuffled) so it "can't play
            favorites when judging their outputs."  ← the bias fix
  Stage 3 — Chairman synthesis : a chairman model fuses all answers + the
            aggregated ranking into one final answer.

This module implements exactly that, but the members are VERITY's own tiers
(sovereign routing: cloud subs → local floor), so council-mode runs on the same
failover-safe backbone as everything else and degrades to whatever tiers are up.

Result: a stronger high-stakes gate. Blind peer-ranking removes self-preference;
Borda aggregation turns N noisy rankings into a robust consensus; the chairman
synthesizes rather than picking one winner. Disagreement (high rank variance) is
surfaced as uncertainty — the v2.2 "disagreement = escalate" rule, now measured.

  python3 -m verity council "<question>"          # full 3-stage council
  python3 -m verity council --members 4 "<q>"      # widen the panel
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

LABELS = "ABCDEFGH"


@dataclass
class CouncilResult:
    question: str
    final: str
    responses: dict = field(default_factory=dict)      # member-name → answer
    consensus: list = field(default_factory=list)      # member-names, best→worst
    scores: dict = field(default_factory=dict)         # member-name → Borda points
    disagreement: float = 0.0                          # 0=unanimous, 1=max spread
    chairman: str = ""

    def report(self) -> str:
        out = [f"COUNCIL — {len(self.responses)} members | chairman: {self.chairman}",
               f"consensus (best→worst): {' > '.join(self.consensus)}",
               f"scores: {self.scores}",
               f"disagreement: {self.disagreement:.2f} "
               f"({'ESCALATE — members disagree' if self.disagreement >= 0.5 else 'aligned'})",
               "", "── final (chairman synthesis) ──", self.final]
        return "\n".join(out)


def _default_members(n: int):
    """Distinct-model subset of VERITY's tiers (dedupe by model, keep order)."""
    from .config import TIERS
    seen, members = set(), []
    for t in TIERS:
        if t.model not in seen:
            seen.add(t.model)
            members.append(t)
        if len(members) >= n:
            break
    return members


def _default_ask(member, prompt: str) -> str:
    from .router import chat
    return chat([{"role": "user", "content": prompt}], tiers=[member]).text.strip()


def _parse_ranking(text: str, labels: list) -> list:
    """Pull an ordered label list from 'RANKING: B > A > C' (tolerant)."""
    m = re.search(r"RANKING\s*[:=]\s*([A-H](?:\s*[>,\s]\s*[A-H])*)", text, re.I)
    seq = m.group(1) if m else text
    order, seen = [], set()
    for ch in re.findall(r"[A-H]", seq.upper()):
        if ch in labels and ch not in seen:
            seen.add(ch)
            order.append(ch)
    for lb in labels:                      # append any the model omitted, stable
        if lb not in seen:
            order.append(lb)
    return order


def council(question: str, *, members=None, chairman=None,
            criteria: str = "factual accuracy, completeness, and insight",
            ask_fn=None, n: int = 3) -> CouncilResult:
    """Run the 3-stage council. `ask_fn(member, prompt)->str` is injectable for
    tests; default routes through VERITY tiers."""
    members = members if members is not None else _default_members(n)
    ask = ask_fn or _default_ask
    chairman = chairman if chairman is not None else (members[0] if members else None)
    names = [getattr(m, "name", str(i)) for i, m in enumerate(members)]

    # ── Stage 1: independent responses ──────────────────────────────────────
    responses = {}
    for m, name in zip(members, names):
        try:
            responses[name] = ask(m, question)
        except Exception as e:
            responses[name] = f"(no answer: {e})"

    if len(responses) < 2:                 # nothing to deliberate
        only = next(iter(responses.values()), "")
        return CouncilResult(question, only, responses, list(responses), {}, 0.0,
                             getattr(chairman, "name", ""))

    # ── Stage 2: ANONYMIZED blind cross-ranking ─────────────────────────────
    # Each member ranks the OTHERS only; identities replaced by shuffled labels
    # so no model can recognize (or favor) its own answer.
    borda = {nm: 0 for nm in names}
    rank_positions = {nm: [] for nm in names}
    for ranker, ranker_name in zip(members, names):
        others = [(nm, responses[nm]) for nm in names if nm != ranker_name]
        # deterministic per-ranker shuffle (no Math.random in this env): rotate
        rot = names.index(ranker_name) % max(1, len(others))
        others = others[rot:] + others[:rot]
        labels = list(LABELS[:len(others)])
        label_to_name = {lb: nm for lb, (nm, _) in zip(labels, others)}
        block = "\n\n".join(
            f"Response {lb}:\n{txt}" for lb, (_, txt) in zip(labels, others))
        prompt = (
            f"You are a council member ranking peer answers to a question. The "
            f"author identities are hidden. Rank them by {criteria}.\n\n"
            f"QUESTION:\n{question}\n\n{block}\n\n"
            f"Reply with ONE line, best to worst, e.g.  RANKING: "
            f"{' > '.join(labels)}")
        try:
            order = _parse_ranking(ask(ranker, prompt), labels)
        except Exception:
            order = labels
        k = len(order)
        for pos, lb in enumerate(order):
            nm = label_to_name.get(lb)
            if nm is not None:
                borda[nm] += (k - 1 - pos)         # 1st place = k-1 points
                rank_positions[nm].append(pos)

    consensus = sorted(names, key=lambda nm: (-borda[nm], nm))

    # disagreement = mean normalized spread of each answer's received positions
    spreads = []
    for nm in names:
        ps = rank_positions[nm]
        if len(ps) >= 2:
            spreads.append((max(ps) - min(ps)) / max(1, len(names) - 1))
    disagreement = round(sum(spreads) / len(spreads), 4) if spreads else 0.0

    # ── Stage 3: chairman synthesis ─────────────────────────────────────────
    ranked_block = "\n\n".join(
        f"[peer-rank #{i+1}] {responses[nm]}" for i, nm in enumerate(consensus))
    chair_prompt = (
        "You are the council chairman. Synthesize ONE best final answer to the "
        "question from the member answers below (already ordered by blind peer "
        "ranking, best first). Prefer higher-ranked content, correct errors, and "
        "merge complementary points. Do not mention the ranking or the process.\n\n"
        f"QUESTION:\n{question}\n\n{ranked_block}\n\nFINAL ANSWER:")
    try:
        final = ask(chairman, chair_prompt).strip()
    except Exception as e:
        final = responses[consensus[0]] + f"\n\n(chairman unavailable: {e})"

    return CouncilResult(question, final, responses, consensus, borda,
                         disagreement, getattr(chairman, "name", ""))


# ── CLI ──────────────────────────────────────────────────────────────────────
def _cli(argv: list) -> int:
    n = 3
    args = []
    i = 0
    while i < len(argv):
        if argv[i] in ("--members", "-n") and i + 1 < len(argv):
            n = int(argv[i + 1]); i += 2; continue
        args.append(argv[i]); i += 1
    if not args:
        print('usage: verity council [--members N] "<question>"', file=sys.stderr)
        return 2
    res = council(" ".join(args), n=n)
    print(res.report())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

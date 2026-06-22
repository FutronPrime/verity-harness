#!/usr/bin/env python3
"""Subject ACQUISITION loop — on-the-job training for the harness (the 'go learn a topic' engine).

The Architect's thesis (2026-06-22): the loop IS on-the-job training. A human hitting a new domain
doesn't get retrained — they go FIND the textbook / library / repo / tutorial, absorb it, and now they
know it. This makes each user's harness its OWN customized evolved expert: it learns the subjects THAT
user works on, from the open-source artifacts the community already built, and keeps them.

This is the general-subject sibling of `assimilate.py` (which does the same SCOUT→FILTER→ASSIMILATE→
SYNTHESIZE loop for VIDEO/YouTube). It REUSES the harness's own primitives rather than rebuilding:
  • SCOUT     — tools.research() (multi-platform sweep) + tools.search_github() + resources.reuse_hint()
  • FILTER    — the model picks the highest-signal, most-learnable sources (deterministic URL fallback)
  • ASSIMILATE— resources.fetch_list()/tools.fetch() pulls each source; the model distills the reusable
                technique/skill/tool it teaches for THIS subject
  • SYNTHESIZE— combine into ONE durable, bounded knowledge note, tagged with its sources
  • PERSIST   — membank.capture(scope="lesson", project=<subject>)

The CONSUME side is already wired, which is why this closes a real loop with almost no new surface:
  • swarm `_context_pack` recalls project-scoped membank into EVERY spawned agent → learned knowledge
    shows up automatically in future tasks on that subject (the "customized assistant" payoff).
  • evolve `membank.promote_block()` already pulls "lesson" memories into the evolved playbook → what
    you learn can flow into the injected discipline/strategy layer too.

Agentic loop (DJ's point): a completeness critic asks "what's still missing on this subject?" and drives
another scout round on the gap — iterate until it has enough or the round budget is spent. Pure stdlib;
honest failure (research() returns a real failure signal, so a dead subject degrades, never hallucinates).

  python3 -m verity learn "rust async runtimes"            # one acquisition round → persisted
  python3 -m verity learn "kalman filters" --rounds 3      # iterate: scout the gaps each round
  python3 -m verity learn "<subject>" --show               # recall what's already been learned
"""
from __future__ import annotations

import re

_URL = re.compile(r"https?://[^\s)\]>\"']+")
_GH = re.compile(r"github\.com/[\w.\-]+/[\w.\-]+")


def _scout(subject: str, tiers=None) -> str:
    """Live multi-source sweep for learnable artifacts on the subject (repos, skills, docs, tutorials)."""
    parts = []
    try:
        from .tools import research
        parts.append(research(f"{subject} — best open-source repo, skill, library, or tutorial to learn it"))
    except Exception:  # noqa: BLE001
        pass
    try:
        from .tools import search_github
        parts.append(search_github(subject, n=6))
    except Exception:  # noqa: BLE001
        pass
    try:
        from .resources import reuse_hint
        h = reuse_hint(f"learn build {subject}")
        if h:
            parts.append(h)
    except Exception:  # noqa: BLE001
        pass
    return "\n\n".join(p for p in parts if p and p.strip())


def _select_sources(subject: str, scout_text: str, k: int = 3, tiers=None) -> list[str]:
    """FILTER: pick the top-k highest-signal sources. Model-ranked, with a deterministic URL/GitHub
    fallback so an LLM outage never blocks acquisition."""
    fallback = []
    seen = set()
    for m in _GH.findall(scout_text) + _URL.findall(scout_text):
        u = m.rstrip(".,);")
        key = u.lower()
        if key not in seen:
            seen.add(key); fallback.append(u if u.startswith("http") else "https://" + u)
        if len(fallback) >= k * 2:
            break
    try:
        from .router import ask
        from .loop import parse_step_json
        sysp = ("Pick the SINGLE best sources to LEARN a subject from the search results — prefer "
                "maintained repos, official docs, and high-signal tutorials over blogspam. "
                'Respond ONLY JSON: {"sources":["<url1>","<url2>"]} (max ' + str(k) + ").")
        r = ask(f"SUBJECT: {subject}\n\nSEARCH RESULTS:\n{scout_text[:5000]}",
                system=sysp, **({"tiers": tiers} if tiers else {}))
        picked = parse_step_json(r.text if hasattr(r, "text") else str(r)).get("sources") or []
        picked = [str(u).strip() for u in picked if str(u).strip().startswith("http")][:k]
        if picked:
            return picked
    except Exception:  # noqa: BLE001
        pass
    return fallback[:k]


def _assimilate_source(subject: str, source: str, tiers=None) -> dict:
    """ASSIMILATE one source: pull it, distill the REUSABLE technique/skill it teaches for the subject."""
    body = ""
    try:
        if "github.com" in source:
            from .resources import fetch_list
            body = fetch_list(source, max_chars=7000)
        else:
            from .tools import fetch
            body = fetch(source, max_chars=7000)
    except Exception:  # noqa: BLE001
        body = ""
    if not body or len(body) < 120:
        return {"source": source, "lesson": "", "ok": False}
    try:
        from .router import ask
        sysp = ("You are LEARNING a subject from a source so the harness can apply it later. Extract the "
                "concrete, REUSABLE knowledge: key techniques, the right tool/library + how to invoke it, "
                "gotchas, and a minimal usage pattern. Be specific and actionable; cite the source. "
                "No fluff — this becomes a permanent cheat-sheet. <900 chars.")
        r = ask(f"SUBJECT: {subject}\nSOURCE: {source}\n\nCONTENT:\n{body[:6000]}",
                system=sysp, **({"tiers": tiers} if tiers else {}))
        lesson = (r.text if hasattr(r, "text") else str(r)).strip()
        return {"source": source, "lesson": lesson[:1200], "ok": bool(lesson)}
    except Exception:  # noqa: BLE001
        return {"source": source, "lesson": "", "ok": False}


def _synthesize(subject: str, lessons: list[dict], tiers=None) -> str:
    """SYNTHESIZE the per-source lessons into ONE durable, bounded knowledge note."""
    good = [l for l in lessons if l.get("ok") and l.get("lesson")]
    if not good:
        return ""
    combined = "\n\n".join(f"[{l['source']}]\n{l['lesson']}" for l in good)
    try:
        from .router import ask
        sysp = ("Synthesize these source notes into ONE coherent KNOWLEDGE NOTE on the subject the harness "
                "can recall before future tasks: the essential techniques, the go-to tool(s) + invocation, "
                "key gotchas. Keep every source's best reusable bit; drop redundancy. List sources at the "
                "end. <1500 chars. This is permanent on-the-job training, not a summary.")
        r = ask(f"SUBJECT: {subject}\n\nSOURCE NOTES:\n{combined[:6000]}",
                system=sysp, **({"tiers": tiers} if tiers else {}))
        return (r.text if hasattr(r, "text") else str(r)).strip()[:1800]
    except Exception:  # noqa: BLE001
        return combined[:1800]


def _gap(subject: str, note: str, tiers=None) -> str:
    """Completeness critic: what's STILL missing on this subject? Returns a focused next-scout query, or ''."""
    try:
        from .router import ask
        r = ask(f"SUBJECT: {subject}\n\nWHAT WE'VE LEARNED:\n{note[:1500]}\n\n"
                "What important sub-topic or practical gap is still MISSING? If the coverage is solid, "
                "reply exactly 'COMPLETE'. Otherwise reply with ONE short search query for the gap.",
                system="You audit knowledge coverage. Be strict but concise.",
                **({"tiers": tiers} if tiers else {}))
        out = (r.text if hasattr(r, "text") else str(r)).strip()
        return "" if "COMPLETE" in out.upper()[:40] else out.splitlines()[0][:120]
    except Exception:  # noqa: BLE001
        return ""


def show(subject: str) -> str:
    """Recall what the harness has already learned on a subject (the per-user customized knowledge)."""
    try:
        from . import membank
        rec = membank.recall(subject, project=subject, budget_chars=2000)
        if rec and not rec.startswith("[membank"):
            return rec
    except Exception:  # noqa: BLE001
        pass
    return f"[nothing learned yet on '{subject}' — run: python3 -m verity learn \"{subject}\"]"


def learn(subject: str, rounds: int = 1, tiers=None, verbose: bool = True) -> dict:
    """Run the acquisition loop on a subject and PERSIST the result to per-user memory. Returns a summary.
    Each round scouts (the gap, on later rounds) → filters → assimilates → synthesizes → persists."""
    subject = subject.strip()
    notes: list[str] = []
    all_sources: list[str] = []
    query = subject
    for rnd in range(max(1, rounds)):
        if verbose:
            print(f"[learn] round {rnd+1}/{rounds} — scouting: {query[:70]}")
        scout = _scout(query, tiers)
        if not scout or "NO real evidence" in scout or len(scout) < 80:
            if verbose:
                print("[learn] scout returned nothing usable — stopping (honest: no sources found).")
            break
        sources = _select_sources(query, scout, k=3, tiers=tiers)
        if verbose:
            print(f"[learn] selected {len(sources)} source(s): " + ", ".join(s[:48] for s in sources))
        lessons = [_assimilate_source(subject, s, tiers) for s in sources]
        note = _synthesize(query, lessons, tiers)
        if note:
            notes.append(note)
            all_sources += [l["source"] for l in lessons if l.get("ok")]
            if verbose:
                print(f"[learn] synthesized note ({len(note)} chars) from {sum(1 for l in lessons if l.get('ok'))} source(s)")
        # agentic loop: find the gap for the next round (skip the critic on the final round)
        if rnd < rounds - 1:
            query = _gap(subject, "\n\n".join(notes), tiers) or ""
            if not query:
                if verbose:
                    print("[learn] completeness critic: coverage COMPLETE — stopping early.")
                break

    if not notes:
        return {"subject": subject, "learned": False, "sources": [], "note": "",
                "msg": "no learnable sources found (honest failure — not a hallucinated answer)"}

    final_note = ("\n\n---\n\n".join(notes))[:3000]
    knowledge = (f"LEARNED SUBJECT · {subject}\n{final_note}\n\nSources: "
                 + "; ".join(dict.fromkeys(all_sources))[:400])
    persisted = False
    try:
        from . import membank
        # scope='lesson' so it (a) recalls into future swarm spawns and (b) feeds evolve's playbook promotion
        membank.capture(knowledge, scope="lesson", project=subject)
        persisted = True
    except Exception:  # noqa: BLE001
        pass
    if verbose:
        print(f"[learn] {'PERSISTED to memory' if persisted else 'NOT persisted (membank error)'} "
              f"— recall with: python3 -m verity learn \"{subject}\" --show")
    return {"subject": subject, "learned": True, "rounds": len(notes),
            "sources": list(dict.fromkeys(all_sources)), "persisted": persisted, "note": final_note}


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if not args:
        print('usage: python3 -m verity learn "<subject>" [--rounds N] [--show]'); sys.exit(2)
    if "--show" in args:
        subj = " ".join(a for a in args if a != "--show")
        print(show(subj)); sys.exit(0)
    rounds = 1
    if "--rounds" in args:
        i = args.index("--rounds")
        try:
            rounds = int(args[i + 1]); del args[i:i + 2]
        except (IndexError, ValueError):
            del args[i:i + 1]
    subj = " ".join(a for a in args if not a.startswith("--"))
    r = learn(subj, rounds=rounds)
    print("\n" + ("✓ learned: " + subj if r["learned"] else "✗ " + r.get("msg", "nothing learned")))

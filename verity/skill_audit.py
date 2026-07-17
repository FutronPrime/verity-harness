#!/usr/bin/env python3
"""verity skills — measure which agent skills are DEAD WEIGHT vs real LIFT.

Every skill's name+description is always-on context tax (the catalog the model reads each session).
A never-invoked, duplicated, or bloated skill is pure token cost with no lift. This audits a skills
directory three ways, cheap → rigorous:

  1. STATIC (free)          — token cost per skill + near-duplicate clusters (Jaccard on descriptions).
  2. USAGE (--with-usage)   — scan a transcripts dir for real invocations; 0-use + high-cost = CUT.
  3. A/B LIFT (--ab N "t")  — run a task WITH the skill's guidance vs WITHOUT; report output divergence.

Portable via env:
  VERITY_SKILLS_DIR       skills root      (default ~/.claude/skills)
  VERITY_TRANSCRIPTS_DIR  transcript store (default ~/.claude/projects) — for --with-usage

  verity skills                # static scorecard
  verity skills --with-usage   # + real invocation counts → CUT list + reclaim estimate
  verity skills --json out.json
  verity skills --ab <skill> "<representative task>"
"""
from __future__ import annotations
import glob, json, os, re, subprocess, sys, pathlib
from difflib import SequenceMatcher
from collections import defaultdict

SKILLS = pathlib.Path(os.environ.get("VERITY_SKILLS_DIR", str(pathlib.Path.home() / ".claude" / "skills")))
TXN = pathlib.Path(os.environ.get("VERITY_TRANSCRIPTS_DIR", str(pathlib.Path.home() / ".claude" / "projects")))


def _frontmatter(p):
    name, desc = p.parent.name, ""
    try: txt = p.read_text(errors="ignore")
    except Exception: return name, "", 0
    m = re.search(r"^---\s*(.*?)\s*---", txt, re.S | re.M)
    fm = m.group(1) if m else txt[:400]
    nm = re.search(r"^name:\s*(.+)$", fm, re.M)
    dm = re.search(r"description:\s*[>|]?\s*(.+?)(?:\n\w+:|\Z)", fm, re.S)
    if nm: name = nm.group(1).strip().strip('"\'')
    if dm: desc = re.sub(r"\s+", " ", dm.group(1)).strip().strip('"\'')
    return name, desc, (len(name) + len(desc)) // 4


def load_skills():
    out = []
    for sm in glob.glob(str(SKILLS / "*" / "SKILL.md")):
        p = pathlib.Path(sm); n, d, c = _frontmatter(p)
        out.append({"name": n, "dir": p.parent.name, "desc": d, "cost": c})
    return out


def find_dupes(skills, thresh=0.6):
    sigs = {s["dir"]: {w for w in re.findall(r"[a-z][a-z0-9-]{4,}", (s["desc"] or s["name"]).lower())} for s in skills}
    word_to = defaultdict(list)
    for d, sg in sigs.items():
        for w in sg: word_to[w].append(d)
    cand = set()
    for w, ds in word_to.items():
        if not (2 <= len(ds) <= 60): continue
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                cand.add(tuple(sorted((ds[i], ds[j]))))
    dupe = {}
    for a, b in cand:
        sa, sb = sigs[a], sigs[b]
        if sa and sb and len(sa & sb) / len(sa | sb) >= thresh:
            dupe.setdefault(a, []).append(b); dupe.setdefault(b, []).append(a)
    return dupe


def scan_usage(skills):
    counts = {s["dir"]: 0 for s in skills}
    names = {s["name"]: s["dir"] for s in skills}
    files = glob.glob(str(TXN / "**" / "*.jsonl"), recursive=True) + glob.glob(str(TXN / "**" / "*.json"), recursive=True)
    if not files: return None
    pat = re.compile(r'"skill"\s*:\s*"([a-zA-Z0-9:_-]+)"|<command-name>/?([a-z0-9:_-]+)')
    for f in files:
        try: data = open(f, errors="ignore").read()
        except Exception: continue
        for m in pat.finditer(data):
            nm = (m.group(1) or m.group(2) or "").split(":")[-1]
            d = names.get(nm) or (nm if nm in counts else None)
            if d in counts: counts[d] += 1
    return counts


def audit(with_usage=False):
    skills = load_skills(); dupes = find_dupes(skills)
    usage = scan_usage(skills) if with_usage else None
    for s in skills:
        s["dupes"] = len(dupes.get(s["dir"], []))
        s["uses"] = usage.get(s["dir"]) if usage else None
        risk = s["cost"] * (1 + 0.5 * s["dupes"])
        if usage is not None: risk *= 3.0 if s["uses"] == 0 else 1.0 / (1 + s["uses"])
        s["risk"] = round(risk, 1)
        if usage is not None:
            s["verdict"] = "CUT" if (s["uses"] == 0 and (s["dupes"] or s["cost"] > 120)) else \
                           ("REVIEW" if s["uses"] <= 1 and s["cost"] > 150 else "KEEP")
        else:
            s["verdict"] = "REVIEW" if (s["dupes"] and s["cost"] > 120) else "KEEP"
    return skills, sum(s["cost"] for s in skills), usage is not None


def _ab(name, task):
    sm = SKILLS / name / "SKILL.md"
    if not sm.exists(): print(f"skill '{name}' not found"); return 1
    g = sm.read_text(errors="ignore")[:4000]
    cl = str(pathlib.Path.home() / ".local" / "bin" / "claude")
    run = lambda p: (subprocess.run([cl, "-p", p], capture_output=True, text=True, timeout=300).stdout or "").strip()
    without = run(task); with_ = run(f"Follow this skill, then do the task.\n\nSKILL:\n{g}\n\nTASK: {task}")
    delta = round((1 - SequenceMatcher(None, without, with_).ratio()) * 100, 1)
    print(f"output divergence with/without '{name}': {delta}%")
    print("→ " + ("REAL LIFT — keep." if delta > 25 else "LOW LIFT — CUT candidate." if delta < 8 else "MODERATE — judge manually."))
    return 0


def _cli(argv):
    if argv and argv[0] == "--ab":
        return _ab(argv[1], " ".join(argv[2:])) if len(argv) >= 3 else print('usage: --ab <skill> "<task>"')
    js = argv[argv.index("--json") + 1] if "--json" in argv else None
    skills, total, had = audit("--with-usage" in argv)
    skills.sort(key=lambda s: -s["risk"])
    if js: json.dump(skills, open(js, "w"), indent=1); print(f"wrote {js}"); return 0
    cuts = [s for s in skills if s["verdict"] == "CUT"]
    print(f"== SKILL AUDIT — {len(skills)} skills, ~{total:,} tokens of always-on catalog tax ==")
    print(f"   usage: {'ON' if had else 'OFF (--with-usage for the real CUT list)'}")
    print(f"   CUT: {len(cuts)} · reclaim ~{sum(s['cost'] for s in cuts):,} tokens/session\n")
    for s in (cuts if had else [x for x in skills if x['verdict'] != 'KEEP'])[:25]:
        u = "-" if s["uses"] is None else s["uses"]
        print(f"  {s['dir'][:32]:<32}{s['cost']:>6}{s['dupes']:>4} dup{str(u):>5} use  {s['verdict']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

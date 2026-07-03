#!/usr/bin/env python3
"""verity broker — Just-In-Time capability broker with a VERITY vet gate.

Keep a catalog of repos/skills you *might* need, without installing any of them. Mount one on
demand, gate it through `verity vet` (unvetted instruction-surfaces never become your agent's
directives), lease it with a TTL, and auto-release it — reclaiming disk — when the task is done.

  Lifecycle:  find → use (vet → mount → lease) → [work] → release (unmount → reclaim)

Reads don't need to clone — a `repo` entry prints its `verity stream` command (zero disk); only
skills / executables materialize, ephemerally, after the vet clears. This is how you make hundreds
of capabilities reachable without the bloat and credential sprawl of installing them all.

Paths are portable (override via env):
  VERITY_BROKER_HOME    state + cache root   (default ~/.verity)
  VERITY_BROKER_SKILLS  where skills symlink (default ~/.claude/skills if present, else <home>/skills)

  verity broker add <name> <git-url> [--kind skill|repo|mcp]   # catalog an entry
  verity broker find "<need>" [N]      # search the catalog
  verity broker show <name>
  verity broker use  <name> [--ttl M] [--exec]   # VET → mount → lease (default 60m)
  verity broker active | release <name> | sweep | stats
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, time, pathlib

HOME = pathlib.Path(os.environ.get("VERITY_BROKER_HOME", str(pathlib.Path.home() / ".verity")))
CACHE = HOME / "capability-cache"
IDX = HOME / "broker-index.json"
LEASES = HOME / "broker-leases.json"
_sk = os.environ.get("VERITY_BROKER_SKILLS")
SKILLS = pathlib.Path(_sk) if _sk else (
    pathlib.Path.home() / ".claude" / "skills" if (pathlib.Path.home() / ".claude" / "skills").exists()
    else HOME / "skills")
DEFAULT_TTL = 60


def _load(p, d):
    try: return json.loads(pathlib.Path(p).read_text())
    except Exception: return d

def _save(p, o):
    pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(p).write_text(json.dumps(o, indent=1))

def _slug(u): return u.rstrip("/").split("/")[-1].replace(".git", "")


def add(name, url, kind="repo"):
    idx = _load(IDX, {})
    idx[name] = {"name": name, "url": url, "kind": kind,
                 "cred": bool(re.search(r"auth|token|api[_-]?key|credential", url, re.I))}
    _save(IDX, idx); print(f"cataloged {name} ({kind}) → {url}")


def find(query, n=8):
    idx = _load(IDX, {}); q = query.lower().split()
    hits = []
    for name, r in idx.items():
        blob = f"{name} {r.get('kind','')} {r.get('what','')}".lower()
        s = sum(blob.count(w) for w in q) + (3 if all(w in name.lower() for w in q) else 0)
        if s: hits.append((s, r))
    hits.sort(key=lambda x: -x[0])
    if not hits:
        print(f"no catalog match for '{query}' ({len(idx)} entries). add with: verity broker add"); return
    for _, r in hits[:n]:
        print(f"  {r['name']:<26} [{r.get('kind')}]" + ("  🔑needs-key" if r.get("cred") else ""))
    print("\nmount:  verity broker use <name>")


def show(name):
    r = _load(IDX, {}).get(name)
    print(json.dumps(r, indent=1) if r else f"'{name}' not cataloged")


def _vet_ok(path):
    """VERITY safe-to-apply gate. Returns (ok, one-line-reason)."""
    try:
        from .vet import vet
        res = vet(str(path))
        line = res.report().splitlines()[0]
        return res.verdict != "BLOCK", line
    except Exception:
        # fallback to the CLI if imported context differs
        p = subprocess.run([sys.executable, "-m", "verity", "vet", str(path)],
                           capture_output=True, text=True, timeout=120)
        out = (p.stdout + p.stderr)
        return ("🛑 BLOCK" not in out and "DO NOT APPLY" not in out.upper()), out.strip().splitlines()[0] if out.strip() else "vet ran"


def use(name, ttl=DEFAULT_TTL, exec_ok=False):
    idx = _load(IDX, {}); r = idx.get(name)
    if not r: print(f"'{name}' not cataloged. verity broker add {name} <url>"); return 1
    leases = _load(LEASES, {})
    if name in leases:
        leases[name]["expires"] = time.time() + ttl * 60; _save(LEASES, leases)
        print(f"↻ {name} already mounted — lease +{ttl}m"); return 0

    url, kind = r["url"], r.get("kind", "repo")
    if kind == "repo" and not exec_ok:
        gh = re.search(r"github\.com/([\w.-]+/[\w.-]+)", url)
        print(f"◈ {name} is read-only → stream, don't clone (zero disk):")
        if gh: print(f"    verity stream github {gh.group(1)} README.md 120")
        print("    (needs execution? re-run with --exec)"); return 0

    dest = CACHE / name; CACHE.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        print(f"⇣ shallow-cloning {url} (ephemeral) …")
        if subprocess.run(["git", "clone", "--depth", "1", "--no-tags", "-q", url, str(dest)],
                          capture_output=True, timeout=180).returncode != 0:
            shutil.rmtree(dest, ignore_errors=True); print(f"✗ clone failed"); return 1

    ok, msg = _vet_ok(dest)
    if not ok:
        shutil.rmtree(dest, ignore_errors=True)
        print(f"🛑 VERITY vet BLOCKED — not mounted. ({msg})"); return 2

    links = []
    skmd = list(dest.glob("**/SKILL.md"))[:1]
    if kind == "skill" or skmd:
        skdir = skmd[0].parent if skmd else dest
        SKILLS.mkdir(parents=True, exist_ok=True)
        link = SKILLS / name
        if link.exists() or link.is_symlink(): link.unlink()
        link.symlink_to(skdir); links.append(str(link))
        print(f"🔗 skill mounted → {link}")
    else:
        print(f"📁 mounted at {dest}")

    leases[name] = {"mounted": time.time(), "expires": time.time() + ttl * 60,
                    "kind": kind, "cache": str(dest), "links": links, "vet": msg}
    _save(LEASES, leases)
    print(f"✓ {name} ACTIVE — vetted, leased {ttl}m. release: verity broker release {name}")
    if r.get("cred"): print("  🔑 needs a credential — code mounted; supply the key to run live.")
    return 0


def release(name, quiet=False):
    leases = _load(LEASES, {}); l = leases.pop(name, None)
    if not l:
        if not quiet: print(f"{name} not mounted");
        return
    for lk in l.get("links", []):
        try: pathlib.Path(lk).unlink()
        except Exception: pass
    shutil.rmtree(l.get("cache", ""), ignore_errors=True); _save(LEASES, leases)
    if not quiet: print(f"⏏ released {name} — disk reclaimed")


def active():
    leases = _load(LEASES, {})
    if not leases: print("nothing mounted (clean)"); return
    now = time.time()
    for n, l in leases.items():
        left = int((l["expires"] - now) / 60)
        print(f"  {n:<24} {l.get('kind'):<7} {left:+d}m {'EXPIRED' if left < 0 else ''}")


def sweep():
    leases = _load(LEASES, {}); now = time.time()
    exp = [n for n, l in leases.items() if l["expires"] < now]
    for n in exp: release(n, quiet=True)
    print(f"swept {len(exp)} expired: {', '.join(exp) or '(none)'}")


def stats():
    idx = _load(IDX, {}); print(f"catalog: {len(idx)} | mounted: {len(_load(LEASES, {}))} | cache: {CACHE}")


def _cli(argv):
    if not argv: print(__doc__); return 0
    c, rest = argv[0], argv[1:]
    if c == "add" and len(rest) >= 2:
        add(rest[0], rest[1], rest[rest.index("--kind")+1] if "--kind" in rest else "repo")
    elif c == "find": find(rest[0] if rest else "", int(rest[1]) if len(rest) > 1 else 8)
    elif c == "show" and rest: show(rest[0])
    elif c == "use" and rest:
        nm = next((x for x in rest if not x.startswith("-")), None)
        ttl = int(rest[rest.index("--ttl")+1]) if "--ttl" in rest else DEFAULT_TTL
        return use(nm, ttl, "--exec" in rest)
    elif c == "release" and rest: release(rest[0])
    elif c == "active": active()
    elif c == "sweep": sweep()
    elif c == "stats": stats()
    else: print(__doc__); return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

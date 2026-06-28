#!/usr/bin/env python3
"""X / Twitter reach (optional) — resilient search/timeline via the maintained
`twscrape` library. Wired in as an OPTIONAL dependency so public VERITY users get
working X retrieval (the search-before-concluding gate is only as good as the
agent's reach), without bloating the zero-dependency core.

Why twscrape (researched 2026-06-28, see docs/x-scraper-resilience.md):
X rotates queryIds, features, guest tokens, the JS asset path, AND validates a
client-side `x-client-transaction-id`. Hand-rolled clients break on a ~2–4 week
cycle. twscrape tracks all of it (its `xclid.XClIdGen` computes the real txn-id
against X's current `abs.twimg.com/x-web/*.js` bundle) — so VERITY reuses it
instead of reverse-engineering. REUSE > rebuild.

Install:  pip install twscrape            (or: pip install -r requirements-reach.txt)
Setup  :  python3 -m verity reach setup    (one-time: add your X account/cookies)
Use    :  python3 -m verity reach x-search "ai agents github" --limit 20
"""
from __future__ import annotations

import asyncio
import sys


class ReachNotAvailable(RuntimeError):
    """twscrape missing or no account configured — carries an actionable fix."""


def _api():
    try:
        from twscrape import API
    except Exception as e:                       # not installed
        raise ReachNotAvailable(
            "twscrape not installed. Enable X reach:\n"
            "  pip install twscrape   (or: pip install -r requirements-reach.txt)\n"
            f"  ({e})")
    return API()


async def _search(query: str, limit: int = 20):
    api = _api()
    out = []
    try:
        async for tw in api.search(query, limit=limit):
            out.append({"id": str(tw.id), "user": tw.user.username,
                        "date": str(tw.date), "text": tw.rawContent,
                        "url": tw.url, "likes": tw.likeCount})
    except Exception as e:
        raise ReachNotAvailable(
            "X search failed — usually no account in the twscrape pool.\n"
            "Add one (cookies stay local):\n"
            "  python3 -m verity reach setup\n"
            f"  (underlying: {e})")
    return out


def x_search(query: str, limit: int = 20):
    """Synchronous wrapper: list of tweet dicts, or raises ReachNotAvailable
    with a concrete setup step (never a bare failure — VERITY's reach philosophy)."""
    return asyncio.run(_search(query, limit))


_SETUP = """\
X reach setup (one-time) — twscrape keeps sessions in a local SQLite pool:

  pip install twscrape
  # add an account by COOKIES (no password stored; cookies stay local):
  python3 - <<'PY'
  import asyncio
  from twscrape import API
  async def main():
      api = API()
      # auth_token + ct0 from your logged-in browser's x.com cookies:
      await api.pool.add_account("acct", "x", "x", "x",
                                 cookies="auth_token=<AUTH_TOKEN>; ct0=<CT0>")
      print("added")
  asyncio.run(main())
  PY

Then:  python3 -m verity reach x-search "your query" --limit 20
Cookies never leave your machine. See docs/x-scraper-resilience.md for the full
threat model and why this path survives X's rotation.
"""


def _cli(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0
    if argv[0] == "setup":
        print(_SETUP); return 0
    if argv[0] in ("x-search", "search"):
        limit = 20
        terms = []
        i = 1
        while i < len(argv):
            if argv[i] == "--limit" and i + 1 < len(argv):
                limit = int(argv[i + 1]); i += 2; continue
            terms.append(argv[i]); i += 1
        if not terms:
            print('usage: verity reach x-search "<query>" [--limit N]', file=sys.stderr)
            return 2
        try:
            rows = x_search(" ".join(terms), limit)
        except ReachNotAvailable as e:
            print(str(e), file=sys.stderr); return 3
        for r in rows:
            print(f"@{r['user']}  {r['url']}\n  {r['text'][:160]}\n")
        print(f"[{len(rows)} results]")
        return 0
    print(f"unknown reach subcommand: {argv[0]}", file=sys.stderr); return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))

# X / Twitter scraper resilience — a reusable resource synthesis (2026-06-28)

A worked example of the **REUSE > reverse-engineer** principle and the
[persistence gate](PERSISTENCE-GATE.md). When an X GraphQL endpoint 404s, the fix
almost always already exists in a maintained scraper's source. This is the map.

## The moving parts X rotates (the threat model)

X deliberately breaks reverse-engineered clients on a ~2–4 week cycle:
- **GraphQL operation queryIds** (`/i/api/graphql/<queryId>/<Op>`) rotate.
- **Required `features` flags** change; a missing/extra flag → rejection.
- **Guest tokens** expire (hours); every unauthenticated GraphQL call needs one.
- **`x-client-transaction-id`** — a per-(method, path) obfuscated header X computes
  client-side from its own JS bundle. Strictly validated on some endpoints
  (SearchTimeline) and **not** on others (Bookmarks). A random value → 404.
- **JS asset path** itself moves — as of 2026 the bundle lives at
  `https://abs.twimg.com/x-web/*.js` with an indices file `sign.o-*.js`. Scrapers
  that hard-code the old path silently fail to find the txn-id algorithm.

## The sources, and what each is good for

| Source | Verdict | Use it for |
|---|---|---|
| **[twscrape](https://github.com/vladkens/twscrape)** (vladkens) | ✅ maintained 2026 | **Ground truth.** Account-pool, cookie sessions in SQLite, account rotation on rate-limit. `twscrape.xclid.XClIdGen` is the working `x-client-transaction-id` generator (fixed in #312/#313 for the new asset path). `api.py` carries current `OP_*` queryIds + `GQL_FEATURES`. Read this FIRST. |
| **[trevorhobenshield/twitter-api-client](https://github.com/trevorhobenshield/twitter-api-client)** | ✅ active | v1/v2/GraphQL, `scraper.py` SearchTimeline reference; alternate feature sets. |
| **[gallery-dl](https://github.com/mikf/gallery-dl)** (issue [#9275](https://github.com/mikf/gallery-dl/issues/9275)) | 🔎 signal | Confirms when a SearchTimeline 404 is *widespread* (vs your setup). Heavily maintained → its issue tracker dates the breakage. |
| **[iSarabjitDhiman/XClientTransaction](https://github.com/iSarabjitDhiman/XClientTransaction)** | ⚠️ lagging | The original txn-id reverse-engineering writeup (educational), but its `get_ondemand_file_url` matched the OLD asset path and returns `None` against current X. Don't grind it — read twscrape's port instead. |
| **[XClientTransactionJS](https://github.com/swyxio/XClientTransactionJS)** / **[Lqm1/x-client-transaction-id](https://github.com/Lqm1/x-client-transaction-id)** | ↔ JS port | If you need the txn-id in a JS/Deno runtime. |
| bb-browser issue [#158](https://github.com/epiral/bb-browser/issues/158) | ❌ misleading | Claimed X "removed" txn-id signing — actually they just **moved** the webpack module; the mechanism still exists. A reminder to verify a "it's removed" claim against a tool that still works. |

## The working recipe (verified 2026-06-28)

1. **queryId**: use the maintained scraper's current value — don't scrape it blind.
   SearchTimeline was `Bcw3RzK-PatNAmbnw54hFw` (confirmed live in twscrape).
2. **Auth**: cookie auth (`auth_token` + `ct0`); send `ct0` as `x-csrf-token` and
   re-read it fresh per request (stale CSRF → 403).
3. **TLS**: X anti-bot inspects the TLS fingerprint; plain `urllib` → 404. Use
   `curl_cffi` with `impersonate="chrome"` (or a real browser).
4. **`x-client-transaction-id`**: generate the REAL value.
   ```python
   from twscrape.xclid import XClIdGen   # pip install --user --break-system-packages twscrape
   gen = await XClIdGen.create()          # fetches x.com/tesla + abs.twimg.com/x-web/*.js (~1.5s)
   header = gen.calc("GET", "/i/api/graphql/<queryId>/SearchTimeline")
   ```
   Build once per process, cache, regenerate on a 404 (twscrape's `XClIdGenStore`
   does exactly this).
5. **variables**: `product: "Latest"`, `querySource: "typed_query"`, `count: 20`.

Result: SearchTimeline → **200**, real timeline entries.

## The meta-lesson

The 404 looked like an impassable wall for 7 attempts because the work being
repeated was the *same* dead path. The wall dissolved the moment a **different**
move was made: read the maintained competitor's source. That is precisely what the
[persistence gate](PERSISTENCE-GATE.md) forces before any "can't."

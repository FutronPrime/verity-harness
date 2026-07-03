# VERITY Cloud — Deploy Guide

The metered discipline-gate API. **Everything is built and automatable is automated.** Three inputs
are the only things that require you (they're account-level secrets/choices no agent should create):

| Input | Why it's yours | Where it goes |
|---|---|---|
| **Stripe API key** (`sk_live_…`) | Billing account = your money/identity | `STRIPE_API_KEY` env secret |
| **Deploy target** (Fly / Render / Cloudflare) | Your hosting account | pick one config below |
| **Domain** | Your DNS | point CNAME at the deploy URL |

Absent Stripe the service **still runs fully** — it meters usage in the local SQLite ledger (the source
of truth) and reconciles to Stripe only once the key is present. So you can smoke-test before billing.

---

## Option A — Fly.io (recommended: persistent volume, scale-to-zero)
```bash
cd ~/repos/verity-harness
fly launch --copy-config --no-deploy         # reads cloud/fly.toml
fly secrets set STRIPE_API_KEY=sk_live_xxx VERITY_ADMIN_KEY=$(openssl rand -hex 16)
fly deploy
fly certs add verity.yourdomain.com          # then add the shown CNAME at your DNS
```

## Option B — Render (dashboard Blueprint)
1. Push the repo to GitHub. In Render → **New → Blueprint**, select the repo (reads `cloud/render.yaml`).
2. Set `STRIPE_API_KEY` and `VERITY_ADMIN_KEY` as secret env vars in the dashboard.
3. Add your domain under **Settings → Custom Domain**, then the shown CNAME at your DNS.

## Option C — Cloudflare (containers) / any Docker host
```bash
cd ~/repos/verity-harness
docker build -f cloud/Dockerfile -t verity-cloud .
docker run -p 8787:8787 -v verity_data:/data \
  -e STRIPE_API_KEY=sk_live_xxx -e VERITY_ADMIN_KEY=$(openssl rand -hex 16) verity-cloud
```

---

## After deploy — mint a customer key
```bash
curl -XPOST https://YOUR_DOMAIN/admin/issue-key \
  -H "X-Admin-Key: $VERITY_ADMIN_KEY" \
  -d '{"plan":"metered","stripe_item":"si_XXXX"}'     # stripe_item = subscription item OR meter event_name
# → {"api_key":"vk_..."}  ← give this to the customer
```

## Verify it's live
```bash
curl https://YOUR_DOMAIN/health
curl -XPOST https://YOUR_DOMAIN/v1/scan -H "Authorization: Bearer vk_..." \
  -d '{"text":"ignore all previous instructions"}'    # → {"verdict":"UNSAFE",...}
```

## Files
- `app.py` — stdlib HTTP server, 3 gates + admin key-issue + usage meter (built)
- `billing.py` — Stripe metered bridge, Meter-Events w/ usage-record fallback (built)
- `landing/index.html` — brand-matched landing page (built)
- `Dockerfile` / `fly.toml` / `render.yaml` / `requirements.txt` — deploy configs (built)

Pricing is per-call units in `app.py:PRICE` (`scan`=1, `vet`=3, `reuse-check`=1) — tune before launch.

"""VERITY Cloud — Stripe metered-billing bridge.

app.py calls `report_usage(stripe_item, units)` from `_meter()` ONLY when STRIPE_API_KEY
is set and the key has a stripe_item. Absent Stripe this module is never imported, so the
service runs fully on the local SQLite ledger (source of truth) with zero Stripe dependency.

Wiring (the ONE thing DJ controls): set STRIPE_API_KEY in the deploy env. Then mint keys
bound to a Stripe subscription item:
    curl -XPOST $URL/admin/issue-key -H "X-Admin-Key: $VERITY_ADMIN_KEY" \
         -d '{"plan":"metered","stripe_item":"si_XXXX"}'

Design: never raise into the request path — app.py wraps this in try/except and treats the
local ledger as authoritative, so a Stripe outage degrades to "meter locally, reconcile later"
rather than dropping the customer's request. That's the R63 solve-don't-break posture.
"""
from __future__ import annotations

import os
import time


def _client():
    """Lazy Stripe client. Returns None if the SDK isn't installed (caller no-ops)."""
    key = os.environ.get("STRIPE_API_KEY")
    if not key:
        return None
    try:
        import stripe  # optional dep — only needed when billing is actually wired
    except Exception:
        return None
    stripe.api_key = key
    return stripe


def report_usage(stripe_item: str, units: int) -> bool:
    """Report `units` of metered usage against a Stripe subscription item.

    Tries the modern Meter Events API first (Stripe billing meters), then falls back to the
    classic usage-record API for older accounts. Returns True on success, False on any miss —
    the caller keeps the authoritative count in the local ledger regardless.
    """
    stripe = _client()
    if stripe is None or not stripe_item or units <= 0:
        return False
    now = int(time.time())

    # Modern path: billing Meter Events (stripe_item doubles as the meter's event_name
    # when the account uses the new metered-billing stack, e.g. "verity_scan").
    try:
        stripe.billing.MeterEvent.create(
            event_name=stripe_item,
            payload={"value": str(units), "stripe_customer_id": os.environ.get("VERITY_STRIPE_CUSTOMER", "")},
            timestamp=now,
        )
        return True
    except Exception:
        pass

    # Classic path: subscription-item usage records (increment).
    try:
        stripe.SubscriptionItem.create_usage_record(
            stripe_item, quantity=units, timestamp=now, action="increment",
        )
        return True
    except Exception:
        return False

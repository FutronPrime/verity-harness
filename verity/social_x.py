#!/usr/bin/env python3
"""Post to X/Twitter — reliably, with HONEST failure detection.

WHY THIS EXISTS (the lesson, encoded so no agent repeats it):
X now requires an `x-client-transaction-id` anti-automation header for WRITES. The old
cookie-HTTP trick (auth_token + ct0 → GraphQL CreateTweet) now returns **HTTP 200 with an
EMPTY tweet_results and creates NOTHING** — a silent false success. Any code that treats
200 as "posted" is lying. ALWAYS verify a write produced a real tweet id.

Two paths that actually work:
  1. **Official X API (this module)** — OAuth 1.0a, browser-free, supports media. Needs the
     user's own 4 keys (free tier ~1,500 writes/mo at developer.x.com). Zero pip deps —
     OAuth 1.0a is signed with stdlib hmac/hashlib here.
  2. **Real browser client** — the actual x.com web app generates the transaction-id, so
     driving the composer works; attach media via SYSTEM-CLIPBOARD PASTE (file-upload
     sandboxes + x.com CSP block other automated attach paths). See capabilities_guide().

Env keys (same names the popular auto-poster repos use):
  X_CONSUMER_KEY  X_CONSUMER_SECRET  X_ACCESS_TOKEN  X_ACCESS_SECRET
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from typing import Optional


def _q(s: str) -> str:
    return urllib.parse.quote(str(s), safe="~")


def _oauth_header(method: str, url: str, creds: dict, query: Optional[dict] = None) -> str:
    """Build an OAuth 1.0a Authorization header. Body params are NOT signed for JSON or
    multipart requests — only oauth_* and URL query params are."""
    oauth = {
        "oauth_consumer_key": creds["consumer_key"],
        "oauth_nonce": base64.b64encode(os.urandom(24)).decode().strip("="),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": creds["access_token"],
        "oauth_version": "1.0",
    }
    sign_params = {**oauth, **(query or {})}
    base = "&".join(f"{_q(k)}={_q(sign_params[k])}" for k in sorted(sign_params))
    base_str = f"{method.upper()}&{_q(url)}&{_q(base)}"
    key = f"{_q(creds['consumer_secret'])}&{_q(creds['access_secret'])}"
    oauth["oauth_signature"] = base64.b64encode(
        hmac.new(key.encode(), base_str.encode(), hashlib.sha1).digest()
    ).decode()
    return "OAuth " + ", ".join(f'{_q(k)}="{_q(v)}"' for k, v in sorted(oauth.items()))


def _creds_from_env(env: Optional[dict] = None) -> Optional[dict]:
    e = env or os.environ
    try:
        return {
            "consumer_key": e["X_CONSUMER_KEY"], "consumer_secret": e["X_CONSUMER_SECRET"],
            "access_token": e["X_ACCESS_TOKEN"], "access_secret": e["X_ACCESS_SECRET"],
        }
    except KeyError:
        return None


def _upload_media(image_path: str, creds: dict) -> str:
    url = "https://upload.twitter.com/1.1/media/upload.json"
    img = open(image_path, "rb").read()
    b = "----verityX" + str(len(img))
    body = (f'--{b}\r\nContent-Disposition: form-data; name="media"; filename="x"\r\n\r\n'
            ).encode() + img + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": _oauth_header("POST", url, creds),
        "Content-Type": f"multipart/form-data; boundary={b}",
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["media_id_string"]


def post_to_x(text: str, image_path: Optional[str] = None, creds: Optional[dict] = None,
              env: Optional[dict] = None) -> dict:
    """Post to X via the official API. Returns {"ok": bool, ...}. NEVER reports a write as
    successful without a real tweet id (the anti-silent-failure guarantee)."""
    creds = creds or _creds_from_env(env)
    if not creds:
        return {"ok": False, "error": (
            "No X API keys. Set X_CONSUMER_KEY / X_CONSUMER_SECRET / X_ACCESS_TOKEN / "
            "X_ACCESS_SECRET (free at developer.x.com, ~1,500 writes/mo). Or post via the real "
            "browser client (clipboard-paste for media) — cookie-HTTP CreateTweet silently fails.")}
    payload = {"text": text}
    if image_path:
        try:
            payload["media"] = {"media_ids": [_upload_media(image_path, creds)]}
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"media upload failed HTTP {e.code}: {e.read().decode()[:300]}"}
    url = "https://api.twitter.com/2/tweets"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={
        "Authorization": _oauth_header("POST", url, creds),
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
        tid = res.get("data", {}).get("id")
        if not tid:                       # anti-silent-failure: no id => NOT posted
            return {"ok": False, "error": "X returned no tweet id — write not confirmed", "raw": res}
        return {"ok": True, "tweet_id": tid, "url": f"https://x.com/i/web/status/{tid}"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:400]}"}


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    img = None
    if "--image" in args:
        i = args.index("--image"); img = args[i + 1]; args = args[:i] + args[i + 2:]
    if not args:
        print("usage: python3 -m verity.social_x \"<text>\" [--image <path>]"); sys.exit(1)
    print(json.dumps(post_to_x(" ".join(args), image_path=img), indent=2))

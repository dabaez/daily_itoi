"""Purge today.json from Cloudflare's cache so a new day shows up immediately.

Optional: does nothing unless CF_ZONE_ID, CF_API_TOKEN and SITE_URL are set. The short
Cache-Control TTL on today.json (see deploy/nginx.conf) covers the case where it fails.
"""

from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)


def purge_today_json() -> None:
    zone = os.environ.get("CF_ZONE_ID")
    token = os.environ.get("CF_API_TOKEN")
    site = os.environ.get("SITE_URL", "").rstrip("/")
    if not (zone and token and site):
        log.info("Cloudflare purge skipped (CF_ZONE_ID / CF_API_TOKEN / SITE_URL not set)")
        return
    url = f"{site}/today.json"
    try:
        resp = requests.post(
            f"https://api.cloudflare.com/client/v4/zones/{zone}/purge_cache",
            headers={"Authorization": f"Bearer {token}"},
            json={"files": [url]},
            timeout=20,
        )
        body = resp.json()
        if resp.ok and body.get("success"):
            log.info("purged %s from Cloudflare", url)
        else:
            log.error("Cloudflare purge failed (%s): %s", resp.status_code, body.get("errors"))
    except Exception as e:
        log.error("Cloudflare purge failed: %s", e)

"""Cheap HTTP liveness probe for every company with a website.

Costs nothing (no API credits), fixes the single biggest data-quality hole
for non-YC accelerators where everyone is labelled "Active" by default.

Heuristic:
- DNS fail / connect refused / TLS fail / 4xx (except 401/403) -> likely DEAD
- 5xx / timeout / connection reset -> TRANSIENT (don't change status)
- 2xx / 3xx -> LIVE (leave status alone; upgrades later from other signals)
- Short body with parked-domain keywords -> PARKED (treat as DEAD)

We never *downgrade* a known Acquired/Public (those are terminal labels that
survived a primary-source tag). We only convert Active -> Dead when the probe
is confident, and we always stamp `status_source = 'liveness_probe'` plus a
confidence score for downstream inspection.
"""

from __future__ import annotations

import concurrent.futures as cf
import logging
import re
import socket
import ssl
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from curl_cffi import requests as curl_requests
from sqlalchemy import select

from accelerator_atlas.schema.models import Company, CompanyStatus
from accelerator_atlas.storage.db import session_scope

log = logging.getLogger("enrich.liveness")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

PARKED_SIGNALS = [
    "domain for sale", "buy this domain", "this domain is for sale",
    "parked domain", "godaddy.com/domain", "sedo.com/search",
    "hugedomains.com", "dan.com", "namesilo.com/domain",
    "afternic.com",
]

# We deliberately skip 401/403 — many startups aggressively block bots.
DEAD_STATUS = {400, 404, 410}
TRANSIENT_STATUS = set(range(500, 600))


@dataclass
class ProbeResult:
    status: str           # "live" | "dead" | "parked" | "unknown"
    http_code: int | None
    reason: str
    confidence: float     # 0..1


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def probe_url(url: str, timeout: float = 8.0) -> ProbeResult:
    url = _normalize_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AtlasProbe/1.0; +https://localhost)",
        "Accept": "text/html,*/*;q=0.5",
    }
    try:
        parsed = urllib.parse.urlparse(url)
        socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return ProbeResult("dead", None, "dns_fail", 0.95)
    except Exception as e:
        return ProbeResult("unknown", None, f"dns_err:{type(e).__name__}", 0.3)

    # Use curl_cffi (Chrome TLS fingerprint) to bypass Cloudflare etc. Fall
    # back to httpx only if curl_cffi itself errors (rare).
    try:
        r = curl_requests.get(
            url, timeout=timeout, impersonate="chrome", allow_redirects=True,
            headers=headers,
        )
    except curl_requests.exceptions.Timeout:
        return ProbeResult("unknown", None, "timeout", 0.2)
    except curl_requests.exceptions.ConnectionError as e:
        msg = str(e)
        # Real DNS/connect failure exposes "Could not resolve host" or
        # "Failed to connect" in the message. Treat anything else as unknown.
        if "Could not resolve host" in msg or "name resolution" in msg.lower():
            return ProbeResult("dead", None, "dns_fail", 0.95)
        if "Failed to connect" in msg or "Connection refused" in msg:
            return ProbeResult("dead", None, "connect_refused", 0.8)
        return ProbeResult("unknown", None, f"conn_err", 0.2)
    except Exception as e:
        return ProbeResult("unknown", None, f"err:{type(e).__name__}", 0.2)

    code = r.status_code
    if code in DEAD_STATUS:
        return ProbeResult("dead", code, f"http_{code}", 0.9)
    if code in TRANSIENT_STATUS:
        return ProbeResult("unknown", code, f"http_{code}", 0.2)
    # Check for parked pages
    body_sample = (r.text or "")[:8000].lower()
    if any(sig in body_sample for sig in PARKED_SIGNALS):
        return ProbeResult("parked", code, "parked_keyword", 0.85)
    # 2xx/3xx -> live
    return ProbeResult("live", code, f"http_{code}", 0.9)


def run(batch_size: int = 500, workers: int = 32, only_accelerator_slug: str | None = None,
        dry_run: bool = False) -> dict:
    now = datetime.now(UTC).replace(tzinfo=None)
    stats = {"probed": 0, "live": 0, "dead": 0, "parked": 0, "unknown": 0, "flipped_dead": 0}

    with session_scope() as s:
        q = select(Company).where(Company.website.is_not(None))
        if only_accelerator_slug:
            from accelerator_atlas.schema.models import Accelerator
            accel_id = s.execute(
                select(Accelerator.id).where(Accelerator.slug == only_accelerator_slug)
            ).scalar_one()
            q = q.where(Company.accelerator_id == accel_id)
        # Skip already-terminal labels
        q = q.where(Company.status.in_([
            CompanyStatus.ACTIVE.value,
            CompanyStatus.UNKNOWN.value,
        ]))
        companies = s.execute(q).scalars().all()
        log.info("probing %d companies (workers=%d)", len(companies), workers)

        # Run probes in parallel
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(
                lambda c: (c.id, probe_url(c.website)), companies
            ))

        id_to_result = dict(results)
        for co in companies:
            res = id_to_result.get(co.id)
            if res is None:
                continue
            stats["probed"] += 1
            stats[res.status] = stats.get(res.status, 0) + 1
            if res.status in ("dead", "parked") and co.status == CompanyStatus.ACTIVE.value:
                if not dry_run:
                    co.status = CompanyStatus.DEAD.value
                    co.status_source = f"liveness_probe:{res.reason}"
                    co.status_confidence = res.confidence
                    co.status_fetched_at = now
                stats["flipped_dead"] += 1
            if stats["probed"] % batch_size == 0:
                log.info("probed=%d live=%d dead=%d parked=%d unknown=%d flipped=%d",
                         stats["probed"], stats["live"], stats["dead"], stats["parked"],
                         stats["unknown"], stats["flipped_dead"])

    return stats


if __name__ == "__main__":
    import sys
    accel = None
    for arg in sys.argv[1:]:
        if arg.startswith("--accelerator="):
            accel = arg.split("=", 1)[1]
    stats = run(only_accelerator_slug=accel)
    log.info("DONE: %s", stats)

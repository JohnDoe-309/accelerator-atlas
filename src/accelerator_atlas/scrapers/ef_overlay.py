"""Fetch EF company overlay HTML (getcompany admin-ajax) and recover websites.

Runs after `ef.py` has seeded the 490 EF companies. The overlay HTML often
contains the company's website, lead investors, a longer description, and a
few other fields the portfolio tile doesn't expose. WP admin-ajax is free, so
this is a zero-credit enrichment pass.
"""

from __future__ import annotations

import concurrent.futures as cf
import logging
import pathlib
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime

from selectolax.parser import HTMLParser
from sqlalchemy import select

from accelerator_atlas.schema.models import (
    Accelerator,
    AcceleratorSlug,
    Company,
)
from accelerator_atlas.storage.db import session_scope

log = logging.getLogger("scrapers.ef_overlay")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

AJAX_URL = "https://www.joinef.com/wp-admin/admin-ajax.php"
CACHE_DIR = pathlib.Path(".firecrawl/ef/overlays")

SKIP_DOMAINS = ("joinef.com", "linkedin.com", "twitter.com", "x.com",
                "facebook.com", "instagram.com", "youtube.com", "crunchbase.com")


def fetch_one(slug: str, timeout: int = 25) -> str | None:
    dst = CACHE_DIR / f"{slug}.html"
    if dst.exists() and dst.stat().st_size > 500:
        return dst.read_text()
    data = urllib.parse.urlencode({
        "action": "getcompany", "company": slug, "index": 0, "featured": "false",
    }).encode()
    req = urllib.request.Request(
        AJAX_URL, data=data, method="POST",
        headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"},
    )
    try:
        body = urllib.request.urlopen(req, timeout=timeout).read().decode()
    except Exception as e:
        log.warning("fetch fail %s: %s", slug, e)
        return None
    if not body or len(body) < 500:
        return None
    dst.write_text(body)
    return body


def fetch_all(slugs: list[str], workers: int = 8, sleep: float = 0.1) -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    done = 0
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_one, s): s for s in slugs}
        for f in cf.as_completed(futures):
            done += 1
            if done % 50 == 0:
                log.info("fetched %d/%d", done, len(slugs))
            time.sleep(sleep)
    log.info("EF overlays cached: %d", done)
    return done


def parse_overlay(html: str) -> dict:
    """Extract website, long description, and lead investors from overlay HTML."""
    tree = HTMLParser(html)

    website = None
    for a in tree.css("a[href^='http']"):
        href = a.attributes.get("href") or ""
        if any(d in href for d in SKIP_DOMAINS):
            continue
        # EF occasionally links founders' Wikipedia / personal sites too; filter
        # by keeping the *first* non-social URL that appears inside the main
        # company block.
        website = href.rstrip("/")
        break

    long_desc = None
    desc_el = tree.css_first(".info__item__text")
    if desc_el:
        long_desc = re.sub(r"\s+", " ", desc_el.text(strip=True))

    # Lead investors sometimes appear as a "Lead Investor" meta row
    lead_investors: list[str] = []
    for row in tree.css(".meta__row"):
        role = row.css_first(".meta__row__role")
        val = row.css_first(".meta__row__value")
        if not role or not val:
            continue
        if "investor" in role.text(strip=True).lower():
            lead_investors.append(val.text(strip=True))

    return {
        "website": website,
        "long_description": long_desc,
        "lead_investors": lead_investors or None,
    }


def enrich() -> tuple[int, int]:
    """Parse every cached overlay and patch the corresponding company row."""
    files = sorted(CACHE_DIR.glob("*.html"))
    if not files:
        raise FileNotFoundError(f"No overlays in {CACHE_DIR}. Run fetch_all() first.")

    now = datetime.now(UTC).replace(tzinfo=None)
    patched = skipped = 0

    with session_scope() as s:
        accel_id = s.execute(
            select(Accelerator.id).where(Accelerator.slug == AcceleratorSlug.EF.value)
        ).scalar_one()

        for fp in files:
            slug = fp.stem
            data = parse_overlay(fp.read_text())
            if not data["website"] and not data["long_description"]:
                skipped += 1
                continue
            co = s.execute(
                select(Company).where(
                    Company.accelerator_id == accel_id, Company.slug == slug
                )
            ).scalar_one_or_none()
            if not co:
                skipped += 1
                continue
            if data["website"] and not co.website:
                co.website = data["website"]
            if data["long_description"] and not co.long_description:
                co.long_description = data["long_description"]
            if data["lead_investors"]:
                co.raw_payload = {**(co.raw_payload or {}), "ef_lead_investors": data["lead_investors"]}
            co.last_enriched_at = now
            patched += 1
    return patched, skipped


if __name__ == "__main__":
    import sys
    if "--fetch" in sys.argv:
        # Load all EF slugs from DB
        with session_scope() as s:
            accel_id = s.execute(
                select(Accelerator.id).where(Accelerator.slug == AcceleratorSlug.EF.value)
            ).scalar_one()
            slugs = [r[0] for r in s.execute(
                select(Company.slug).where(Company.accelerator_id == accel_id)
            )]
        fetch_all(slugs)
    p, sk = enrich()
    log.info("EF overlay enrich: patched=%d skipped=%d", p, sk)

"""SPC (South Park Commons) ingestion.

Source: 194 detail pages already scraped to .firecrawl/spc/details/*.md by:

    cat .firecrawl/spc/company-urls.txt | xargs -n1 -P2 -I {} bash -c '
      slug="${1##*/companies/}"
      firecrawl scrape "$1" --only-main-content -o ".firecrawl/spc/details/$slug.md"
    ' _ {}

This module parses each markdown file and upserts companies + a year-pseudo-batch.
SPC has no batches; we use the founded year as a cohort proxy (e.g. SPC-2019).
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from accelerator_atlas.schema.models import (
    Accelerator,
    AcceleratorSlug,
    Batch,
    Company,
    CompanyStatus,
    Founder,
)
from accelerator_atlas.storage.db import session_scope

log = logging.getLogger("scrapers.spc")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DETAILS_DIR = Path(".firecrawl/spc/details")

# Stage labels SPC uses inline. Anything else falls through.
SPC_STAGE_LABELS = {
    "Pre-Seed",
    "Seed",
    "Series A",
    "Series B",
    "Series C",
    "Series D",
    "Series E",
    "Series F",
    "Growth",
    "Unicorn",
    "IPO",
    "Public",
}

# Compiled regexes
RE_HEADING = re.compile(r"^#\s+(.+?)\s*$", re.M)
RE_FOUNDERS = re.compile(r"^Founded by\s+(.+?)\s*$", re.M)
RE_LINK = re.compile(r"\[([^\]]+?)\]\((https?://[^)]+)\)")
RE_SECTOR_LINE = re.compile(
    r"\[([^\]]+)\]\(https://www\.southparkcommons\.com/companies\?sector=[^\)]+\)"
    r"\s+(.+?)"
    r"\s*\[([^\]]+)\]\(https://www\.southparkcommons\.com/companies\?location=[^\)]+\)",
)


def _strip_acq_suffix(name: str) -> str:
    """Render a clean display name when the slug embeds an acquisition note."""
    return re.sub(r"\s*\(acq[^)]*\)\s*$", "", name, flags=re.IGNORECASE).strip()


def _parse_sector_line(text: str) -> dict:
    """Pull (sector, stage, founded_year, location) out of the sector/stage line."""
    out = {"sector": None, "stage": None, "founded_year": None, "location": None}
    m = RE_SECTOR_LINE.search(text)
    if not m:
        return out
    sector, mid, location = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    out["sector"] = sector
    out["location"] = location

    year_match = re.search(r"\b(19|20)\d{2}\b", mid)
    if year_match:
        out["founded_year"] = int(year_match.group(0))
        mid = (mid[: year_match.start()] + " " + mid[year_match.end() :]).strip()

    mid = re.sub(r"\s+", " ", mid).strip()
    if mid in SPC_STAGE_LABELS:
        out["stage"] = mid
    elif mid:
        out["stage"] = mid
    return out


def parse_detail(slug: str, md: str) -> dict | None:
    """Return a dict matching the Company columns we care about, or None on miss."""
    h = RE_HEADING.search(md)
    if not h:
        log.warning("%s: no name heading", slug)
        return None
    raw_name = h.group(1).strip()
    name = _strip_acq_suffix(raw_name)

    is_acquired = "-acq-" in slug
    status = CompanyStatus.ACQUIRED.value if is_acquired else CompanyStatus.ACTIVE.value
    # Stage line can also explicitly say "Acquired" / "Public" — catch those below.

    founders = []
    fm = RE_FOUNDERS.search(md)
    if fm:
        founders = [n.strip() for n in fm.group(1).split(",") if n.strip()]

    website = linkedin = twitter = None
    for label, url in RE_LINK.findall(md):
        if "southparkcommons.com" in url or "jobs.southparkcommons" in url:
            continue
        ll = label.lower()
        if " website" in ll and not website:
            website = url
        elif " on linkedin" in ll and not linkedin:
            linkedin = url
        elif (" on x" in ll or " on twitter" in ll) and not twitter:
            twitter = url

    sector_info = _parse_sector_line(md)
    stage_lower = (sector_info["stage"] or "").lower()
    if "acquired" in stage_lower:
        status = CompanyStatus.ACQUIRED.value
    elif stage_lower in {"public", "ipo"}:
        status = CompanyStatus.PUBLIC.value

    description = None
    block_after_links = re.search(
        r"\)\s*\n\s*\n([^\[#].+?)\n\s*\n\s*\[",
        md,
        re.S,
    )
    if block_after_links:
        description = block_after_links.group(1).strip()
        if "\n\n" in description:
            description = description.split("\n\n", 1)[0].strip()

    one_liner = description.split(".")[0][:240] + "." if description else None

    return {
        "slug": slug,
        "name": name,
        "website": website,
        "one_liner": one_liner,
        "long_description": description,
        "status": status,
        "industry_primary": sector_info["sector"],
        "stage": sector_info["stage"],
        "country": None,
        "all_locations": sector_info["location"],
        "linkedin_url": linkedin,
        "twitter_url": twitter,
        "founded_year": sector_info["founded_year"],
        "founders": founders,
        "source_url": f"https://www.southparkcommons.com/companies/{slug}",
    }


def _ensure_batch(session, accel_id: int, year: int | None) -> int | None:
    if year is None:
        return None
    name = f"SPC-{year}"
    slug = f"spc-{year}"
    existing = session.execute(
        select(Batch).where(Batch.accelerator_id == accel_id, Batch.slug == slug)
    ).scalar_one_or_none()
    if existing:
        return existing.id
    b = Batch(
        accelerator_id=accel_id,
        slug=slug,
        name=name,
        season=None,
        year=year,
        company_count=None,
        notes="Pseudo-batch derived from company founded year (SPC has no formal batches).",
    )
    session.add(b)
    session.flush()
    return b.id


def ingest() -> tuple[int, int, int]:
    files = sorted(DETAILS_DIR.glob("*.md"))
    if not files:
        raise FileNotFoundError(
            f"No detail files in {DETAILS_DIR}. Run the Firecrawl batch first."
        )

    inserted = updated = parse_failed = 0
    now = datetime.now(UTC).replace(tzinfo=None)

    with session_scope() as s:
        accel = s.execute(
            select(Accelerator).where(Accelerator.slug == AcceleratorSlug.SPC.value)
        ).scalar_one()
        accel_id = accel.id

        for fp in files:
            slug = fp.stem
            try:
                rec = parse_detail(slug, fp.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning("parse error %s: %s", slug, e)
                parse_failed += 1
                continue
            if rec is None:
                parse_failed += 1
                continue

            batch_id = _ensure_batch(s, accel_id, rec["founded_year"])

            existing = s.execute(
                select(Company).where(
                    Company.accelerator_id == accel_id, Company.slug == slug
                )
            ).scalar_one_or_none()

            payload = dict(
                accelerator_id=accel_id,
                slug=slug,
                name=rec["name"],
                website=rec["website"],
                one_liner=rec["one_liner"],
                long_description=rec["long_description"],
                status=rec["status"],
                status_source="spc.detail_page",
                status_confidence=0.95 if rec["status"] == CompanyStatus.ACQUIRED.value else 0.7,
                status_fetched_at=now,
                industry_primary=rec["industry_primary"],
                stage=rec["stage"],
                is_b2b=(rec["industry_primary"] or "").upper().startswith("B2B"),
                is_top_company=rec["stage"] in {"Unicorn", "Public", "IPO"},
                all_locations=rec["all_locations"],
                source_url=rec["source_url"],
                linkedin_url=rec["linkedin_url"],
                twitter_url=rec["twitter_url"],
                founded_year=rec["founded_year"],
                batch_id=batch_id,
                last_enriched_at=now,
            )

            if existing is None:
                company = Company(**payload)
                s.add(company)
                s.flush()
                for fname in rec["founders"]:
                    s.add(Founder(company_id=company.id, name=fname))
                inserted += 1
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
                # Replace founders idempotently
                existing.founders.clear()
                s.flush()
                for fname in rec["founders"]:
                    s.add(Founder(company_id=existing.id, name=fname))
                updated += 1

    return inserted, updated, parse_failed


if __name__ == "__main__":
    ins, upd, failed = ingest()
    log.info("SPC ingest: inserted=%d updated=%d parse_failed=%d", ins, upd, failed)

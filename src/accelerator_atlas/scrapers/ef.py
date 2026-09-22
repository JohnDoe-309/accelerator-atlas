"""Entrepreneur First (EF) ingestion.

EF's portfolio page is JS-rendered but it uses a public WP admin-ajax endpoint
(`loadmore` action) that returns tile HTML. We dump all pages to
.firecrawl/ef/page-NN.html (plus the featured tiles from the main portfolio
page) and parse each tile out of the HTML.

Data available per tile:
    - slug, display name
    - location (single tag)
    - industry tags (may be multiple)
    - one-liner description
    - founders w/ role + LinkedIn URL
    - founded year

Stage / status / website are NOT exposed by EF; those will be filled by the
enrichment phase. All EF companies start as `Active`, `founded_year`-based
pseudo-batches named `EF-{year}`.
"""

from __future__ import annotations

import json
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
    Batch,
    Company,
    CompanyStatus,
    Founder,
)
from accelerator_atlas.storage.db import session_scope

log = logging.getLogger("scrapers.ef")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

EF_DIR = pathlib.Path(".firecrawl/ef")
AJAX_URL = "https://www.joinef.com/wp-admin/admin-ajax.php"
PORTFOLIO_URL = "https://www.joinef.com/portfolio/"

# `post__not_in` excludes the featured tiles from the loadmore action. We reuse
# the same list the live site uses so our pagination matches.
EXCLUDED_IDS = [
    12720, 12721, 12722, 12723, 12724, 12725, 12727, 12728, 12729, 12730,
    12731, 12732, 12733, 12734, 12735, 12736, 12737, 12738, 12739, 12740,
    12741, 12742, 12743, 13192,
]


def fetch_all(out_dir: pathlib.Path = EF_DIR, max_pages: int = 40, sleep: float = 0.4) -> int:
    """Pull every page of the EF portfolio to disk. Returns total unique slug count."""
    out_dir.mkdir(parents=True, exist_ok=True)

    posts_query = {
        "post_type": "company",
        "paged": 1,
        "post_status": "publish",
        "orderby": "menu_order",
        "order": "ASC",
        "posts_per_page": 24,
        "post__not_in": EXCLUDED_IDS,
    }

    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        form = urllib.parse.urlencode({
            "action": "loadmore",
            "query": json.dumps(posts_query),
            "page": page,
            "format": "default",
        }).encode()
        req = urllib.request.Request(
            AJAX_URL, data=form, method="POST",
            headers={
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        body = urllib.request.urlopen(req, timeout=30).read().decode()
        slugs = set(re.findall(r'data-companyslug="([^"]+)"', body))
        if not slugs:
            log.info("stop at page=%d (empty)", page)
            break
        new = slugs - seen
        log.info("page=%d total=%d new=%d", page, len(slugs), len(new))
        seen |= slugs
        (out_dir / f"page-{page:02d}.html").write_text(body)
        time.sleep(sleep)

    # Featured tiles live on the main portfolio page, excluded from loadmore.
    req = urllib.request.Request(PORTFOLIO_URL, headers={"User-Agent": "Mozilla/5.0"})
    body = urllib.request.urlopen(req, timeout=30).read().decode()
    featured_slugs = set(re.findall(r'data-companyslug="([^"]+)"', body))
    log.info("featured tiles on main page: %d (new: %d)", len(featured_slugs), len(featured_slugs - seen))
    seen |= featured_slugs
    (out_dir / "portfolio-featured.html").write_text(body)
    (out_dir / "slugs.txt").write_text("\n".join(sorted(seen)))
    return len(seen)


def _tag_text(tag) -> str:
    return re.sub(r"\s+", " ", tag.text(strip=True)) if tag else ""


def _parse_tile(tile) -> dict | None:
    link = tile.css_first("div.tile__link")
    if not link:
        return None
    slug = link.attributes.get("data-companyslug")
    name = link.attributes.get("data-companyname")
    if not slug or not name:
        return None

    # Tags: location (single) + industries (1..N)
    location = None
    industries: list[str] = []
    for a in tile.css("div.tile__tags a"):
        cls = a.attributes.get("class", "") or ""
        text = _tag_text(a)
        if "locationtag" in cls and not location:
            location = text
        elif "categorytag" in cls:
            industries.append(text)

    desc_el = tile.css_first("div.tile__description")
    description = _tag_text(desc_el) if desc_el else None

    founders: list[dict] = []
    founded_year: int | None = None
    for row in tile.css("div.tile__meta .meta__row"):
        # Two possible row shapes: role/founder or "Founded" / year.
        role_el = row.css_first(".meta__row__role")
        founder_el = row.css_first(".meta__row__founder")
        if role_el and founder_el:
            role = _tag_text(role_el)
            a = founder_el.css_first("a")
            fname = _tag_text(a) if a else _tag_text(founder_el)
            linkedin = a.attributes.get("href") if a else None
            if fname:
                founders.append({"name": fname, "role": role, "linkedin": linkedin})
            continue

        name_cells = row.css(".meta__row__name")
        if len(name_cells) == 2 and _tag_text(name_cells[0]).lower() == "founded":
            txt = _tag_text(name_cells[1])
            m = re.search(r"(19|20)\d{2}", txt)
            if m:
                founded_year = int(m.group(0))

    return {
        "slug": slug,
        "name": name,
        "description": description,
        "location": location,
        "industry_primary": industries[0] if industries else None,
        "industries": industries or None,
        "founders": founders,
        "founded_year": founded_year,
        "source_url": f"https://www.joinef.com/companies/{slug}/",
    }


def parse_dir(src: pathlib.Path = EF_DIR) -> list[dict]:
    files = sorted([*src.glob("page-*.html"), src / "portfolio-featured.html"])
    records: dict[str, dict] = {}
    for fp in files:
        if not fp.exists():
            continue
        tree = HTMLParser(fp.read_text())
        for tile in tree.css("div.tile.tile--company"):
            rec = _parse_tile(tile)
            if rec:
                # Prefer richer records if a slug appears twice.
                existing = records.get(rec["slug"])
                if existing is None or (rec["founded_year"] and not existing["founded_year"]):
                    records[rec["slug"]] = rec
    return list(records.values())


def _ensure_batch(session, accel_id: int, year: int | None) -> int | None:
    if year is None:
        return None
    slug = f"ef-{year}"
    existing = session.execute(
        select(Batch).where(Batch.accelerator_id == accel_id, Batch.slug == slug)
    ).scalar_one_or_none()
    if existing:
        return existing.id
    b = Batch(
        accelerator_id=accel_id,
        slug=slug,
        name=f"EF-{year}",
        season=None,
        year=year,
        company_count=None,
        notes="Pseudo-batch derived from company founded year (EF cohorts aren't published on the portfolio page).",
    )
    session.add(b)
    session.flush()
    return b.id


def ingest() -> tuple[int, int, int]:
    records = parse_dir()
    if not records:
        raise FileNotFoundError(
            f"No EF tiles parsed from {EF_DIR}. Run fetch_all() first (make scrape-ef)."
        )

    inserted = updated = skipped = 0
    now = datetime.now(UTC).replace(tzinfo=None)

    with session_scope() as s:
        accel = s.execute(
            select(Accelerator).where(Accelerator.slug == AcceleratorSlug.EF.value)
        ).scalar_one()
        accel_id = accel.id

        for rec in records:
            if not rec["name"]:
                skipped += 1
                continue

            batch_id = _ensure_batch(s, accel_id, rec["founded_year"])
            existing = s.execute(
                select(Company).where(
                    Company.accelerator_id == accel_id, Company.slug == rec["slug"]
                )
            ).scalar_one_or_none()

            payload = dict(
                accelerator_id=accel_id,
                slug=rec["slug"],
                name=rec["name"],
                one_liner=rec["description"],
                long_description=None,
                status=CompanyStatus.ACTIVE.value,
                status_source="ef.portfolio_tile",
                status_confidence=0.6,
                status_fetched_at=now,
                industry_primary=rec["industry_primary"],
                industries=rec["industries"],
                all_locations=rec["location"],
                country=None,
                source_url=rec["source_url"],
                founded_year=rec["founded_year"],
                batch_id=batch_id,
                last_enriched_at=now,
                is_top_company=False,
                is_b2b=False,
            )

            if existing is None:
                company = Company(**payload)
                s.add(company)
                s.flush()
                for f in rec["founders"]:
                    s.add(Founder(
                        company_id=company.id,
                        name=f["name"],
                        role=f.get("role"),
                        linkedin_url=f.get("linkedin"),
                        source="ef.portfolio_tile",
                        confidence=0.9,
                    ))
                inserted += 1
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
                existing.founders.clear()
                s.flush()
                for f in rec["founders"]:
                    s.add(Founder(
                        company_id=existing.id,
                        name=f["name"],
                        role=f.get("role"),
                        linkedin_url=f.get("linkedin"),
                        source="ef.portfolio_tile",
                        confidence=0.9,
                    ))
                updated += 1

    return inserted, updated, skipped


if __name__ == "__main__":
    import sys
    if "--fetch" in sys.argv:
        count = fetch_all()
        log.info("EF fetch_all done: %d unique slugs on disk", count)
    ins, upd, sk = ingest()
    log.info("EF ingest: inserted=%d updated=%d skipped=%d", ins, upd, sk)

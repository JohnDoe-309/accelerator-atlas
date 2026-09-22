"""a16z Speedrun ingestion via the public REST API.

Source: https://speedrun-be.a16z.com/api/companies/companies/?limit=300
Discovered by inspecting the page HTML (no auth required, returns full payload).
This bypasses the JS-driven cohort filter and gives us all 240 companies in one shot.

Run:
    uv run python -m accelerator_atlas.scrapers.speedrun
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from tenacity import retry, stop_after_attempt, wait_exponential

from accelerator_atlas.schema.models import (
    Accelerator,
    AcceleratorSlug,
    Batch,
    Company,
    CompanyStatus,
    Founder,
)
from accelerator_atlas.storage.db import session_scope

log = logging.getLogger("scrapers.speedrun")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

API = "https://speedrun-be.a16z.com/api/companies/companies/"
RAW_PATH = Path(".firecrawl/speedrun/all.json")
COHORT_ORDER = ["SR001", "SR002", "SR003", "SR004", "SR005", "SR006"]
# Indicative start dates per Speedrun blog history (each cohort runs ~12 weeks).
COHORT_YEAR = {
    "SR001": 2023,
    "SR002": 2023,
    "SR003": 2024,
    "SR004": 2024,
    "SR005": 2025,
    "SR006": 2026,
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_all() -> list[dict]:
    with httpx.Client(timeout=30) as c:
        r = c.get(API, params={"limit": 500})
        r.raise_for_status()
        data = r.json()
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(data, indent=2))
    log.info("fetched %d Speedrun companies (count=%d)", len(data["results"]), data["count"])
    return data["results"]


def _ensure_batch(session, accel_id: int, cohort: str) -> int | None:
    if not cohort:
        return None
    slug = cohort.lower()
    existing = session.execute(
        select(Batch).where(Batch.accelerator_id == accel_id, Batch.slug == slug)
    ).scalar_one_or_none()
    if existing:
        return existing.id
    b = Batch(
        accelerator_id=accel_id,
        slug=slug,
        name=cohort,
        season=None,
        year=COHORT_YEAR.get(cohort),
        company_count=None,
        notes="a16z Speedrun cohort.",
    )
    session.add(b)
    session.flush()
    return b.id


def _location(rec: dict) -> str | None:
    parts = [rec.get(k) for k in ("city", "state", "country") if rec.get(k)]
    return ", ".join(parts) if parts else None


def ingest(records: list[dict] | None = None) -> tuple[int, int, int]:
    if records is None:
        records = fetch_all() if not RAW_PATH.exists() else json.loads(RAW_PATH.read_text())["results"]

    inserted = updated = skipped = 0
    now = datetime.now(UTC).replace(tzinfo=None)

    with session_scope() as s:
        accel = s.execute(
            select(Accelerator).where(Accelerator.slug == AcceleratorSlug.SPEEDRUN.value)
        ).scalar_one()
        accel_id = accel.id

        for rec in records:
            slug = rec.get("slug") or rec.get("id")
            if not slug:
                skipped += 1
                continue

            batch_id = _ensure_batch(s, accel_id, rec.get("cohort"))
            industries = rec.get("industries") or []
            primary = industries[0] if industries else None

            payload = dict(
                accelerator_id=accel_id,
                source_id=rec.get("id"),
                slug=slug,
                name=rec.get("name"),
                website=rec.get("website_url") or None,
                one_liner=rec.get("preamble") or None,
                long_description=rec.get("description") or None,
                logo_url=rec.get("logo") or None,
                status=CompanyStatus.ACTIVE.value,
                status_source="speedrun.api",
                status_confidence=0.7,
                status_fetched_at=now,
                industry_primary=primary,
                industry_sub=industries[1] if len(industries) > 1 else None,
                industries=industries or None,
                tags=industries or None,
                is_b2b=any("b2b" in (i or "").lower() for i in industries),
                is_ai=any("ai" in (i or "").lower() for i in industries),
                is_top_company=False,
                all_locations=_location(rec),
                country=rec.get("country") or None,
                team_size_current=rec.get("team_size") or None,
                team_size_source="speedrun.api",
                team_size_confidence=0.85,
                team_size_fetched_at=now,
                linkedin_url=rec.get("linkedin_url") or None,
                twitter_url=rec.get("x_url") or None,
                source_url=f"https://speedrun.a16z.com/companies/{slug}",
                founded_year=rec.get("founded_year") or None,
                batch_id=batch_id,
                raw_payload=rec,
                last_enriched_at=now,
            )

            existing = s.execute(
                select(Company).where(
                    Company.accelerator_id == accel_id, Company.slug == slug
                )
            ).scalar_one_or_none()

            if existing is None:
                co = Company(**payload)
                s.add(co)
                s.flush()
                for f in rec.get("founder_set") or []:
                    name = " ".join(filter(None, (f.get("first_name"), f.get("last_name"))))
                    if not name:
                        continue
                    s.add(
                        Founder(
                            company_id=co.id,
                            name=name,
                            role=f.get("title"),
                            linkedin_url=f.get("linkedin_url") or None,
                            image_url=f.get("profile_pic") or None,
                        )
                    )
                inserted += 1
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
                existing.founders.clear()
                s.flush()
                for f in rec.get("founder_set") or []:
                    name = " ".join(filter(None, (f.get("first_name"), f.get("last_name"))))
                    if not name:
                        continue
                    s.add(
                        Founder(
                            company_id=existing.id,
                            name=name,
                            role=f.get("title"),
                            linkedin_url=f.get("linkedin_url") or None,
                            image_url=f.get("profile_pic") or None,
                        )
                    )
                updated += 1

        # Update batch.company_count from the data we just ingested
        for b in s.execute(
            select(Batch).where(Batch.accelerator_id == accel_id)
        ).scalars():
            b.company_count = sum(1 for r in records if r.get("cohort") == b.name)

    return inserted, updated, skipped


if __name__ == "__main__":
    ins, upd, skp = ingest()
    log.info("Speedrun ingest: inserted=%d updated=%d skipped=%d", ins, upd, skp)

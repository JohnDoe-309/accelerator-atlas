"""YC ingestion via yc-oss/api.

Zero scraping: yc-oss/api exposes daily-updated static JSON from
https://yc-oss.github.io/api. We pull:
  1. meta.json  -> batch catalog + company counts
  2. companies/all.json -> all 5,690 companies in one file

Idempotent: rerunning updates existing rows, creates new batches as they appear.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from tenacity import retry, stop_after_attempt, wait_exponential

from accelerator_atlas.schema.accelerators_seed import ACCELERATOR_BY_SLUG
from accelerator_atlas.schema.models import (
    Accelerator,
    Batch,
    Company,
    CompanyStatus,
)
from accelerator_atlas.storage.db import session_scope

logger = logging.getLogger(__name__)

YC_API_BASE = "https://yc-oss.github.io/api"
RAW_DIR = Path("data/raw/yc")


# yc-oss status -> canonical status
YC_STATUS_MAP = {
    "Active": CompanyStatus.ACTIVE.value,
    "Acquired": CompanyStatus.ACQUIRED.value,
    "Public": CompanyStatus.PUBLIC.value,
    "Inactive": CompanyStatus.DEAD.value,
}


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
def _get(url: str) -> dict | list:
    logger.info("GET %s", url)
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()


def _parse_batch_slug(batch_slug: str) -> tuple[str | None, int | None]:
    """'winter-2024' -> ('Winter', 2024). 'unspecified' -> (None, None)."""
    if batch_slug == "unspecified":
        return None, None
    parts = batch_slug.split("-")
    if len(parts) == 2:
        season, year_str = parts
        try:
            return season.capitalize(), int(year_str)
        except ValueError:
            pass
    return None, None


def upsert_accelerator_meta(slug: str) -> int:
    """Ensure the accelerator row exists; return its id."""
    seed = ACCELERATOR_BY_SLUG[slug]
    with session_scope() as s:
        existing = s.scalar(select(Accelerator).where(Accelerator.slug == slug))
        if existing is None:
            row = Accelerator(**seed)
            s.add(row)
            s.flush()
            accel_id = row.id
            logger.info("Created accelerator %s (id=%s)", slug, accel_id)
        else:
            for k, v in seed.items():
                setattr(existing, k, v)
            s.flush()
            accel_id = existing.id
            logger.info("Updated accelerator %s (id=%s)", slug, accel_id)
    return accel_id


def fetch_meta() -> dict:
    """Fetch and cache yc-oss meta.json."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    meta = _get(f"{YC_API_BASE}/meta.json")
    (RAW_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def fetch_all_companies() -> list[dict]:
    """Fetch and cache yc-oss companies/all.json."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    companies = _get(f"{YC_API_BASE}/companies/all.json")
    (RAW_DIR / "companies_all.json").write_text(json.dumps(companies))
    logger.info("Cached %d YC companies", len(companies))
    return companies


def ingest_batches(accel_id: int, meta: dict) -> dict[str, int]:
    """Upsert batches from meta['batches']. Returns {batch_name: batch_id}."""
    name_to_id: dict[str, int] = {}
    with session_scope() as s:
        for slug, info in meta["batches"].items():
            season, year = _parse_batch_slug(slug)
            existing = s.scalar(
                select(Batch).where(Batch.accelerator_id == accel_id, Batch.slug == slug)
            )
            payload = {
                "accelerator_id": accel_id,
                "slug": slug,
                "name": info["name"],
                "season": season,
                "year": year,
                "company_count": info.get("count"),
                "api_url": info.get("api"),
            }
            if existing is None:
                row = Batch(**payload)
                s.add(row)
                s.flush()
                name_to_id[info["name"]] = row.id
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
                s.flush()
                name_to_id[info["name"]] = existing.id
    logger.info("Upserted %d YC batches", len(name_to_id))
    return name_to_id


def _ts_to_datetime(ts: int | None) -> datetime | None:
    if ts is None or ts == 0:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=UTC).replace(tzinfo=None)
    except (OSError, ValueError, OverflowError):
        return None


def ingest_companies(
    accel_id: int, companies: list[dict], batch_name_to_id: dict[str, int]
) -> tuple[int, int]:
    """Upsert all YC companies. Returns (inserted, updated)."""
    inserted = 0
    updated = 0
    now = datetime.now(UTC).replace(tzinfo=None)

    with session_scope() as s:
        for i, c in enumerate(companies):
            slug = c.get("slug") or str(c.get("id"))
            if not slug:
                continue

            status_raw = c.get("status", "Active")
            status = YC_STATUS_MAP.get(status_raw, CompanyStatus.UNKNOWN.value)

            industries = c.get("industries") or []
            batch_id = batch_name_to_id.get(c.get("batch") or "")

            # cheap is_ai heuristic on tags + description
            tags = c.get("tags") or []
            descr = (c.get("long_description") or "") + " " + (c.get("one_liner") or "")
            is_ai = bool(
                "ai" in [t.lower() for t in tags]
                or "artificial-intelligence" in tags
                or "generative-ai" in tags
                or "machine-learning" in tags
                or " ai " in descr.lower()
            )
            industries_lower = [x.lower() for x in industries]
            is_b2b = "b2b" in industries_lower or any(
                t.lower() == "b2b" for t in tags
            )

            payload = {
                "accelerator_id": accel_id,
                "batch_id": batch_id,
                "source_id": str(c.get("id")) if c.get("id") is not None else None,
                "slug": slug,
                "name": c.get("name") or slug,
                "former_names": c.get("former_names") or None,
                "website": c.get("website"),
                "one_liner": c.get("one_liner"),
                "long_description": c.get("long_description"),
                "logo_url": c.get("small_logo_thumb_url"),
                "status": status,
                "status_source": "yc_oss_api",
                "status_confidence": 1.0,
                "status_fetched_at": now,
                "industry_primary": c.get("industry"),
                "industry_sub": c.get("subindustry"),
                "industries": industries or None,
                "tags": tags or None,
                "stage": c.get("stage"),
                "is_ai": is_ai,
                "is_b2b": is_b2b,
                "is_nonprofit": bool(c.get("nonprofit")),
                "is_hiring": bool(c.get("isHiring")),
                "is_top_company": bool(c.get("top_company")),
                "all_locations": c.get("all_locations"),
                "regions": c.get("regions") or None,
                "team_size_current": c.get("team_size"),
                "team_size_source": "yc_oss_api",
                "team_size_confidence": 0.9,
                "team_size_fetched_at": now,
                "source_url": c.get("url"),
                "launched_at": _ts_to_datetime(c.get("launched_at")),
                "data_sources": ["yc_oss_api"],
                "raw_payload": c,
                "last_enriched_at": now,
            }

            existing = s.scalar(
                select(Company).where(
                    Company.accelerator_id == accel_id, Company.slug == slug
                )
            )
            if existing is None:
                s.add(Company(**payload))
                inserted += 1
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
                updated += 1

            if (i + 1) % 500 == 0:
                s.flush()
                logger.info("  processed %d/%d", i + 1, len(companies))

    logger.info("YC companies: %d inserted, %d updated", inserted, updated)
    return inserted, updated


def ingest_all() -> None:
    """Full YC ingest: accelerator meta -> batches -> companies."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    accel_id = upsert_accelerator_meta("yc")
    meta = fetch_meta()
    batch_ids = ingest_batches(accel_id, meta)
    companies = fetch_all_companies()
    ingest_companies(accel_id, companies, batch_ids)

    logger.info("YC ingest complete.")


if __name__ == "__main__":
    ingest_all()

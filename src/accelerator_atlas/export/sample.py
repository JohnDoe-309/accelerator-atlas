"""Export a small, founder-free public sample for the static web demo.

Writes to `web/public/sample/` (committed; the web app reads it at build time):

    companies.json  ~300 companies: 75 per accelerator, drawn from its 4 most
                    recent batches (proportional to batch size). Company-level
                    public fields only, plus a founder *count*.
    summary.json    aggregate stats over the FULL dataset (totals per
                    accelerator, industries, founded-year trend) plus a
                    `sample` block describing this export.
    batches.json    per-batch aggregate counts (full dataset).
    coverage.json   per-field coverage percentages (full dataset).
    insights.json   Grok cohort narratives + spend ledger (aggregate text).
    founders.json   always [] -- no founder-level data is exported.

Deterministic: companies are picked in sha256(seed:accelerator:slug) order and
`generated_at` is the DB's latest `companies.updated_at`, not wall-clock time,
so reruns against the same DB produce identical files. The run aborts if any
founder name, founder URL or email address ends up in the output.

    uv run python -m accelerator_atlas.export.sample
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path

from accelerator_atlas.export import to_json as full_export

log = logging.getLogger("export.sample")

DB_PATH = full_export.DB_PATH
OUT_DIR = Path("web/public/sample")

SEED = "accelerator-atlas-sample-v1"
PER_ACCELERATOR = 75
RECENT_BATCHES = 4
SEASON_RANK = {"Winter": 1, "Spring": 2, "Summer": 3, "Fall": 4}
SOCIAL_HOSTS = re.compile(r"linkedin\.com|twitter\.com|//(www\.)?x\.com", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Every key the web app's `Company` type expects. Only the first block is
# populated; the rest stay null so the UI contract holds without shipping
# enrichment, traction or founder data.
PUBLIC_FIELDS = [
    "id", "accelerator", "slug", "name", "one_liner", "website",
    "industry_primary", "industry", "all_locations", "country",
    "status", "founded_year",
    "batch_slug", "batch_name", "batch_year", "batch_season",
]
NULL_FIELDS = [
    "linkedin_url", "twitter_url", "source_url", "status_source",
    "status_confidence", "stage", "funding_tier", "is_top_company", "is_b2b",
    "is_hiring", "team_size_current", "total_funding_usd",
    "total_funding_source", "total_funding_confidence", "last_round_type",
    "traction_arr_usd", "traction_mrr_usd", "traction_users",
    "traction_customers", "traction_gmv_usd", "traction_growth_rate",
    "traction_source", "traction_confidence", "traction_snippet",
]


def allocate(total: int, sizes: list[int]) -> list[int]:
    """Split `total` across strata proportionally to `sizes` (largest remainder)."""
    pool = sum(sizes)
    if pool <= total:
        return list(sizes)
    raw = [total * s / pool for s in sizes]
    alloc = [int(x) for x in raw]
    by_remainder = sorted(range(len(sizes)), key=lambda i: (alloc[i] - raw[i], i))
    for i in by_remainder[: total - sum(alloc)]:
        alloc[i] += 1
    return alloc


def _pick_order(accelerator: str, slug: str) -> str:
    return hashlib.sha256(f"{SEED}:{accelerator}:{slug}".encode()).hexdigest()


def recent_batches(c: sqlite3.Connection, accelerator_id: int) -> list[sqlite3.Row]:
    rows = c.execute("""
        SELECT b.id, b.slug, b.year, b.season, COUNT(co.id) AS n
        FROM batches b JOIN companies co ON co.batch_id = b.id
        WHERE b.accelerator_id = ?
        GROUP BY b.id
    """, (accelerator_id,)).fetchall()
    rows.sort(key=lambda r: (r["year"] or 0, SEASON_RANK.get(r["season"], 0), r["slug"]), reverse=True)
    return rows[:RECENT_BATCHES]


def sample_companies(c: sqlite3.Connection) -> tuple[list[dict], dict]:
    founder_counts = dict(c.execute("SELECT company_id, COUNT(*) FROM founders GROUP BY company_id"))
    picked: list[dict] = []
    plan: dict[str, dict[str, int]] = {}
    for acc in c.execute("SELECT id, slug FROM accelerators ORDER BY id").fetchall():
        batches = recent_batches(c, acc["id"])
        quotas = allocate(PER_ACCELERATOR, [b["n"] for b in batches])
        plan[acc["slug"]] = {b["slug"]: q for b, q in zip(batches, quotas)}
        for batch, quota in zip(batches, quotas):
            rows = c.execute("""
                SELECT c.id, ? AS accelerator, c.slug, c.name, c.one_liner, c.website,
                       c.industry_primary,
                       COALESCE(json_extract(c.tags_normalized,'$[0]'), c.industry_primary, 'Unknown') AS industry,
                       c.all_locations, c.country, c.status, c.founded_year,
                       b.slug AS batch_slug, b.name AS batch_name,
                       b.year AS batch_year, b.season AS batch_season
                FROM companies c JOIN batches b ON c.batch_id = b.id
                WHERE b.id = ?
            """, (acc["slug"], batch["id"])).fetchall()
            rows.sort(key=lambda r: (_pick_order(acc["slug"], r["slug"]), r["id"]))
            for r in rows[:quota]:
                company = {k: r[k] for k in PUBLIC_FIELDS}
                if company["website"] and SOCIAL_HOSTS.search(company["website"]):
                    company["website"] = None  # a personal profile, not a company site
                company.update(dict.fromkeys(NULL_FIELDS))
                company["founders"] = []
                company["founder_count"] = founder_counts.get(r["id"], 0)
                company["has_serial_founder"] = False
                picked.append(company)
    picked.sort(key=lambda d: (-(d["founded_year"] or 0), d["name"], d["id"]))
    return picked, plan


def assert_no_founder_data(c: sqlite3.Connection, out_dir: Path) -> None:
    """Fail loudly if any founder name, founder URL or email reached the output."""
    needles: set[str] = set()
    for name, linkedin, twitter, image in c.execute(
        "SELECT name, linkedin_url, twitter_url, image_url FROM founders"
    ):
        needles.update(u for u in (linkedin, twitter, image) if u)
        if name and " " in name.strip() and len(name.strip()) >= 6:
            needles.add(name.strip())
    for path in sorted(out_dir.glob("*.json")):
        text = path.read_text()
        leaks = sorted(n for n in needles if n in text)
        emails = EMAIL.findall(text)
        if leaks or emails:
            raise RuntimeError(f"{path}: {len(leaks)} founder values, {len(emails)} emails in public sample")
    log.info("privacy check passed: %d founder values, 0 emails in %s", len(needles), out_dir)


def run() -> None:
    full_export.OUT_DIR = OUT_DIR  # reuse the full exporter's aggregate queries
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as c:
        c.row_factory = sqlite3.Row
        snapshot = c.execute("SELECT MAX(updated_at) FROM companies").fetchone()[0]
        snapshot_iso = snapshot.replace(" ", "T").split(".")[0] + "+00:00"

        companies, plan = sample_companies(c)
        full_export._write("companies.json", companies)
        full_export.export_batches(c)
        full_export.export_coverage(c)
        full_export.export_insights(c)
        full_export.export_summary(c)

        summary_path = OUT_DIR / "summary.json"
        summary = json.loads(summary_path.read_text())
        summary["generated_at"] = snapshot_iso
        summary["sample"] = {
            "n_companies": len(companies),
            "n_companies_total": summary["totals"]["n_companies"],
            "seed": SEED,
            "per_accelerator": PER_ACCELERATOR,
            "batches": plan,
            "fields": PUBLIC_FIELDS + ["founder_count"],
        }
        full_export._write("summary.json", summary)
        full_export._write("founders.json", [])
        assert_no_founder_data(c, OUT_DIR)
    log.info("sample export complete: %d companies -> %s", len(companies), OUT_DIR.resolve())


if __name__ == "__main__":
    run()

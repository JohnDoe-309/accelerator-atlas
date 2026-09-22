"""Export SQLite snapshot to static JSON for the Next.js web app.

Writes to `web/public/data/`.

Run after any scraping/enrichment pass:

    uv run python -m accelerator_atlas.export.to_json
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from pathlib import Path

from accelerator_atlas.enrich.founders import find_serial_founders, normalize

log = logging.getLogger("export.to_json")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DB_PATH = "data/accelerators.db"
OUT_DIR = Path("web/public/data")


STAGE_TO_TIER = {
    "Pre-seed": "Pre-seed",
    "Pre-Seed": "Pre-seed",
    "Seed": "Seed",
    "Series A": "Series A",
    "Series B": "Series B+",
    "Series C": "Series B+",
    "Series D": "Series B+",
    "Series E": "Series B+",
    "Series F": "Series B+",
    "Growth": "Growth",
    "Unicorn": "Unicorn",
    "Early": "Early",
    "IPO": "Public",
    "Public": "Public",
    "Acquired": "Acquired",
}


def derive_funding_tier(stage: str | None, status: str | None) -> str | None:
    """Stage+status -> coarse tier label for charts/filters."""
    if status in {"Public", "Acquired"}:
        return status
    if not stage:
        return None
    return STAGE_TO_TIER.get(stage)


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def export_summary(c: sqlite3.Connection) -> None:
    accelerators = [dict(r) for r in c.execute("""
        SELECT a.id, a.slug, a.name, a.website, a.hq_location, a.founded_year,
               a.investment_amount_usd, a.investment_equity_pct,
               a.investment_terms_note, a.program_duration_weeks,
               a.batch_cadence, a.focus_areas, a.description,
               a.notable_alumni, a.total_companies_funded,
               (SELECT COUNT(*) FROM companies WHERE accelerator_id=a.id) AS company_count,
               (SELECT COUNT(*) FROM companies WHERE accelerator_id=a.id AND status='Active') AS active_count,
               (SELECT COUNT(*) FROM companies WHERE accelerator_id=a.id AND status='Acquired') AS acquired_count,
               (SELECT COUNT(*) FROM companies WHERE accelerator_id=a.id AND status='Public') AS public_count,
               (SELECT COUNT(*) FROM companies WHERE accelerator_id=a.id AND status='Dead') AS dead_count
        FROM accelerators a
        ORDER BY company_count DESC
    """)]
    totals = c.execute("""
        SELECT COUNT(*) AS n_companies,
               SUM(CASE WHEN status='Active' THEN 1 ELSE 0 END) AS n_active,
               SUM(CASE WHEN status='Acquired' THEN 1 ELSE 0 END) AS n_acquired,
               SUM(CASE WHEN status='Public' THEN 1 ELSE 0 END) AS n_public,
               SUM(CASE WHEN status='Dead' THEN 1 ELSE 0 END) AS n_dead,
               (SELECT COUNT(*) FROM founders) AS n_founders,
               (SELECT COUNT(*) FROM batches) AS n_batches
        FROM companies
    """).fetchone()
    industries = [dict(r) for r in c.execute("""
        SELECT COALESCE(json_extract(tags_normalized,'$[0]'), industry_primary, 'Unknown') AS industry,
               COUNT(*) AS n
        FROM companies
        GROUP BY industry
        ORDER BY n DESC
    """)]
    industry_year = [dict(r) for r in c.execute("""
        SELECT COALESCE(json_extract(tags_normalized,'$[0]'), industry_primary, 'Unknown') AS industry,
               founded_year, COUNT(*) AS n
        FROM companies
        WHERE founded_year BETWEEN 2010 AND 2025
        GROUP BY industry, founded_year
    """)]
    batch_trend = [dict(r) for r in c.execute("""
        SELECT a.slug, c.founded_year, COUNT(*) AS n
        FROM companies c JOIN accelerators a ON c.accelerator_id=a.id
        WHERE c.founded_year IS NOT NULL
        GROUP BY a.slug, c.founded_year
        ORDER BY c.founded_year DESC
    """)]
    # Funding tier distribution across all accelerators
    tier_dist = [dict(r) for r in c.execute("""
        SELECT a.slug, c.stage, c.status, COUNT(*) AS n
        FROM companies c JOIN accelerators a ON c.accelerator_id=a.id
        WHERE c.stage IS NOT NULL OR c.status IN ('Acquired','Public')
        GROUP BY a.slug, c.stage, c.status
    """)]
    # Funding mentions extracted from descriptions (high precision, low recall).
    funding_coverage = [dict(r) for r in c.execute("""
        SELECT a.slug,
               COUNT(*) FILTER (WHERE c.total_funding_usd IS NOT NULL) AS n_matched,
               COUNT(*) AS n_total,
               COALESCE(SUM(c.total_funding_usd), 0) AS sum_usd,
               COALESCE(AVG(c.total_funding_usd), 0) AS avg_usd
        FROM companies c JOIN accelerators a ON c.accelerator_id=a.id
        GROUP BY a.slug
    """)]
    summary = {
        "generated_at": _now_iso(),
        "totals": dict(totals),
        "accelerators": accelerators,
        "industries": industries,
        "industry_year": industry_year,
        "batch_trend": batch_trend,
        "funding_tier_raw": tier_dist,
        "funding_coverage": funding_coverage,
    }
    _write("summary.json", summary)


def export_companies(c: sqlite3.Connection, serial_keys: set[str]) -> None:
    rows = c.execute("""
        SELECT
            c.id, a.slug AS accelerator, c.slug, c.name, c.one_liner,
            c.website, c.linkedin_url, c.twitter_url, c.source_url,
            c.status, c.status_source, c.status_confidence,
            c.industry_primary,
            COALESCE(json_extract(c.tags_normalized,'$[0]'), c.industry_primary, 'Unknown') AS industry,
            c.stage, c.is_top_company, c.is_b2b, c.is_hiring,
            c.all_locations, c.country,
            c.team_size_current,
            c.total_funding_usd, c.total_funding_source,
            c.total_funding_confidence, c.last_round_type,
            c.traction_arr_usd, c.traction_mrr_usd, c.traction_users,
            c.traction_customers, c.traction_gmv_usd, c.traction_growth_rate,
            c.traction_source, c.traction_confidence, c.traction_snippet,
            c.founded_year, b.slug AS batch_slug, b.name AS batch_name,
            b.year AS batch_year, b.season AS batch_season
        FROM companies c
        JOIN accelerators a ON c.accelerator_id=a.id
        LEFT JOIN batches b ON c.batch_id=b.id
        ORDER BY c.founded_year DESC NULLS LAST, c.name ASC
    """).fetchall()

    # Founders per company + serial flags
    founders_by_co: dict[int, list] = {}
    founder_rows = c.execute("""
        SELECT company_id, name, role, linkedin_url
        FROM founders
    """).fetchall()
    serial_count_by_co: dict[int, int] = defaultdict(int)
    for r in founder_rows:
        serial = normalize(r["name"] or "") in serial_keys if r["name"] else False
        founders_by_co.setdefault(r["company_id"], []).append({
            "name": r["name"], "role": r["role"], "linkedin": r["linkedin_url"],
            "serial": serial,
        })
        if serial:
            serial_count_by_co[r["company_id"]] += 1

    companies = []
    for row in rows:
        d = dict(row)
        d["founders"] = founders_by_co.get(d["id"], [])
        d["founder_count"] = len(d["founders"])
        d["has_serial_founder"] = serial_count_by_co[d["id"]] > 0
        d["funding_tier"] = derive_funding_tier(d.get("stage"), d.get("status"))
        companies.append(d)
    _write("companies.json", companies)
    log.info("exported %d companies", len(companies))


def export_batches(c: sqlite3.Connection) -> None:
    rows = c.execute("""
        SELECT b.id, a.slug AS accelerator, b.slug, b.name,
               b.year, b.season, b.notes,
               (SELECT COUNT(*) FROM companies WHERE batch_id=b.id) AS company_count,
               (SELECT COUNT(*) FROM companies WHERE batch_id=b.id AND status='Active') AS active_count,
               (SELECT COUNT(*) FROM companies WHERE batch_id=b.id AND status='Acquired') AS acquired_count,
               (SELECT COUNT(*) FROM companies WHERE batch_id=b.id AND status='Public') AS public_count,
               (SELECT COUNT(*) FROM companies WHERE batch_id=b.id AND status='Dead') AS dead_count,
               (SELECT GROUP_CONCAT(DISTINCT c.industry_primary) FROM companies c WHERE c.batch_id=b.id) AS industries_csv
        FROM batches b
        JOIN accelerators a ON b.accelerator_id=a.id
        ORDER BY b.year DESC NULLS LAST, b.season DESC NULLS LAST
    """).fetchall()
    _write("batches.json", [dict(r) for r in rows])
    log.info("exported %d batches", len(rows))


def export_insights(c: sqlite3.Connection) -> None:
    insights = [dict(r) for r in c.execute("""
        SELECT id, kind, subject_type, subject_id, title, content, model, created_at
        FROM insights ORDER BY created_at DESC, id DESC
    """)]
    budget = c.execute("""
        SELECT COUNT(*) AS calls,
               COALESCE(SUM(usd_cost),0) AS spent_usd,
               COALESCE(SUM(prompt_tokens),0) AS prompt_tokens,
               COALESCE(SUM(completion_tokens),0) AS completion_tokens
        FROM grok_usage WHERE success=1
    """).fetchone()
    by_purpose = [dict(r) for r in c.execute("""
        SELECT purpose, COUNT(*) AS calls,
               SUM(usd_cost) AS spent_usd,
               SUM(prompt_tokens) AS prompt_tokens,
               SUM(completion_tokens) AS completion_tokens
        FROM grok_usage WHERE success=1
        GROUP BY purpose ORDER BY SUM(usd_cost) DESC
    """)]
    _write("insights.json", {
        "insights": insights,
        "budget": {
            "cap_usd": 50.0,
            "spent_usd": float(budget["spent_usd"]),
            "remaining_usd": 50.0 - float(budget["spent_usd"]),
            "calls": int(budget["calls"]),
            "prompt_tokens": int(budget["prompt_tokens"]),
            "completion_tokens": int(budget["completion_tokens"]),
            "by_purpose": by_purpose,
        },
    })


def export_coverage(c: sqlite3.Connection) -> None:
    fields = [
        ("website", "c.website"),
        ("one_liner", "c.one_liner"),
        ("long_description", "c.long_description"),
        ("industry_primary", "c.industry_primary"),
        ("founded_year", "c.founded_year"),
        ("team_size_current", "c.team_size_current"),
        ("linkedin_url", "c.linkedin_url"),
        ("stage", "c.stage"),
        ("status (labelled)", "CASE WHEN c.status IN ('Active','Dead','Acquired','Public') THEN 1 END"),
        ("all_locations", "c.all_locations"),
        ("founders (>=1)", "(SELECT COUNT(*) FROM founders f WHERE f.company_id=c.id)"),
    ]
    rows = []
    for name, expr in fields:
        q = f"""SELECT a.slug AS accelerator, COUNT(*) AS total,
                   SUM(CASE WHEN ({expr}) IS NOT NULL AND ({expr}) != 0 AND ({expr}) != '' THEN 1 ELSE 0 END) AS have
            FROM companies c JOIN accelerators a ON c.accelerator_id=a.id
            GROUP BY a.slug ORDER BY a.slug"""
        for r in c.execute(q):
            rows.append({
                "field": name, "accelerator": r["accelerator"],
                "total": r["total"], "have": r["have"],
                "pct": round(100.0 * r["have"] / r["total"], 1) if r["total"] else 0,
            })
    _write("coverage.json", rows)


def export_founders() -> None:
    serial = find_serial_founders()
    # Pack into a list sorted by number of companies touched, then by name
    rows = []
    for key, entries in serial.items():
        names = sorted({e["founder_name"] for e in entries})
        companies = [
            {
                "name": e["company_name"],
                "slug": e["company_slug"],
                "accelerator": e["accelerator"],
                "role": e["role"],
                "linkedin": e["linkedin"],
                "status": e["company_status"],
            }
            for e in entries
        ]
        # Distinct accelerators
        accs = sorted({c["accelerator"] for c in companies})
        rows.append({
            "key": key,
            "display_name": names[0],
            "aliases": names,
            "company_count": len(companies),
            "accelerator_count": len(accs),
            "accelerators": accs,
            "companies": companies,
        })
    rows.sort(key=lambda r: (-r["company_count"], -r["accelerator_count"], r["display_name"]))
    _write("founders.json", rows)
    log.info("exported %d serial founders", len(rows))


def _now_iso() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write(name: str, obj) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(json.dumps(obj, ensure_ascii=False, default=str, separators=(",", ":")))
    log.info("wrote %s (%d KB)", path, path.stat().st_size // 1024)


def run() -> None:
    serial = find_serial_founders()
    serial_keys = set(serial.keys())
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        export_summary(c)
        export_companies(c, serial_keys)
        export_batches(c)
        export_insights(c)
        export_coverage(c)
    export_founders()
    log.info("export complete -> %s", OUT_DIR.resolve())


if __name__ == "__main__":
    run()

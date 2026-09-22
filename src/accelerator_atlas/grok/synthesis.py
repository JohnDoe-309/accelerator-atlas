"""Grok-powered synthesis jobs over the accelerator database.

Three passes, all aggressively budget-conscious:

    1. normalize_industries(): Collapse raw YC/SPC/EF/Speedrun industry labels
       into a unified taxonomy (~15 categories) and persist the mapping to
       `companies.tags_normalized`.

    2. whitespace_report(): Compute pivot stats locally (industry x accelerator
       x year x outcome) and ask Grok to narrate the gaps.

    3. cohort_narratives(): Per-accelerator batch-year narratives of what
       worked and what didn't.

All outputs are persisted to the `insights` table and replayable via
`input_hash` + the on-disk cache in `.firecrawl/grok_cache/`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import func, select

from accelerator_atlas.grok.client import (
    DEFAULT_MODEL_FAST,
    DEFAULT_MODEL_REASON,
    chat,
    print_budget,
)
from accelerator_atlas.schema.models import Accelerator, Company, Insight
from accelerator_atlas.storage.db import session_scope

log = logging.getLogger("grok.synthesis")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DB_PATH = "data/accelerators.db"


# ---------------------------------------------------------------------------
# Pass 1: Industry normalization
# ---------------------------------------------------------------------------

NORMALIZED_TAXONOMY = [
    "AI & ML Infrastructure",
    "Developer Tools",
    "SaaS / Enterprise Software",
    "Consumer Software",
    "Fintech",
    "Healthtech / Biotech",
    "Climate & Energy",
    "Hardware & Robotics",
    "Industrial & Manufacturing",
    "Logistics & Supply Chain",
    "Education",
    "Government & Defense",
    "Media, Gaming & Creator Tools",
    "Marketplace & Commerce",
    "Security & Privacy",
    "Crypto & Web3",
    "Agtech & Food",
    "Real Estate & Construction",
    "Other",
]


def _collect_industry_labels() -> list[str]:
    """All distinct industry_primary strings across accelerators."""
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute(
            "SELECT DISTINCT industry_primary FROM companies "
            "WHERE industry_primary IS NOT NULL AND industry_primary != ''"
        ).fetchall()
    return sorted({r[0] for r in rows})


def normalize_industries() -> dict[str, str]:
    """Produce a mapping {raw_label -> normalized_category} via one Grok call.

    Idempotent: cached by input hash. Writes nothing back to the DB itself;
    use `apply_industry_map` to persist.
    """
    labels = _collect_industry_labels()
    log.info("found %d distinct industry labels", len(labels))

    prompt = (
        "You are classifying startup industries. Given the raw labels below "
        "(each from an accelerator's taxonomy), map each to EXACTLY ONE "
        "category from this fixed taxonomy:\n\n"
        + "\n".join(f"- {c}" for c in NORMALIZED_TAXONOMY)
        + "\n\nReturn a single JSON object whose keys are the raw labels and "
        "whose values are the normalized category. No commentary, no extra "
        "fields, no markdown.\n\nRaw labels:\n"
        + "\n".join(f"- {lab}" for lab in labels)
    )
    resp = chat(
        purpose="normalize_industries",
        messages=[
            {"role": "system", "content": "Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        model=DEFAULT_MODEL_FAST,
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=6000,
    )
    mapping = json.loads(resp.text)
    # Sanity-check: drop anything not in the taxonomy
    valid = {k: (v if v in NORMALIZED_TAXONOMY else "Other") for k, v in mapping.items()}
    log.info(
        "normalize_industries: %d labels mapped (%d calls, $%.4f, cached=%s)",
        len(valid), 1, resp.usd_cost, resp.cached,
    )
    return valid


def apply_industry_map(mapping: dict[str, str]) -> int:
    """Write the normalized category back into companies.tags_normalized (JSON).

    We reuse tags_normalized as the canonical unified taxonomy column and
    avoid schema migration. The raw label stays in industry_primary.
    """
    n = 0
    with sqlite3.connect(DB_PATH) as c:
        for raw, normalized in mapping.items():
            res = c.execute(
                "UPDATE companies SET tags_normalized = ? "
                "WHERE industry_primary = ?",
                (json.dumps([normalized]), raw),
            )
            n += res.rowcount
        c.commit()
    log.info("applied normalization to %d companies", n)
    return n


# ---------------------------------------------------------------------------
# Pass 2: White-space report
# ---------------------------------------------------------------------------


def _compute_industry_accelerator_pivot() -> dict:
    """Return a compact pivot: normalized_industry -> accelerator -> (total, active, dead, acquired, public)."""
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("""
            SELECT
                COALESCE(json_extract(c.tags_normalized, '$[0]'), c.industry_primary, 'Unknown') AS norm,
                a.slug AS accel,
                c.status AS st,
                COUNT(*) AS n
            FROM companies c
            JOIN accelerators a ON c.accelerator_id = a.id
            GROUP BY norm, accel, st
        """).fetchall()
    pivot: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for norm, accel, st, n in rows:
        pivot[norm][accel][st] = n
    compact = {}
    for norm, accels in pivot.items():
        compact[norm] = {}
        for accel, counts in accels.items():
            total = sum(counts.values())
            compact[norm][accel] = {
                "total": total,
                "active": counts.get("Active", 0),
                "dead": counts.get("Dead", 0),
                "acquired": counts.get("Acquired", 0),
                "public": counts.get("Public", 0),
            }
    return compact


def _compute_industry_year_trend() -> dict[str, dict[int, int]]:
    """normalized_industry -> founded_year -> company_count (last 10 years only)."""
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("""
            SELECT
                COALESCE(json_extract(c.tags_normalized, '$[0]'), c.industry_primary, 'Unknown') AS norm,
                c.founded_year,
                COUNT(*)
            FROM companies c
            WHERE c.founded_year BETWEEN 2015 AND 2025
            GROUP BY norm, c.founded_year
            ORDER BY norm, c.founded_year
        """).fetchall()
    out: dict[str, dict[int, int]] = defaultdict(dict)
    for norm, yr, n in rows:
        out[norm][yr] = n
    return out


def whitespace_report() -> int:
    """Run the Grok narrative over locally-computed pivots. Returns insight_id."""
    pivot = _compute_industry_accelerator_pivot()
    trend = _compute_industry_year_trend()

    # Serialize compactly to minimize tokens (the pivot alone is ~300 rows).
    payload = {
        "industry_x_accelerator": {
            k: v for k, v in pivot.items()
            if sum(acc["total"] for acc in v.values()) >= 10  # drop noise
        },
        "industry_year_trend_2015_2025": dict(trend),
    }
    payload_str = json.dumps(payload, separators=(",", ":"))

    system = (
        "You are a top-tier venture-capital analyst. You will receive a compact "
        "cross-accelerator dataset (4 accelerators: Y Combinator 'yc', "
        "Entrepreneur First 'ef', South Park Commons 'spc', a16z Speedrun "
        "'a16z_speedrun') showing company counts and outcome mix (Active/Dead/"
        "Acquired/Public) per normalized industry, plus yearly founding trends. "
        "Your job: produce a rigorous *white-space* analysis."
    )
    user = (
        "DATA (JSON):\n" + payload_str + "\n\n"
        "Produce a structured markdown report with EXACTLY these sections:\n\n"
        "## 1. Executive summary\n"
        "Three bullets on the most important cross-accelerator patterns.\n\n"
        "## 2. White spaces (under-funded categories)\n"
        "List 5-8 categories where at least one accelerator is clearly "
        "under-indexed relative to another. For each: the gap, the "
        "supporting numbers from the data, and why this might be a real "
        "opportunity vs. a deliberate pass. Be concrete.\n\n"
        "## 3. Outcome-mix outliers\n"
        "Which categories have unusually high acquired or dead rates, and "
        "at which accelerators? Cite rates.\n\n"
        "## 4. Declining vs. rising verticals (2015-2025)\n"
        "Use the yearly trend to identify 3 rising and 3 declining "
        "verticals. Cite years and counts.\n\n"
        "## 5. Thesis-level takeaways\n"
        "Three sentences on what this says about each accelerator's "
        "implicit strategy.\n\n"
        "Rules: Every numerical claim must cite a number from the data. "
        "No invented figures. Be direct; skip hedging."
    )
    resp = chat(
        purpose="whitespace_report",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=DEFAULT_MODEL_REASON,
        temperature=0.2,
        max_tokens=3500,
        max_usd_this_call=0.50,
    )
    log.info("whitespace_report: $%.4f tokens=%d reasoning=%d cached=%s",
             resp.usd_cost, resp.total_tokens, resp.reasoning_tokens, resp.cached)

    input_hash = hashlib.sha256(payload_str.encode()).hexdigest()
    with session_scope() as s:
        row = Insight(
            kind="whitespace_report",
            subject_type=None,
            subject_id=None,
            title="Cross-accelerator white-space analysis",
            content=resp.text,
            evidence=[{"type": "pivot_snapshot", "size_chars": len(payload_str)}],
            input_hash=input_hash,
            model=resp.model,
            usage_id=resp.usage_id,
        )
        s.add(row)
        s.flush()
        return row.id


# ---------------------------------------------------------------------------
# Pass 3: Per-accelerator cohort narratives
# ---------------------------------------------------------------------------


def _accelerator_cohort_stats(slug: str) -> dict:
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("""
            SELECT c.founded_year, c.status, COUNT(*) 
            FROM companies c JOIN accelerators a ON c.accelerator_id=a.id
            WHERE a.slug=? AND c.founded_year IS NOT NULL
            GROUP BY c.founded_year, c.status ORDER BY c.founded_year
        """, (slug,)).fetchall()
        tops = c.execute("""
            SELECT c.name, c.founded_year, c.status, c.industry_primary,
                   COALESCE(json_extract(c.tags_normalized,'$[0]'), c.industry_primary)
            FROM companies c JOIN accelerators a ON c.accelerator_id=a.id
            WHERE a.slug=? AND (c.is_top_company = 1 OR c.status IN ('Acquired','Public'))
            ORDER BY c.founded_year DESC NULLS LAST
            LIMIT 40
        """, (slug,)).fetchall()
    per_year: dict[int, Counter] = defaultdict(Counter)
    for y, st, n in rows:
        per_year[y][st] = n
    return {
        "per_year": {y: dict(counts) for y, counts in sorted(per_year.items())},
        "top_40_outcomes": [
            {"name": n, "founded_year": y, "status": s, "industry": ind, "normalized": norm}
            for n, y, s, ind, norm in tops
        ],
    }


def cohort_narratives(slugs: list[str] | None = None) -> list[int]:
    """One short narrative per accelerator. Cheap (grok-4-fast-non-reasoning)."""
    if slugs is None:
        slugs = ["yc", "ef", "spc", "a16z_speedrun"]
    insight_ids: list[int] = []
    for slug in slugs:
        stats = _accelerator_cohort_stats(slug)
        if not stats["per_year"]:
            log.warning("no cohort data for %s", slug)
            continue
        payload = json.dumps(stats, separators=(",", ":"))
        resp = chat(
            purpose=f"cohort_narrative:{slug}",
            messages=[
                {"role": "system", "content":
                    "You are a concise VC analyst. Output plain markdown, no preamble."},
                {"role": "user", "content":
                    f"Accelerator slug: {slug}\n\nDATA (JSON):\n{payload}\n\n"
                    "Write a tight 250-word narrative:\n"
                    "- Strongest cohort(s) by outcome mix (cite years + numbers)\n"
                    "- Two notable wins from the top_40_outcomes list\n"
                    "- Any multi-year trend worth calling out\n"
                    "- One-sentence bottom-line on their batting average.\n"
                    "Do not invent numbers. If data is sparse, say so."},
            ],
            model=DEFAULT_MODEL_FAST,
            temperature=0.2,
            max_tokens=800,
            max_usd_this_call=0.10,
        )
        input_hash = hashlib.sha256(payload.encode()).hexdigest()
        with session_scope() as s:
            accel_id = s.execute(
                select(Accelerator.id).where(Accelerator.slug == slug)
            ).scalar_one()
            row = Insight(
                kind="cohort_narrative",
                subject_type="accelerator",
                subject_id=str(accel_id),
                title=f"{slug}: cohort narrative",
                content=resp.text,
                evidence=[{"type": "cohort_stats", "years": list(stats["per_year"].keys())}],
                input_hash=input_hash,
                model=resp.model,
                usage_id=resp.usage_id,
            )
            s.add(row)
            s.flush()
            insight_ids.append(row.id)
        log.info("cohort %s: $%.4f tokens=%d cached=%s",
                 slug, resp.usd_cost, resp.total_tokens, resp.cached)
    return insight_ids


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_all() -> dict:
    log.info("=== Pass 1: industry normalization ===")
    mapping = normalize_industries()
    applied = apply_industry_map(mapping)

    log.info("=== Pass 2: white-space report ===")
    wid = whitespace_report()

    log.info("=== Pass 3: cohort narratives ===")
    cids = cohort_narratives()

    print_budget()
    return {
        "industry_map_size": len(mapping),
        "companies_normalized": applied,
        "whitespace_insight_id": wid,
        "cohort_insight_ids": cids,
    }


if __name__ == "__main__":
    result = run_all()
    log.info("synthesis DONE: %s", result)

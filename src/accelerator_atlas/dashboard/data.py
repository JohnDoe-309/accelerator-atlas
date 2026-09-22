"""Shared data loaders for the Streamlit dashboard.

All queries cached with @st.cache_data; DB is read-only from the dashboard's view.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from accelerator_atlas.storage.db import DB_PATH


def _connect() -> sqlite3.Connection:
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run `make seed scrape-yc` first."
        )
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


@st.cache_data(ttl=3600)
def load_accelerators() -> pd.DataFrame:
    with _connect() as c:
        return pd.read_sql(
            "select id, slug, name, founded_year, hq_location, website, "
            "program_duration_weeks, investment_amount_usd, investment_equity_pct, "
            "batch_cadence, total_companies_funded, description "
            "from accelerators order by id",
            c,
        )


@st.cache_data(ttl=3600)
def load_batches() -> pd.DataFrame:
    with _connect() as c:
        return pd.read_sql(
            """
            select b.id, b.slug, b.name, b.season, b.year, b.company_count,
                   a.slug as accelerator, a.name as accelerator_name
            from batches b
            join accelerators a on a.id = b.accelerator_id
            order by b.year, b.season
            """,
            c,
        )


@st.cache_data(ttl=3600)
def load_companies() -> pd.DataFrame:
    """Master company frame with accelerator + batch joined."""
    with _connect() as c:
        df = pd.read_sql(
            """
            select
              c.id, c.slug, c.name, c.website, c.one_liner, c.long_description,
              c.logo_url, c.status, c.industry_primary, c.industry_sub,
              c.stage, c.is_ai, c.is_b2b, c.is_nonprofit, c.is_hiring, c.is_top_company,
              c.all_locations, c.country, c.team_size_current, c.total_funding_usd,
              c.revenue_estimate_usd, c.launched_at, c.source_url, c.linkedin_url,
              c.crunchbase_url,
              a.slug as accelerator, a.name as accelerator_name,
              b.name as batch, b.year as batch_year, b.season as batch_season
            from companies c
            join accelerators a on a.id = c.accelerator_id
            left join batches b on b.id = c.batch_id
            """,
            c,
        )
    # Convert boolean-like ints to Python bools for cleaner UI
    for col in ("is_ai", "is_b2b", "is_nonprofit", "is_hiring", "is_top_company"):
        df[col] = df[col].fillna(0).astype(bool)
    return df


@st.cache_data(ttl=3600)
def coverage_by_field(accelerator_slug: str | None = None) -> pd.DataFrame:
    where = ""
    params: tuple = ()
    if accelerator_slug:
        where = "where a.slug = ?"
        params = (accelerator_slug,)
    sql = f"""
        select
          count(*) as total,
          sum(case when c.website is not null and c.website <> '' then 1 else 0 end) as website,
          sum(case when c.one_liner is not null and c.one_liner <> '' then 1 else 0 end) as one_liner,
          sum(case when c.industry_primary is not null then 1 else 0 end) as industry,
          sum(case when c.batch_id is not null then 1 else 0 end) as batch,
          sum(case when c.status is not null and c.status <> 'Unknown' then 1 else 0 end) as status,
          sum(case when c.team_size_current is not null then 1 else 0 end) as team_size,
          sum(case when c.total_funding_usd is not null then 1 else 0 end) as total_funding,
          sum(case when c.revenue_estimate_usd is not null then 1 else 0 end) as revenue,
          sum(case when c.linkedin_url is not null then 1 else 0 end) as linkedin_url,
          sum(case when c.crunchbase_url is not null then 1 else 0 end) as crunchbase_url
        from companies c
        join accelerators a on a.id = c.accelerator_id
        {where}
    """
    with _connect() as con:
        df = pd.read_sql(sql, con, params=params)
    total = df.loc[0, "total"] or 1
    rows = []
    for col in df.columns:
        if col == "total":
            continue
        filled = int(df.loc[0, col])
        rows.append(
            {
                "field": col,
                "filled": filled,
                "missing": int(total - filled),
                "coverage_pct": round(100 * filled / total, 1),
            }
        )
    return pd.DataFrame(rows).sort_values("coverage_pct", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=3600)
def status_counts(accelerator_slug: str | None = None) -> pd.DataFrame:
    where = "where a.slug = ?" if accelerator_slug else ""
    params: tuple = (accelerator_slug,) if accelerator_slug else ()
    with _connect() as c:
        return pd.read_sql(
            f"""
            select c.status, count(*) as n
            from companies c join accelerators a on a.id = c.accelerator_id
            {where}
            group by c.status order by n desc
            """,
            c,
            params=params,
        )


@st.cache_data(ttl=3600)
def industry_counts(accelerator_slug: str | None = None) -> pd.DataFrame:
    where = "where a.slug = ?" if accelerator_slug else ""
    params: tuple = (accelerator_slug,) if accelerator_slug else ()
    with _connect() as c:
        return pd.read_sql(
            f"""
            select coalesce(c.industry_primary, 'Unspecified') as industry, count(*) as n
            from companies c join accelerators a on a.id = c.accelerator_id
            {where}
            group by industry order by n desc
            """,
            c,
            params=params,
        )


@st.cache_data(ttl=3600)
def batch_trend(accelerator_slug: str | None = None) -> pd.DataFrame:
    where = "where a.slug = ?" if accelerator_slug else ""
    params: tuple = (accelerator_slug,) if accelerator_slug else ()
    with _connect() as c:
        return pd.read_sql(
            f"""
            select b.year, b.season, b.name as batch, b.company_count,
                   a.slug as accelerator
            from batches b join accelerators a on a.id = b.accelerator_id
            {where}
            order by b.year, b.season
            """,
            c,
            params=params,
        )


@st.cache_data(ttl=3600)
def survivorship_by_batch_year(accelerator_slug: str = "yc") -> pd.DataFrame:
    """% Active / Acquired / Public / Dead per batch year."""
    with _connect() as c:
        df = pd.read_sql(
            """
            select b.year, c.status, count(*) as n
            from companies c
            join accelerators a on a.id = c.accelerator_id
            join batches b on b.id = c.batch_id
            where a.slug = ? and b.year is not null
            group by b.year, c.status
            order by b.year
            """,
            c,
            params=(accelerator_slug,),
        )
    pivot = df.pivot(index="year", columns="status", values="n").fillna(0)
    totals = pivot.sum(axis=1)
    pct = pivot.div(totals, axis=0) * 100
    pct["total"] = totals
    return pct.reset_index()

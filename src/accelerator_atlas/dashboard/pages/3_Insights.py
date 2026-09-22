"""Insights page: Grok-generated narratives + the underlying pivot tables."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = "data/accelerators.db"

st.set_page_config(page_title="Insights | Accelerator Atlas", layout="wide")
st.title("Insights")
st.caption(
    "Grok-generated narratives over the full cross-accelerator dataset. "
    "Every numeric claim in the narratives is backed by a pivot computed "
    "locally from the DB — no external lookups. See the 'Evidence' tab "
    "below each insight for the underlying table."
)


@st.cache_data(ttl=300)
def load_insights() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as c:
        return pd.read_sql_query(
            "SELECT id, kind, subject_type, subject_id, title, content, model, created_at "
            "FROM insights ORDER BY kind, id",
            c,
        )


@st.cache_data(ttl=300)
def industry_outcome_pivot() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as c:
        return pd.read_sql_query("""
            SELECT
                COALESCE(json_extract(c.tags_normalized, '$[0]'), c.industry_primary, 'Unknown') AS industry,
                a.slug AS accelerator,
                c.status,
                COUNT(*) AS n
            FROM companies c JOIN accelerators a ON c.accelerator_id = a.id
            GROUP BY industry, accelerator, status
        """, c)


@st.cache_data(ttl=300)
def industry_year_trend() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as c:
        return pd.read_sql_query("""
            SELECT
                COALESCE(json_extract(c.tags_normalized, '$[0]'), c.industry_primary, 'Unknown') AS industry,
                c.founded_year,
                COUNT(*) AS n
            FROM companies c
            WHERE c.founded_year BETWEEN 2015 AND 2025
            GROUP BY industry, c.founded_year
        """, c)


@st.cache_data(ttl=300)
def grok_budget() -> dict:
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(usd_cost),0), COALESCE(SUM(prompt_tokens),0), "
            "COALESCE(SUM(completion_tokens),0) FROM grok_usage WHERE success=1"
        ).fetchone()
    return {"calls": row[0], "spent_usd": row[1], "prompt_tok": row[2], "completion_tok": row[3]}


ins = load_insights()
if ins.empty:
    st.warning("No insights yet. Run `make grok-batch` to generate them.")
    st.stop()

ws = ins[ins["kind"] == "whitespace_report"].tail(1)
cohorts = ins[ins["kind"] == "cohort_narrative"]

b = grok_budget()
CAP = 50.0
c1, c2, c3, c4 = st.columns(4)
c1.metric("Grok calls", b["calls"])
c2.metric("Spent (USD)", f"${b['spent_usd']:.4f}")
c3.metric("Remaining", f"${CAP - b['spent_usd']:.2f}", delta=f"of ${CAP:.0f} cap")
c4.metric("Total tokens", f"{b['prompt_tok'] + b['completion_tok']:,}")

tab_ws, tab_cohorts, tab_pivot = st.tabs([
    "White-space report", "Per-accelerator narratives", "Underlying pivot",
])

with tab_ws:
    if ws.empty:
        st.info("No white-space report yet.")
    else:
        r = ws.iloc[0]
        st.caption(f"Model: `{r['model']}` · Generated: {r['created_at']}")
        st.markdown(r["content"])

with tab_cohorts:
    if cohorts.empty:
        st.info("No cohort narratives yet.")
    else:
        acc_pick = st.selectbox(
            "Accelerator",
            options=sorted(cohorts["title"].tolist()),
            index=0,
        )
        r = cohorts[cohorts["title"] == acc_pick].iloc[0]
        st.caption(f"Model: `{r['model']}` · Generated: {r['created_at']}")
        st.markdown(r["content"])

with tab_pivot:
    st.subheader("Industry × Accelerator × Outcome")
    piv = industry_outcome_pivot()
    if not piv.empty:
        wide = piv.pivot_table(
            index=["industry", "accelerator"], columns="status", values="n", fill_value=0,
        ).reset_index()
        wide["total"] = wide[[c for c in wide.columns if c not in {"industry", "accelerator"}]].sum(axis=1)
        wide = wide.sort_values("total", ascending=False)
        st.dataframe(wide, use_container_width=True, height=420)

    st.subheader("Industry founding trend (2015–2025)")
    trend = industry_year_trend()
    if not trend.empty:
        top_ind = trend.groupby("industry")["n"].sum().nlargest(10).index.tolist()
        fig = px.line(
            trend[trend["industry"].isin(top_ind)],
            x="founded_year", y="n", color="industry",
            markers=True,
        )
        fig.update_layout(xaxis_title="Founded year", yaxis_title="Companies", height=500)
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption(
    f"All narratives are idempotent: rerunning `make grok-batch` with unchanged "
    f"data hits the on-disk cache (zero cost). "
    f"Budget ledger: `.firecrawl/grok_cache/` + `grok_usage` table."
)

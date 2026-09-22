"""Accelerator Atlas dashboard — Overview (home page).

Run:   uv run streamlit run src/accelerator_atlas/dashboard/app.py
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from accelerator_atlas.dashboard.data import (
    batch_trend,
    industry_counts,
    load_accelerators,
    load_companies,
    status_counts,
)

st.set_page_config(
    page_title="Accelerator Atlas",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Accelerator Atlas")
st.caption(
    "Unified analytical view of YC, SPC, a16z Speedrun, and EF. "
    "YC is primary — 5,690 companies across 48 batches."
)

accelerators = load_accelerators()
companies = load_companies()

# ---------- Sidebar controls ----------
with st.sidebar:
    st.header("Filters")
    accel_options = ["All"] + accelerators["slug"].tolist()
    accel_label_map = {"All": "All accelerators"}
    for _, r in accelerators.iterrows():
        accel_label_map[r["slug"]] = r["name"]
    accel = st.selectbox(
        "Accelerator",
        accel_options,
        format_func=lambda x: accel_label_map.get(x, x),
    )
    accel_slug = None if accel == "All" else accel

# ---------- Accelerator meta strip ----------
st.subheader("Accelerators")
meta_cols = st.columns(len(accelerators))
for col, (_, row) in zip(meta_cols, accelerators.iterrows(), strict=False):
    with col:
        st.markdown(f"**{row['name']}**")
        st.caption(row["hq_location"] or "")
        invest = row["investment_amount_usd"]
        equity = row["investment_equity_pct"]
        if invest:
            terms = f"${invest/1000:.0f}K"
            if equity:
                terms += f" / {equity:.0f}%"
            st.caption(terms)
        if row["founded_year"]:
            st.caption(f"Since {int(row['founded_year'])}")
        if row["total_companies_funded"]:
            st.metric("Companies", f"{int(row['total_companies_funded']):,}")

st.divider()

# ---------- Filtered views ----------
if accel_slug:
    filt = companies[companies["accelerator"] == accel_slug]
else:
    filt = companies

st.subheader("Headline metrics" + (f" — {accel_label_map[accel]}" if accel_slug else ""))

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Companies in DB", f"{len(filt):,}")
k2.metric("Active", f"{(filt['status'] == 'Active').sum():,}")
k3.metric("Acquired", f"{(filt['status'] == 'Acquired').sum():,}")
k4.metric("Public", f"{(filt['status'] == 'Public').sum():,}")
k5.metric("Dead", f"{(filt['status'] == 'Dead').sum():,}")

c1, c2 = st.columns(2)
c1.metric("AI-tagged", f"{filt['is_ai'].sum():,}")
c1.caption(f"{100 * filt['is_ai'].sum() / max(len(filt), 1):.1f}% of cohort")
c2.metric("Currently hiring", f"{filt['is_hiring'].sum():,}")
c2.caption(f"{100 * filt['is_hiring'].sum() / max(len(filt), 1):.1f}% of cohort")

st.divider()

# ---------- Status distribution ----------
left, right = st.columns(2)

with left:
    st.subheader("Status distribution")
    sc = status_counts(accel_slug)
    if len(sc):
        fig = px.pie(sc, names="status", values="n", hole=0.4)
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data.")

with right:
    st.subheader("Top industries")
    ind = industry_counts(accel_slug).head(12)
    if len(ind):
        fig = px.bar(ind, x="n", y="industry", orientation="h")
        fig.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            height=320,
            yaxis=dict(autorange="reversed"),
            xaxis_title="Companies",
            yaxis_title=None,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data.")

# ---------- Batch trend ----------
st.subheader("Batch sizes over time")
bt = batch_trend(accel_slug)
if len(bt):
    agg = bt.groupby(["year", "accelerator"], as_index=False)["company_count"].sum()
    fig = px.bar(
        agg,
        x="year",
        y="company_count",
        color="accelerator" if not accel_slug else None,
        labels={"company_count": "Companies", "year": "Batch year"},
    )
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=340)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No batches ingested for this accelerator yet.")

st.caption(
    "Explorer, Survivorship, and Data Quality pages available in the sidebar."
)

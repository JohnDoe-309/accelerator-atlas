"""Survivorship — outcome rates by batch year."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from accelerator_atlas.dashboard.data import load_companies, survivorship_by_batch_year

st.set_page_config(page_title="Survivorship · Accelerator Atlas", layout="wide")
st.title("Survivorship")
st.caption(
    "Outcome rates per batch year. 'Active' is best read against age — older batches "
    "have had more time to die or exit."
)

with st.sidebar:
    accel = st.selectbox("Accelerator", ["yc"], index=0)

surv = survivorship_by_batch_year(accel)
if not len(surv):
    st.info("No batch-linked companies for this accelerator yet.")
    st.stop()

status_cols = [c for c in surv.columns if c not in ("year", "total")]
long_df = surv.melt(
    id_vars=["year", "total"],
    value_vars=status_cols,
    var_name="status",
    value_name="pct",
)

st.subheader("Outcome mix by batch year")
fig = px.bar(
    long_df,
    x="year",
    y="pct",
    color="status",
    labels={"pct": "% of cohort", "year": "Batch year"},
    color_discrete_map={
        "Active": "#3B82F6",
        "Acquired": "#10B981",
        "Public": "#8B5CF6",
        "Dead": "#EF4444",
        "Unknown": "#9CA3AF",
    },
)
fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=440, barmode="stack")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Cohort sizes")
fig2 = px.bar(surv, x="year", y="total", labels={"total": "Companies"})
fig2.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=240)
st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ---------- Acquisitions / IPOs leaderboard ----------
df = load_companies()
df = df[df["accelerator"] == accel]

a, b = st.columns(2)
with a:
    st.subheader("Acquired companies")
    acq = df[df["status"] == "Acquired"][
        ["name", "batch", "industry_primary", "team_size_current", "website"]
    ].sort_values("team_size_current", ascending=False, na_position="last")
    st.dataframe(acq, use_container_width=True, hide_index=True, height=400)

with b:
    st.subheader("Public companies")
    pub = df[df["status"] == "Public"][
        ["name", "batch", "industry_primary", "team_size_current", "website"]
    ].sort_values("team_size_current", ascending=False, na_position="last")
    st.dataframe(pub, use_container_width=True, hide_index=True, height=400)

st.divider()
st.subheader("YC 'Top Companies' list")
top = df[df["is_top_company"]][
    ["name", "batch", "status", "industry_primary", "team_size_current", "website"]
].sort_values("team_size_current", ascending=False, na_position="last")
st.dataframe(top, use_container_width=True, hide_index=True, height=400)
st.caption(f"{len(top):,} companies flagged as YC Top Company.")

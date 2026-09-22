"""Data Quality — what's filled, what's missing, per accelerator."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from accelerator_atlas.dashboard.data import (
    coverage_by_field,
    load_accelerators,
    load_companies,
)

st.set_page_config(page_title="Data Quality · Accelerator Atlas", layout="wide")
st.title("Data Quality")
st.caption("Field-level coverage. Funding/revenue land here once Phase 3 enrichment runs.")

accelerators = load_accelerators()
slug_to_name = dict(zip(accelerators["slug"], accelerators["name"], strict=False))

with st.sidebar:
    st.header("Scope")
    options = ["All"] + accelerators["slug"].tolist()
    sel = st.selectbox(
        "Accelerator",
        options,
        format_func=lambda s: slug_to_name.get(s, "All accelerators"),
    )
    scope = None if sel == "All" else sel

cov = coverage_by_field(scope)

companies = load_companies()
if scope:
    total_n = (companies["accelerator"] == scope).sum()
else:
    total_n = len(companies)

st.metric("Companies in scope", f"{int(total_n):,}")

st.subheader("Field coverage")
fig = px.bar(
    cov,
    x="coverage_pct",
    y="field",
    orientation="h",
    text="coverage_pct",
    labels={"coverage_pct": "% filled", "field": "Field"},
)
fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig.update_layout(
    margin=dict(t=10, b=0, l=0, r=40),
    height=480,
    yaxis=dict(autorange="reversed"),
    xaxis=dict(range=[0, 110]),
)
st.plotly_chart(fig, use_container_width=True)

st.dataframe(cov, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Per-accelerator row counts")
counts = (
    companies.groupby("accelerator_name")
    .size()
    .reset_index(name="companies")
    .sort_values("companies", ascending=False)
)
st.dataframe(counts, use_container_width=True, hide_index=True)

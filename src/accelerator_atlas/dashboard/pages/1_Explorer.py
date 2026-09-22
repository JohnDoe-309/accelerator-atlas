"""Explorer — filterable, sortable table of every company we've ingested."""

from __future__ import annotations

import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from accelerator_atlas.dashboard.data import load_companies

st.set_page_config(page_title="Explorer · Accelerator Atlas", layout="wide")
st.title("Explorer")
st.caption("Filter, sort, and inspect every ingested company. Click a row for details.")

df = load_companies()

# ---------- Filters ----------
with st.sidebar:
    st.header("Filters")

    accel_options = sorted(df["accelerator"].unique().tolist())
    accel = st.multiselect("Accelerator", accel_options, default=accel_options)

    status_options = sorted(df["status"].dropna().unique().tolist())
    statuses = st.multiselect("Status", status_options, default=status_options)

    industry_options = sorted(df["industry_primary"].dropna().unique().tolist())
    industries = st.multiselect("Industry", industry_options)

    year_min = int(df["batch_year"].min(skipna=True) or 2005)
    year_max = int(df["batch_year"].max(skipna=True) or 2025)
    years = st.slider("Batch year", year_min, year_max, (year_min, year_max))

    flags = st.multiselect(
        "Flags",
        ["AI", "B2B", "Hiring", "Top company", "Nonprofit"],
    )

    search = st.text_input("Search (name / one-liner)").strip().lower()

# ---------- Apply filters ----------
mask = (
    df["accelerator"].isin(accel)
    & df["status"].isin(statuses)
    & df["batch_year"].between(years[0], years[1])
)
if industries:
    mask &= df["industry_primary"].isin(industries)
if "AI" in flags:
    mask &= df["is_ai"]
if "B2B" in flags:
    mask &= df["is_b2b"]
if "Hiring" in flags:
    mask &= df["is_hiring"]
if "Top company" in flags:
    mask &= df["is_top_company"]
if "Nonprofit" in flags:
    mask &= df["is_nonprofit"]
if search:
    mask &= df["name"].str.lower().str.contains(search, na=False) | df[
        "one_liner"
    ].fillna("").str.lower().str.contains(search, na=False)

view = df[mask].copy()

st.write(f"**{len(view):,}** companies match · out of {len(df):,} total")

display_cols = [
    "name",
    "accelerator",
    "batch",
    "status",
    "industry_primary",
    "team_size_current",
    "country",
    "one_liner",
    "website",
    "is_ai",
    "is_top_company",
]

grid_df = view[display_cols].rename(
    columns={
        "industry_primary": "industry",
        "team_size_current": "team",
        "is_ai": "AI",
        "is_top_company": "top",
    }
)

gob = GridOptionsBuilder.from_dataframe(grid_df)
gob.configure_default_column(filter=True, sortable=True, resizable=True)
gob.configure_column("name", pinned="left", width=200)
gob.configure_column("one_liner", width=420)
gob.configure_column("website", width=220)
gob.configure_selection("single", use_checkbox=False)
gob.configure_pagination(paginationAutoPageSize=False, paginationPageSize=50)
grid_options = gob.build()

resp = AgGrid(
    grid_df,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    height=600,
    fit_columns_on_grid_load=False,
    allow_unsafe_jscode=True,
)

selected = resp.get("selected_rows")
if selected is not None and len(selected):
    sel_name = selected.iloc[0]["name"] if hasattr(selected, "iloc") else selected[0]["name"]
    rec = df[df["name"] == sel_name].iloc[0]
    st.divider()
    st.subheader(rec["name"])
    if rec["one_liner"]:
        st.markdown(f"_{rec['one_liner']}_")

    meta_cols = st.columns(4)
    meta_cols[0].markdown(f"**Accelerator** · {rec['accelerator_name']}")
    meta_cols[1].markdown(f"**Batch** · {rec['batch'] or '—'}")
    meta_cols[2].markdown(f"**Status** · {rec['status']}")
    meta_cols[3].markdown(f"**Team** · {int(rec['team_size_current']) if rec['team_size_current'] else '—'}")

    link_cols = st.columns(4)
    if rec["website"]:
        link_cols[0].markdown(f"[Website]({rec['website']})")
    if rec["linkedin_url"]:
        link_cols[1].markdown(f"[LinkedIn]({rec['linkedin_url']})")
    if rec["crunchbase_url"]:
        link_cols[2].markdown(f"[Crunchbase]({rec['crunchbase_url']})")
    if rec["source_url"]:
        link_cols[3].markdown(f"[Source]({rec['source_url']})")

    if rec["long_description"]:
        st.markdown("**Description**")
        st.write(rec["long_description"])

    tag_bits = []
    if rec["industry_primary"]:
        tag_bits.append(rec["industry_primary"])
    if rec["industry_sub"]:
        tag_bits.append(rec["industry_sub"])
    if rec["country"]:
        tag_bits.append(rec["country"])
    if rec["is_ai"]:
        tag_bits.append("AI")
    if rec["is_b2b"]:
        tag_bits.append("B2B")
    if rec["is_top_company"]:
        tag_bits.append("YC top company")
    if tag_bits:
        st.caption(" · ".join(tag_bits))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide", page_title="Executive Supply Chain Dashboard")

# =====================================================
# HEADER / USER INSTRUCTIONS
# =====================================================
st.title("📊 Executive Supply Chain Dashboard")

st.markdown("""
### Instructions
1. Upload your SAP datasets:
   - Manual Accruals
   - SAP TM
   - SAP ERP
2. Use sidebar filters to explore cost drivers
3. Identify optimization opportunities (carriers, routes, delays)
""")

# =====================================================
# FILE UPLOADS
# =====================================================
st.sidebar.header("Upload Files")

accruals_file = st.sidebar.file_uploader("Manual Accruals", type=["xlsx"])
tm_file = st.sidebar.file_uploader("SAP TM", type=["xlsx"])
erp_file = st.sidebar.file_uploader("SAP ERP", type=["xlsx"])

# =====================================================
# LOAD DATA
# =====================================================
def load_data(accruals_file, tm_file, erp_file):
    accruals, tm, erp = None, None, None

    if accruals_file:
        accruals = pd.read_excel(accruals_file, engine="openpyxl")

    if tm_file:
        tm = pd.read_excel(tm_file, engine="openpyxl")

    if erp_file:
        erp = pd.read_excel(erp_file, engine="openpyxl")

    return accruals, tm, erp


accruals, tm, erp = load_data(accruals_file, tm_file, erp_file)

# =====================================================
# SAFETY CHECKS
# =====================================================
if accruals is None:
    st.warning("Please upload the Manual Accruals file to start.")
    st.stop()

if tm is None:
    st.info("SAP TM not uploaded — transport metrics limited.")

if erp is None:
    st.info("SAP ERP not uploaded — product analysis limited.")

# =====================================================
# STANDARDIZE COLUMNS
# =====================================================
def safe_rename(df):
    col_map = {
        "Net Amt in Doc Crcy": "Cost",
        "Net value": "NetValue"
    }
    return df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

accruals = safe_rename(accruals)
if tm is not None:
    tm = safe_rename(tm)
if erp is not None:
    erp = safe_rename(erp)

# =====================================================
# DATE PARSING
# =====================================================
for col in accruals.columns:
    if "Date" in col:
        accruals[col] = pd.to_datetime(accruals[col], errors="coerce")

# =====================================================
# SIDEBAR FILTERS
# =====================================================
st.sidebar.header("Filters")

status_filter = st.sidebar.multiselect(
    "Status",
    accruals.get("Execution Status", pd.Series()).dropna().unique(),
    default=accruals.get("Execution Status", pd.Series()).dropna().unique()
)

date_range = st.sidebar.date_input(
    "Date Range",
    [accruals["Actual Delivered Date"].min(), accruals["Actual Delivered Date"].max()]
)

df = accruals.copy()

if "Execution Status" in df.columns:
    df = df[df["Execution Status"].isin(status_filter)]

if "Actual Delivered Date" in df.columns:
    df = df[
        (df["Actual Delivered Date"] >= pd.to_datetime(date_range[0])) &
        (df["Actual Delivered Date"] <= pd.to_datetime(date_range[1]))
    ]

# =====================================================
# KPIs
# =====================================================
total_cost = df["Cost"].sum() if "Cost" in df.columns else 0
shipments = len(df)
avg_cost = df["Cost"].mean() if "Cost" in df.columns else 0
exec_rate = (
    (df["Execution Status"] == "Executed").mean()
    if "Execution Status" in df.columns else 0
)

avg_cost_per_kg = 0
if tm is not None and "Cost" in tm.columns and "Gross Weight" in tm.columns:
    tm["Cost_per_kg"] = tm["Cost"] / tm["Gross Weight"].replace(0, np.nan)
    avg_cost_per_kg = tm["Cost_per_kg"].mean()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Cost", f"€{total_cost:,.0f}")
col2.metric("Shipments", f"{shipments:,}")
col3.metric("Avg Cost", f"€{avg_cost:,.0f}")
col4.metric("Execution Rate", f"{exec_rate*100:.1f}%")
col5.metric("Avg €/kg", f"{avg_cost_per_kg:.2f}")

# =====================================================
# COST DRIVERS
# =====================================================
st.subheader("💸 Cost Drivers")

group_col = st.selectbox(
    "Break cost by",
    [col for col in ["Carrier Description", "Incoterm", "Ob Sales Org ID"] if col in df.columns]
)

waterfall = df.groupby(group_col)["Cost"].sum().sort_values(ascending=False).head(10)

fig = px.bar(
    x=waterfall.index,
    y=waterfall.values,
    labels={"x": group_col, "y": "Cost"},
    title="Top Cost Drivers"
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# NETWORK VIEW
# =====================================================
if "Source Location Description" in df.columns and "Destination Location Descripti" in df.columns:
    st.subheader("🌍 Network – Top Routes")

    df["Route"] = df["Source Location Description"] + " → " + df["Destination Location Descripti"]

    route_df = df.groupby("Route")["Cost"].sum().sort_values(ascending=False).head(15)

    fig = px.bar(
        route_df,
        orientation="h",
        title="Top Expensive Routes"
    )

    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# CARRIER PERFORMANCE
# =====================================================
if "Carrier Description" in df.columns:
    st.subheader("🚚 Carrier Performance")

    carrier_perf = df.groupby("Carrier Description").agg(
        total_cost=("Cost", "sum"),
        shipments=("Cost", "count")
    )

    carrier_perf["cost_per_shipment"] = carrier_perf["total_cost"] / carrier_perf["shipments"]

    carrier_perf = carrier_perf.sort_values("total_cost", ascending=False).head(10)

    fig = px.scatter(
        carrier_perf,
        x="shipments",
        y="cost_per_shipment",
        size="total_cost",
        text=carrier_perf.index,
        title="Carrier Efficiency"
    )

    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# PRODUCT ANALYSIS (ERP)
# =====================================================
if erp is not None and "NetValue" in erp.columns:
    st.subheader("📦 Product Value Analysis")

    group_col = st.selectbox(
        "ERP grouping",
        [col for col in ["Matl Group", "Material"] if col in erp.columns]
    )

    erp_group = erp.groupby(group_col)["NetValue"].sum().nlargest(10)

    fig = px.bar(erp_group, title="Top Product Value Drivers")
    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# SCENARIO SIMULATOR
# =====================================================
if "Carrier Description" in df.columns:
    st.subheader("🧮 Cost Optimization Simulator")

    carrier_cost = df.groupby("Carrier Description")["Cost"].sum()

    top_carrier = carrier_cost.idxmax()
    top_cost = carrier_cost.max()

    reduction = st.slider("Reduce top carrier cost (%)", 0, 30, 10)

    savings = top_cost * reduction / 100

    st.metric("Estimated Savings", f"€{savings:,.0f}")
    st.info(f"Top carrier: {top_carrier}")

# =====================================================
# TIME SERIES
# =====================================================
if "Actual Delivered Date" in df.columns:
    st.subheader("📈 Cost Evolution")

    time_df = df.groupby(pd.Grouper(key="Actual Delivered Date", freq="W"))["Cost"].sum()

    fig = px.line(time_df, title="Weekly Cost Trend")
    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# DATA TABLE
# =====================================================
st.subheader("🔍 Data Detail")
st.dataframe(df, use_container_width=True)

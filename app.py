import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide", page_title="Executive Supply Chain Dashboard")

# =====================================================
# HEADER
# =====================================================
st.title("📊 Executive Supply Chain Dashboard")

st.markdown("""
### Instructions
1. Upload your SAP datasets:
   - Manual Accruals
   - SAP TM
   - SAP ERP
2. Use filters to analyze cost drivers and performance
""")

# =====================================================
# FILE UPLOAD
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
    st.info("SAP ERP not uploaded — product insights limited.")

# =====================================================
# CLEAN / STANDARDIZE
# =====================================================
def safe_rename(df):
    col_map = {
        "Net Amt in Doc Crcy": "Cost",
        "Net value": "NetValue"
    }
    return df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})


def parse_euro_number(series):
    """Convert SAP EU number formats to float"""
    return pd.to_numeric(
        series.astype(str)
        .str.replace(".", "", regex=False)   # remove thousand separator
        .str.replace(",", ".", regex=False), # convert decimal
        errors="coerce"
    )


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
# FILTERS
# =====================================================
st.sidebar.header("Filters")

status_filter = []
if "Execution Status" in accruals.columns:
    status_filter = st.sidebar.multiselect(
        "Status",
        accruals["Execution Status"].dropna().unique(),
        default=accruals["Execution Status"].dropna().unique()
    )

date_range = None
if "Actual Delivered Date" in accruals.columns:
    date_range = st.sidebar.date_input(
        "Date Range",
        [accruals["Actual Delivered Date"].min(),
         accruals["Actual Delivered Date"].max()]
    )

df = accruals.copy()

if status_filter and "Execution Status" in df.columns:
    df = df[df["Execution Status"].isin(status_filter)]

if date_range and "Actual Delivered Date" in df.columns:
    df = df[
        (df["Actual Delivered Date"] >= pd.to_datetime(date_range[0])) &
        (df["Actual Delivered Date"] <= pd.to_datetime(date_range[1]))
    ]

# =====================================================
# KPI CALCULATION
# =====================================================
total_cost = df["Cost"].sum() if "Cost" in df.columns else 0
shipments = len(df)
avg_cost = df["Cost"].mean() if "Cost" in df.columns else 0

exec_rate = 0
if "Execution Status" in df.columns:
    exec_rate = (df["Execution Status"] == "Executed").mean()

# ✅ FIXED €/kg calculation
avg_cost_per_kg = 0

if tm is not None and "Cost" in tm.columns and "Gross Weight" in tm.columns:
    tm["Gross Weight"] = parse_euro_number(tm["Gross Weight"])
    tm["Cost_per_kg"] = tm["Cost"] / tm["Gross Weight"].replace(0, np.nan)
    avg_cost_per_kg = tm["Cost_per_kg"].mean()

# =====================================================
# KPI DISPLAY
# =====================================================
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

possible_cols = [c for c in ["Carrier Description", "Incoterm", "Ob Sales Org ID"] if c in df.columns]

if possible_cols:
    group_col = st.selectbox("Break cost by", possible_cols)

    cost_driver = df.groupby(group_col)["Cost"].sum().sort_values(ascending=False).head(10)

    fig = px.bar(
        x=cost_driver.index,
        y=cost_driver.values,
        labels={"x": group_col, "y": "Cost"}
    )

    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# NETWORK VIEW
# =====================================================
if "Source Location Description" in df.columns and "Destination Location Descripti" in df.columns:
    st.subheader("🌍 Top Routes")

    df["Route"] = df["Source Location Description"] + " → " + df["Destination Location Descripti"]

    routes = df.groupby("Route")["Cost"].sum().sort_values(ascending=False).head(15)

    fig = px.bar(routes, orientation="h")
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
        text=carrier_perf.index
    )

    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# ERP PRODUCT ANALYSIS
# =====================================================
if erp is not None and "NetValue" in erp.columns:

    st.subheader("📦 Product Analysis")

    cols = [c for c in ["Matl Group", "Material"] if c in erp.columns]

    if cols:
        group_col = st.selectbox("Group ERP data by", cols)

        erp_group = erp.groupby(group_col)["NetValue"].sum().nlargest(10)

        fig = px.bar(erp_group)
        st.plotly_chart(fig, use_container_width=True)

# =====================================================
# SCENARIO SIMULATION
# =====================================================
if "Carrier Description" in df.columns:
    st.subheader("🧮 Cost Optimization")

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
    st.subheader("📈 Cost Trend")

    time_df = df.groupby(pd.Grouper(key="Actual Delivered Date", freq="W"))["Cost"].sum()

    fig = px.line(time_df)
    st.plotly_chart(fig, use_container_width=True)

# =====================================================
# DATA TABLE
# =====================================================
st.subheader("🔍 Data")

st.dataframe(df, use_container_width=True)



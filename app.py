import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(layout="wide", page_title="Executive Supply Chain Dashboard")

# ===============================
# LOAD
# ===============================
@st.cache_data
def load_data():
    accruals = pd.read_excel("Manual accruals.xlsx", engine="openpyxl")
    tm = pd.read_excel("SAP TM.xlsx", engine="openpyxl")
    erp = pd.read_excel("SAP ERP.XLSX", engine="openpyxl")
    return accruals, tm, erp

accruals, tm, erp = load_data()

# ===============================
# CLEAN
# ===============================
accruals.rename(columns={"Net Amt in Doc Crcy": "Cost"}, inplace=True)

for col in accruals.columns:
    if "Date" in col:
        accruals[col] = pd.to_datetime(accruals[col], errors="coerce")

tm.rename(columns={"Net Amt in Doc Crcy": "Cost"}, inplace=True)

# ===============================
# MERGE KEY METRICS
# ===============================
tm["Cost_per_kg"] = tm["Cost"] / tm["Gross Weight"].replace(0, np.nan)

# ===============================
# SIDEBAR
# ===============================
st.sidebar.header("Executive Filters")

date_range = st.sidebar.date_input(
    "Date range",
    [accruals["Actual Delivered Date"].min(),
     accruals["Actual Delivered Date"].max()]
)

status = st.sidebar.multiselect(
    "Status",
    accruals["Execution Status"].dropna().unique(),
    default=accruals["Execution Status"].dropna().unique()
)

df = accruals[
    (accruals["Execution Status"].isin(status)) &
    (accruals["Actual Delivered Date"] >= pd.to_datetime(date_range[0])) &
    (accruals["Actual Delivered Date"] <= pd.to_datetime(date_range[1]))
]

# ===============================
# KPI SECTION (EXECUTIVE)
# ===============================
st.title("📊 Executive Supply Chain Dashboard")

col1, col2, col3, col4, col5 = st.columns(5)

total_cost = df["Cost"].sum()
shipments = len(df)
avg_cost = df["Cost"].mean()
exec_rate = (df["Execution Status"] == "Executed").mean()

col1.metric("Total Cost", f"€{total_cost:,.0f}")
col2.metric("Shipments", f"{shipments:,}")
col3.metric("Avg Cost", f"€{avg_cost:,.0f}")
col4.metric("Execution Rate", f"{exec_rate*100:.1f}%")

if "Cost" in tm.columns:
    col5.metric("Avg €/kg", f"{tm['Cost_per_kg'].mean():.2f}")

# ===============================
# WATERFALL (SIMPLIFIED)
# ===============================
st.subheader("💸 Cost Drivers (Waterfall-style)")

group_col = st.selectbox(
    "Break cost by",
    ["Carrier Description", "Incoterm", "Ob Sales Org ID"]
)

waterfall = df.groupby(group_col)["Cost"].sum().sort_values(ascending=False).head(10)
fig = px.bar(
    waterfall,
    x=waterfall.index,
    y=waterfall.values,
    title="Top Cost Drivers"
)
st.plotly_chart(fig, use_container_width=True)

# ===============================
# NETWORK VIEW
# ===============================
st.subheader("🌍 Logistics Network Analysis")

if "Source Location Description" in df.columns:
    df["Route"] = df["Source Location Description"] + " → " + df["Destination Location Descripti"]

    route_df = df.groupby("Route")["Cost"].sum().sort_values(ascending=False).head(15)
    fig = px.bar(route_df, orientation="h")
    st.plotly_chart(fig, use_container_width=True)

# ===============================
# CARRIER PERFORMANCE
# ===============================
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

# ===============================
# ERP PRODUCT PROFITABILITY
# ===============================
st.subheader("📦 Product Cost vs Value")

if "Net value" in erp.columns:
    grouping = st.selectbox("Group by", ["Matl Group", "Material"])

    erp_group = erp.groupby(grouping)["Net value"].sum().nlargest(10)

    fig = px.bar(erp_group, title="Top Value Drivers")
    st.plotly_chart(fig, use_container_width=True)

# ===============================
# SCENARIO SIMULATION
# ===============================
st.subheader("🧮 Cost Optimization Simulator")

top_carrier = df.groupby("Carrier Description")["Cost"].sum().idxmax()
top_cost = df.groupby("Carrier Description")["Cost"].sum().max()

reduction = st.slider("Reduce top carrier cost (%)", 0, 30, 10)

savings = top_cost * reduction / 100

st.metric("Estimated Savings", f"€{savings:,.0f}")

st.info(f"Top carrier: {top_carrier}")

# ===============================
# TIME SERIES
# ===============================
st.subheader("📈 Cost Evolution")

time_df = df.groupby(pd.Grouper(key="Actual Delivered Date", freq="W"))["Cost"].sum()

fig = px.line(time_df, title="Weekly Cost Trend")
st.plotly_chart(fig, use_container_width=True)



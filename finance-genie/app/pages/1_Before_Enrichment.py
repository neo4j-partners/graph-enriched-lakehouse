"""
Page 1: Before Enrichment — "What Flat Tables Show"

Reproduces the core Genie demo questions against raw tables and shows
why volume-based sorting surfaces whales, not fraud ring members.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import backend as db

st.set_page_config(page_title="Before Enrichment", layout="wide", page_icon="📊")
st.title("📊 Before Enrichment — What Flat Tables Show")
st.markdown(
    "These views recreate the questions a fraud analyst asks against raw lakehouse "
    "tables. Every answer looks plausible — but none surface the fraud rings."
)

# ── KPI Row ──────────────────────────────────────────────────────────────────

stats = db.get_overview_stats()
top_n = st.sidebar.slider("Top-N for ranking", 50, 500, 200, step=50)
vol_stats = db.get_fraud_in_top_n_volume(top_n)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Accounts", f"{stats['total_accounts']:,}")
k2.metric("Known Fraud", f"{stats['fraud_accounts']:,}")
k3.metric(f"Fraud in Top-{top_n} (Volume)", f"{vol_stats['fraud_in_top_n']}")
k4.metric("Fraud Hit Rate (Volume)", f"{vol_stats['pct']}%")

st.markdown("---")

# ── Section 1: Top Accounts by Transfer Volume ──────────────────────────────

st.subheader("1. Top Accounts by Inbound Transfer Volume")
st.markdown(
    "Sorting by inbound P2P count surfaces **whale accounts** — high-volume "
    "normal accounts that act as payment aggregators. Fraud ring members do not "
    "appear because their centrality is recursive, not volume-based."
)

df_volume = db.get_top_accounts_by_inbound(top_n)
df_volume["label"] = df_volume["is_fraud"].map({True: "Fraud", False: "Normal"})

fig_vol = px.bar(
    df_volume.head(50),
    x=df_volume.head(50).index,
    y="inbound_count",
    color="label",
    color_discrete_map={"Fraud": "#e74c3c", "Normal": "#3498db"},
    labels={"x": "Rank", "inbound_count": "Inbound Transfers", "label": ""},
    title=f"Top 50 Accounts by Inbound P2P Count",
)
fig_vol.update_layout(xaxis_title="Rank (by inbound count)", showlegend=True)
st.plotly_chart(fig_vol, use_container_width=True)

with st.expander("View full top-N table"):
    st.dataframe(
        df_volume,
        column_config={
            "account_id": st.column_config.NumberColumn("Account ID", format="%d"),
            "inbound_count": st.column_config.NumberColumn("Inbound #"),
            "inbound_total": st.column_config.NumberColumn("Inbound $", format="$%.2f"),
            "is_fraud": st.column_config.CheckboxColumn("Fraud?"),
        },
        hide_index=True,
        use_container_width=True,
    )

st.markdown("---")

# ── Section 2: Bilateral Transfer Pairs ─────────────────────────────────────

st.subheader("2. Top Bilateral Transfer Pairs")
st.markdown(
    "The top account pairs by mutual transfer count show **isolated pairs** "
    "with 3–4 transfers each. There is no way to see from this view that they "
    "belong to rings of ~100 accounts with high internal edge density."
)

df_pairs = db.get_bilateral_pairs(50)
df_pairs["pair_type"] = df_pairs.apply(
    lambda r: "Both Fraud" if r["a_is_fraud"] and r["b_is_fraud"]
    else ("Mixed" if r["a_is_fraud"] or r["b_is_fraud"] else "Both Normal"),
    axis=1,
)

fig_pairs = px.bar(
    df_pairs.head(30),
    x=df_pairs.head(30).index,
    y="mutual_transfers",
    color="pair_type",
    color_discrete_map={
        "Both Fraud": "#e74c3c",
        "Mixed": "#f39c12",
        "Both Normal": "#3498db",
    },
    labels={"x": "Pair Rank", "mutual_transfers": "Mutual Transfers"},
    title="Top 30 Bilateral Account Pairs",
)
fig_pairs.update_layout(xaxis_title="Pair Rank")
st.plotly_chart(fig_pairs, use_container_width=True)

with st.expander("View pairs table"):
    st.dataframe(df_pairs, hide_index=True, use_container_width=True)

st.markdown("---")

# ── Section 3: Transaction Amount Distribution ──────────────────────────────

st.subheader("3. Transaction Amount Distribution: Fraud vs Normal")
st.markdown(
    "Fraud accounts average **$123.90** per transaction vs **$111.77** for normals "
    "— a 10.8% gap. The distributions overlap almost entirely, making amount-based "
    "ranking ineffective: the top-N by avg amount is dominated by high-spending normals."
)

df_amounts = db.get_avg_txn_amount_by_fraud()
df_amounts["label"] = df_amounts["is_fraud"].map({True: "Fraud", False: "Normal"})

fig_hist = px.histogram(
    df_amounts,
    x="avg_amount",
    color="label",
    color_discrete_map={"Fraud": "#e74c3c", "Normal": "#3498db"},
    nbins=60,
    barmode="overlay",
    opacity=0.7,
    labels={"avg_amount": "Avg Transaction Amount ($)", "label": ""},
    title="Distribution of Per-Account Avg Transaction Amount",
)
fig_hist.update_layout(yaxis_title="Account Count")
st.plotly_chart(fig_hist, use_container_width=True)

col_a, col_b = st.columns(2)
fraud_avg = df_amounts.loc[df_amounts["is_fraud"] == True, "avg_amount"].mean()
normal_avg = df_amounts.loc[df_amounts["is_fraud"] == False, "avg_amount"].mean()
col_a.metric("Fraud Avg Txn Amount", f"${fraud_avg:,.2f}")
col_b.metric("Normal Avg Txn Amount", f"${normal_avg:,.2f}")

st.markdown("---")

# ── Section 4: The Verdict ──────────────────────────────────────────────────

st.subheader("4. The Verdict")
st.error(
    f"**Volume sorting finds {vol_stats['fraud_in_top_n']} fraud accounts in the "
    f"top {top_n}** — a {vol_stats['pct']}% hit rate. The flat table approach "
    f"surfaces whales, not ring members. The fraud is hiding in network structure "
    f"that no single-table sort can reach."
)
st.info(
    "👉 Navigate to **After Enrichment** in the sidebar to see how PageRank, "
    "Louvain, and Node Similarity resolve these same questions."
)

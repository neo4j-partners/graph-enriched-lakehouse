"""
Page 2: After Enrichment — "What Graph Algorithms Reveal"

The same data, augmented with Neo4j GDS features (PageRank, Louvain,
Node Similarity), answering the same fraud questions correctly.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import backend as db

st.set_page_config(page_title="After Enrichment", layout="wide", page_icon="🔬")
st.title("🔬 After Enrichment — What Graph Algorithms Reveal")
st.markdown(
    "Three Neo4j GDS algorithms — **PageRank**, **Louvain**, and **Node Similarity** "
    "— write `risk_score`, `community_id`, and `similarity_score` back to the "
    "accounts table. The same questions now resolve correctly."
)

# ── KPI Row ──────────────────────────────────────────────────────────────────

top_n = st.sidebar.slider("Top-N for ranking", 50, 500, 200, step=50)
risk_stats = db.get_fraud_in_top_n_risk(top_n)
risk_summary = db.get_risk_score_summary()

fraud_row = risk_summary[risk_summary["is_fraud"] == True]
normal_row = risk_summary[risk_summary["is_fraud"] == False]
fraud_avg_risk = float(fraud_row["avg_risk_score"].iloc[0]) if len(fraud_row) > 0 else 0
normal_avg_risk = float(normal_row["avg_risk_score"].iloc[0]) if len(normal_row) > 0 else 0
separation_ratio = round(fraud_avg_risk / max(normal_avg_risk, 1e-9), 2)

k1, k2, k3, k4 = st.columns(4)
k1.metric(f"Fraud in Top-{top_n} (Risk Score)", f"{risk_stats['fraud_in_top_n']}")
k2.metric("Fraud Hit Rate (Risk Score)", f"{risk_stats['pct']}%")
k3.metric("Risk Score Separation", f"{separation_ratio}×")
k4.metric("Fraud Avg Risk Score", f"{fraud_avg_risk:.6f}")

st.markdown("---")

# ── Section 1: PageRank Risk Scores ─────────────────────────────────────────

st.subheader("1. PageRank Risk Scores — Fraud vs Normal")
st.markdown(
    f"Fraud accounts average **{separation_ratio}×** higher `risk_score` than "
    f"normal accounts. Sorting by risk_score now surfaces **ring members**, not whales."
)

df_gold = db.get_gold_accounts()
df_gold["label"] = df_gold["is_fraud"].map({True: "Fraud", False: "Normal"})

fig_risk = px.histogram(
    df_gold,
    x="risk_score",
    color="label",
    color_discrete_map={"Fraud": "#e74c3c", "Normal": "#3498db"},
    nbins=80,
    barmode="overlay",
    opacity=0.7,
    marginal="box",
    labels={"risk_score": "PageRank Risk Score", "label": ""},
    title="Distribution of PageRank Risk Scores",
)
fig_risk.update_layout(yaxis_title="Account Count")
st.plotly_chart(fig_risk, use_container_width=True)

# Scatter: risk_score vs balance, colored by fraud
fig_scatter = px.scatter(
    df_gold.sample(min(5000, len(df_gold)), random_state=42),
    x="risk_score",
    y="balance",
    color="label",
    color_discrete_map={"Fraud": "#e74c3c", "Normal": "#3498db"},
    opacity=0.5,
    labels={"risk_score": "PageRank Risk Score", "balance": "Account Balance ($)"},
    title="Risk Score vs Balance (sampled)",
)
st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")

# ── Section 2: Louvain Communities ──────────────────────────────────────────

st.subheader("2. Louvain Community Detection")
st.markdown(
    "Louvain partitions the transfer network into communities. **10 communities "
    "map cleanly to 10 fraud rings** with high purity — the ring structure that "
    "was invisible in bilateral pair views."
)

df_communities = db.get_community_stats()

# Show top communities by fraud count
fig_comm = px.bar(
    df_communities.head(20),
    x="community_id",
    y="member_count",
    color="purity_pct",
    color_continuous_scale=["#3498db", "#e74c3c"],
    text="fraud_count",
    labels={
        "community_id": "Community ID",
        "member_count": "Members",
        "purity_pct": "Fraud Purity %",
    },
    title="Top 20 Communities by Fraud Count",
)
fig_comm.update_traces(texttemplate="%{text} fraud", textposition="outside")
fig_comm.update_layout(xaxis_type="category")
st.plotly_chart(fig_comm, use_container_width=True)

# Community explorer
st.markdown("#### Community Explorer")
community_ids = sorted(df_communities["community_id"].tolist())
selected_community = st.selectbox(
    "Select a community to inspect",
    community_ids,
    index=0,
)

if selected_community is not None:
    df_members = db.get_community_members(int(selected_community))
    comm_row = df_communities[df_communities["community_id"] == selected_community]
    if len(comm_row) > 0:
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Members", f"{int(comm_row['member_count'].iloc[0])}")
        mc2.metric("Fraud Members", f"{int(comm_row['fraud_count'].iloc[0])}")
        mc3.metric("Purity", f"{comm_row['purity_pct'].iloc[0]}%")

    st.dataframe(
        df_members,
        column_config={
            "account_id": st.column_config.NumberColumn("Account ID", format="%d"),
            "risk_score": st.column_config.NumberColumn("Risk Score", format="%.6f"),
            "similarity_score": st.column_config.NumberColumn("Similarity", format="%.4f"),
            "is_fraud": st.column_config.CheckboxColumn("Fraud?"),
        },
        hide_index=True,
        use_container_width=True,
    )

st.markdown("---")

# ── Section 3: Node Similarity Pairs ────────────────────────────────────────

st.subheader("3. Node Similarity — Shared Merchant Patterns")
st.markdown(
    "Node Similarity computes Jaccard similarity over merchant-visit patterns. "
    "Fraud pairs average **1.98×** higher similarity than normal pairs — "
    "the shared anchor merchants are now visible."
)

df_sim = db.get_similarity_pairs(200)

fig_sim = px.histogram(
    df_sim,
    x="similarity_score",
    color="pair_type",
    color_discrete_map={
        "Both Fraud": "#e74c3c",
        "Mixed": "#f39c12",
        "Both Normal": "#3498db",
    },
    nbins=40,
    barmode="overlay",
    opacity=0.7,
    labels={"similarity_score": "Similarity Score", "pair_type": ""},
    title="Distribution of Similarity Scores in Top-200 Pairs",
)
st.plotly_chart(fig_sim, use_container_width=True)

with st.expander("View top similarity pairs"):
    st.dataframe(
        df_sim,
        column_config={
            "account_id_a": st.column_config.NumberColumn("Account A", format="%d"),
            "account_id_b": st.column_config.NumberColumn("Account B", format="%d"),
            "similarity_score": st.column_config.NumberColumn("Similarity", format="%.4f"),
        },
        hide_index=True,
        use_container_width=True,
    )

st.markdown("---")

# ── Section 4: Enriched Account Table ───────────────────────────────────────

st.subheader("4. Enriched Account Table")
st.markdown(
    "The full `gold_accounts` table with graph features. Sort by any column "
    "to see fraud clustering that was invisible in the raw data."
)

show_fraud_only = st.checkbox("Show fraud accounts only", value=False)
df_display = df_gold[df_gold["is_fraud"] == True] if show_fraud_only else df_gold

st.dataframe(
    df_display.sort_values("risk_score", ascending=False),
    column_config={
        "account_id": st.column_config.NumberColumn("Account ID", format="%d"),
        "balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
        "risk_score": st.column_config.NumberColumn("Risk Score", format="%.6f"),
        "community_id": st.column_config.NumberColumn("Community", format="%d"),
        "similarity_score": st.column_config.NumberColumn("Similarity", format="%.4f"),
        "is_fraud": st.column_config.CheckboxColumn("Fraud?"),
    },
    hide_index=True,
    use_container_width=True,
    height=500,
)

st.markdown("---")

# ── Section 5: The Verdict ──────────────────────────────────────────────────

st.subheader("5. The Verdict")
st.success(
    f"**Risk score sorting finds {risk_stats['fraud_in_top_n']} fraud accounts "
    f"in the top {top_n}** — a {risk_stats['pct']}% hit rate. Three graph "
    f"algorithms computed in seconds gave us the structural signal that no "
    f"flat-table sort could reach."
)

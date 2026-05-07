"""Data lineage view for the graph-enriched Genie workflow."""

from __future__ import annotations

import streamlit as st


st.set_page_config(page_title="Data Lineage", layout="wide")

st.title("Data Lineage")
st.markdown(
    """
    The graph analysis sits between governed Silver tables and Genie-facing Gold
    tables. Nothing reaches Genie until it has been materialized back into Delta.
    """
)

silver, graph, gold, genie = st.columns(4)

with silver:
    st.subheader("Silver")
    st.markdown(
        """
        - `accounts`
        - `transactions`
        - `account_links`
        - `merchants`
        """
    )
    st.caption("Rows, transfers, payments, and merchant dimensions.")

with graph:
    st.subheader("Neo4j GDS")
    st.markdown(
        """
        - PageRank
        - Louvain
        - Node Similarity
        """
    )
    st.caption("Algorithms compute structural properties over the network.")

with gold:
    st.subheader("Gold")
    st.markdown(
        """
        - `gold_accounts`
        - `gold_account_similarity_pairs`
        - `gold_fraud_ring_communities`
        """
    )
    st.caption("Graph outputs become ordinary Delta columns.")

with genie:
    st.subheader("Genie")
    st.markdown(
        """
        - Group by risk tier
        - Filter ring communities
        - Rank by risk score
        - Compare merchant concentration
        """
    )
    st.caption("Analysts ask business questions in natural language.")

st.markdown("### Governed Interface")
st.success(
    "The audit boundary stays in Databricks. Neo4j computes graph features; "
    "Databricks stores the outputs in Gold Delta tables; Genie reads those "
    "columns through the governed catalog."
)

st.markdown("### Why This Matters")
st.markdown(
    """
    - Finance users keep the Genie workflow they already understand.
    - Platform teams keep Unity Catalog governance and SQL warehouse access.
    - Graph features become reusable dimensions for dashboards, Genie, and ML.
    - The before and after comparison is reproducible because the after signal is
      materialized as deterministic columns.
    """
)

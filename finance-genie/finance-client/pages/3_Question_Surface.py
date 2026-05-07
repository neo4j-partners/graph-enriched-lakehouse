"""Question surface unlocked by graph enrichment."""

from __future__ import annotations

import streamlit as st

import backend as db


st.set_page_config(page_title="Question Surface", layout="wide")

st.title("Question Surface")
st.markdown(
    """
    Graph enrichment changes what the catalog can express. Genie still produces
    SQL, but the after space includes dimensions that did not exist in the base
    rows.
    """
)

surface = db.question_surface()
st.dataframe(surface, hide_index=True, use_container_width=True)

st.markdown("### Column Unlocks")
left, mid, right = st.columns(3)

with left:
    st.subheader("PageRank")
    st.metric("Gold column", "risk_score")
    st.markdown(
        "Ranks accounts by transfer-network centrality, so Genie can sort by "
        "structural importance instead of raw transfer volume."
    )

with mid:
    st.subheader("Louvain")
    st.metric("Gold column", "community_id")
    st.markdown(
        "Assigns accounts to communities, so Genie can group transfers and "
        "balances by structural membership."
    )

with right:
    st.subheader("Node Similarity")
    st.metric("Gold column", "similarity_score")
    st.markdown(
        "Measures shared merchant behavior, so Genie can compare accounts that "
        "look similar even when they do not transfer directly."
    )

st.markdown("### Catalog Expansion")
st.info(
    "`fraud_risk_tier` and `is_ring_community` are plain Gold columns. Genie can "
    "filter on them with the same SQL patterns it already uses for region, "
    "category, balance, and account type."
)

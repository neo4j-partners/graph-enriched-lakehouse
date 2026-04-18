"""
Graph-Enriched Lakehouse Explorer
==================================
Interactive comparison of lakehouse data before and after Neo4j GDS enrichment.

This is the main entry point for the Streamlit multi-page app.
Pages are auto-discovered from the pages/ directory.
"""

import streamlit as st

st.set_page_config(
    page_title="Graph-Enriched Lakehouse Explorer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Graph-Enriched Lakehouse Explorer")

st.markdown("""
### From Flat Tables to Graph Intelligence

This app demonstrates the difference between analyzing financial fraud data with
**flat lakehouse tables** versus **graph-enriched features** from Neo4j GDS.

The same five questions a fraud analyst would ask are answered two ways:

| Approach | Tools | What It Finds |
|----------|-------|---------------|
| **Before Enrichment** | SQL sorts, aggregates, bilateral pairs | Whale accounts (high-volume normals) |
| **After Enrichment** | PageRank, Louvain, Node Similarity | Fraud ring members |

---

**Navigate using the sidebar** to explore each view:

- **Before Enrichment** — What flat tables show (and miss)
- **After Enrichment** — What graph algorithms reveal
""")

st.sidebar.markdown("---")
st.sidebar.caption(
    "Built with Streamlit on Databricks Apps. "
    "Data: `graph-enriched-lakehouse.graph-enriched-schema`."
)

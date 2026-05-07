"""Finance Genie Client.

Streamlit entry point for a Databricks App that demonstrates how graph-derived
Gold columns expand the questions Genie can answer for financial crime analysis.
"""

from __future__ import annotations

import streamlit as st


st.set_page_config(
    page_title="Finance Genie Client",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --fg-border: #d8dee8;
            --fg-soft: #f6f8fb;
            --fg-ink: #162033;
            --fg-muted: #526071;
            --fg-accent: #0f766e;
            --fg-warn: #9a3412;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1180px;
        }
        .fg-kicker {
            color: var(--fg-accent);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }
        .fg-subtle {
            color: var(--fg-muted);
            font-size: 1rem;
            line-height: 1.45;
        }
        .fg-panel {
            border: 1px solid var(--fg-border);
            border-radius: 8px;
            padding: 1rem;
            background: #fff;
        }
        .fg-band {
            border: 1px solid var(--fg-border);
            border-radius: 8px;
            padding: 1rem 1.1rem;
            background: var(--fg-soft);
            margin: 1rem 0;
        }
        .fg-question {
            font-size: 1rem;
            font-weight: 650;
            line-height: 1.35;
            color: var(--fg-ink);
        }
        .fg-small {
            color: var(--fg-muted);
            font-size: 0.88rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_styles()

st.sidebar.title("Finance Genie Client")
st.sidebar.caption("Same Genie. Expanded catalog.")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "Use the pages above to compare the Silver-only Genie experience with the "
    "Gold graph-enriched experience."
)

st.markdown('<div class="fg-kicker">Graph-Enriched Lakehouse</div>', unsafe_allow_html=True)
st.title("Finance Genie Client")
st.markdown(
    """
    This Databricks App demonstrates the value of the before and after Genie
    experience for finance teams. The before space points Genie at the base
    Silver tables. The after space points Genie at the same business domain plus
    Gold tables enriched with graph-derived columns from Neo4j Graph Data
    Science.
    """
)

st.markdown(
    """
    <div class="fg-band">
      <div class="fg-question">The product claim</div>
      <div class="fg-subtle">
        Genie does not need a new analyst workflow. Once structural signals such
        as risk score, community membership, similarity, and risk tier are
        materialized as Delta columns, Genie can group, filter, and compare them
        like any other governed Lakehouse dimension.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns(2)

with left:
    st.subheader("Before enrichment")
    st.markdown(
        """
        The Silver-only catalog supports standard BI questions: account volume,
        merchant popularity, balances, transfer counts, and regional workload.
        Those are legitimate questions over flat rows.
        """
    )
    st.caption("Best for: tabular aggregation and descriptive finance analytics.")

with right:
    st.subheader("After enrichment")
    st.markdown(
        """
        The Gold catalog adds structural dimensions: PageRank risk score,
        Louvain community, shared-merchant similarity, and precomputed risk
        tiers. Genie can now answer relationship-aware finance questions.
        """
    )
    st.caption("Best for: triage, concentration, exposure, and ring-candidate analysis.")

st.markdown("### Databricks App Checklist")
st.markdown(
    """
    - Framework selected: Streamlit
    - Auth strategy: app auth through Databricks SDK `Config()`
    - App resources: SQL warehouse injected through `app.yaml`
    - Backend data strategy: SQL warehouse over Delta tables
    - Deployment method: Databricks Apps CLI or Asset Bundles
    """
)

st.info("Open Lakehouse Graph Schema first to see the graph context, then continue to Executive Comparison.")

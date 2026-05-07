"""Executive before and after comparison."""

from __future__ import annotations

import streamlit as st

import backend as db


st.set_page_config(page_title="Executive Comparison", layout="wide")


SILVER_METRICS = (
    "Silver accounts",
    "Silver transactions",
    "Silver transfers",
)
GOLD_METRICS = (
    "Gold accounts",
    "High-risk Gold accounts",
    "Ring-candidate communities",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1220px;
        }
        .fg-split-label {
            border-radius: 8px;
            padding: 0.8rem 0.95rem;
            margin-bottom: 0.8rem;
        }
        .fg-split-label strong {
            display: block;
            color: #111827;
            font-size: 1.15rem;
            line-height: 1.2;
            margin-bottom: 0.25rem;
        }
        .fg-split-label span {
            color: #4b5563;
            font-size: 0.9rem;
            line-height: 1.35;
        }
        .fg-silver {
            background: #f5f7fa;
            border: 1px solid #d7dee8;
        }
        .fg-gold {
            background: #fff7df;
            border: 1px solid #e8c766;
        }
        .fg-section-label {
            color: #6b7280;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0;
            margin: 1rem 0 0.25rem;
            text-transform: uppercase;
        }
        div[data-testid="stMetric"] {
            background: #fff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.85rem 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_dataframe(label: str, frame_loader) -> None:
    try:
        frame = frame_loader()
    except Exception as exc:  # noqa: BLE001
        st.warning(f"{label} evidence is unavailable: {exc}")
        return
    if frame.empty:
        st.info(f"{label} evidence returned no rows.")
        return
    st.dataframe(frame, hide_index=True, use_container_width=True)


def metric_value(snapshot, metric: str) -> str:
    row = snapshot[snapshot["metric"] == metric]
    if row.empty:
        return "Unavailable"
    return f"{int(row.iloc[0]['value']):,}"


def show_metric_group(snapshot, metrics: tuple[str, ...]) -> None:
    cols = st.columns(len(metrics))
    for col, metric in zip(cols, metrics):
        with col:
            st.metric(metric, metric_value(snapshot, metric))


inject_styles()

st.title("Executive Comparison")
st.markdown(
    """
    The before Genie space answers questions over the Silver catalog. The after
    Genie space answers over the graph-enriched Gold catalog. The difference is
    the set of columns available to Genie, not a new analyst workflow.
    """
)

try:
    snapshot = db.dataset_snapshot()
except Exception as exc:  # noqa: BLE001
    st.warning(f"Dataset snapshot is unavailable: {exc}")
    snapshot = None

st.markdown("### Question Pair")
pair = st.selectbox(
    "Select comparison",
    db.QUESTION_PAIRS,
    format_func=lambda item: item.title,
    label_visibility="collapsed",
)

before_col, after_col = st.columns(2)

with before_col:
    st.markdown(
        """
        <div class="fg-split-label fg-silver">
          <strong>Silver Catalog</strong>
          <span>Before Genie works from base accounts, transactions, merchants, and transfers.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if snapshot is not None:
        show_metric_group(snapshot, SILVER_METRICS)
    st.markdown('<div class="fg-section-label">Before Genie</div>', unsafe_allow_html=True)
    st.markdown(f"**Question**: {pair.before_question}")
    st.caption(pair.before_takeaway)
    st.markdown('<div class="fg-section-label">SQL Evidence</div>', unsafe_allow_html=True)
    st.markdown(f"**{pair.before_label}**")
    if pair.key not in db.PAIR_QUERY_FUNCTIONS:
        st.error(f"No SQL evidence is registered for `{pair.key}`.")
    else:
        before_fn, _ = db.PAIR_QUERY_FUNCTIONS[pair.key]
        show_dataframe("Before", before_fn)

with after_col:
    st.markdown(
        """
        <div class="fg-split-label fg-gold">
          <strong>Gold Catalog</strong>
          <span>After Genie adds graph-derived risk, community, similarity, and ring-candidate fields.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if snapshot is not None:
        show_metric_group(snapshot, GOLD_METRICS)
    st.markdown('<div class="fg-section-label">After Genie</div>', unsafe_allow_html=True)
    st.markdown(f"**Question**: {pair.after_question}")
    st.caption(pair.after_takeaway)
    st.markdown('<div class="fg-section-label">SQL Evidence</div>', unsafe_allow_html=True)
    st.markdown(f"**{pair.after_label}**")
    if pair.key not in db.PAIR_QUERY_FUNCTIONS:
        st.error(f"No SQL evidence is registered for `{pair.key}`.")
    else:
        _, after_fn = db.PAIR_QUERY_FUNCTIONS[pair.key]
        show_dataframe("After", after_fn)

st.markdown("### What This Proves")
st.success(
    "The same business interface becomes more valuable when the Lakehouse "
    "contains structural dimensions. Genie can ask ordinary SQL questions over "
    "risk tier, community, similarity, and ring-candidate fields once those "
    "signals are materialized in Gold."
)

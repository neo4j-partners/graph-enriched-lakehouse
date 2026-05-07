"""Business value views for finance stakeholders."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

import backend as db


st.set_page_config(page_title="Business Value", layout="wide")


def show_table(label: str, loader):
    try:
        frame = loader()
    except Exception as exc:  # noqa: BLE001
        st.warning(f"{label} is unavailable: {exc}")
        return None
    if frame.empty:
        st.info(f"{label} returned no rows.")
        return frame
    st.dataframe(frame, hide_index=True, use_container_width=True)
    return frame


st.title("Business Value")
st.markdown(
    """
    The after catalog turns graph signals into finance questions: where review
    workload lands, which merchants deserve attention, how much book exposure is
    tied to high-risk accounts, and whether transfer flow stays inside
    communities.
    """
)

tab_merchants, tab_workload, tab_exposure, tab_flow = st.tabs(
    ["Merchant concentration", "Review workload", "Book exposure", "Transfer flow"]
)

with tab_merchants:
    st.subheader("Merchants Overrepresented in Ring-Candidate Activity")
    frame = show_table("Merchant concentration", lambda: db.merchant_concentration_after(15))
    if frame is not None and not frame.empty:
        fig = px.bar(
            frame,
            x="merchant_name",
            y="overrepresentation_index",
            color="category",
            labels={
                "merchant_name": "Merchant",
                "overrepresentation_index": "Overrepresentation index",
                "category": "Category",
            },
        )
        fig.update_layout(xaxis_tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

with tab_workload:
    st.subheader("Regional Investigator Workload")
    before_col, after_col = st.columns(2)
    with before_col:
        st.markdown("**Before: top-transfer proxy**")
        show_table("Before workload", db.review_workload_before)
    with after_col:
        st.markdown("**After: high-risk tier**")
        frame = show_table("After workload", db.review_workload_after)
    if frame is not None and not frame.empty:
        fig = px.bar(
            frame,
            x="region",
            y="review_accounts",
            color="communities",
            labels={
                "region": "Region",
                "review_accounts": "Accounts",
                "communities": "Communities",
            },
        )
        st.plotly_chart(fig, use_container_width=True)

with tab_exposure:
    st.subheader("Book Exposure by Segment")
    before_col, after_col = st.columns(2)
    with before_col:
        st.markdown("**Before: high-transfer segment**")
        show_table("Before exposure", db.book_exposure_before)
    with after_col:
        st.markdown("**After: high-risk tier segment**")
        frame = show_table("After exposure", db.book_exposure_after)
    if frame is not None and not frame.empty:
        fig = px.bar(
            frame,
            x="region",
            y="regional_book_share_pct",
            color="segment_balance",
            labels={
                "region": "Region",
                "regional_book_share_pct": "Regional book share %",
                "segment_balance": "Segment balance",
            },
        )
        st.plotly_chart(fig, use_container_width=True)

with tab_flow:
    st.subheader("Transfer Flow Structure")
    before_col, after_col = st.columns(2)
    with before_col:
        st.markdown("**Before: repeat-pair proxy**")
        before = show_table("Before transfer flow", db.flow_structure_before)
    with after_col:
        st.markdown("**After: community membership**")
        after = show_table("After transfer flow", db.flow_structure_after)

    if after is not None and not after.empty:
        fig = px.pie(
            after,
            names="segment",
            values="transfer_volume",
            hole=0.45,
        )
        st.plotly_chart(fig, use_container_width=True)

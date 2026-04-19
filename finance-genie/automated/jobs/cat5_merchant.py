"""Category 5 — Merchant-side questions that previously had no handle.

Merchants were always in the catalog, but the BEFORE catalog had no way to
group them by the structural cohort they serve. After enrichment, merchant
questions can be asked conditionally on community membership or risk tier.
"""

QUESTIONS = [
    {
        "name": "merchant_ring_community_favorites",
        "question": (
            "Which merchants are most commonly visited by accounts in "
            "ring-candidate communities?"
        ),
    },
    {
        "name": "merchant_category_risk_tier_share",
        "question": (
            "For each merchant category, what share of transaction volume comes "
            "from accounts in the high-risk tier?"
        ),
    },
    {
        "name": "merchant_community_concentration",
        "question": (
            "Are there merchants whose customer base is disproportionately "
            "concentrated in a single community?"
        ),
    },
    {
        "name": "merchant_risk_tier_gap",
        "question": (
            "Which merchants show the largest gap between the risk-tier composition "
            "of their customer base and the risk-tier composition of the overall "
            "account population?"
        ),
    },
]

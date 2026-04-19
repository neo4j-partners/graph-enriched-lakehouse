"""Category 1 — Portfolio composition over structural segments.

Questions that ask how much of the book sits in a structurally-defined segment.
Only answerable after enrichment because the community_id and is_ring_community
columns do not exist in base tables.
"""

QUESTIONS = [
    {
        "name": "portfolio_ring_share_by_region",
        "question": (
            "What share of accounts sits in communities flagged as ring candidates, "
            "broken out by region?"
        ),
    },
    {
        "name": "portfolio_balance_by_risk_tier",
        "question": "How does total account balance split between the high and low risk tiers?",
    },
    {
        "name": "portfolio_community_size_distribution",
        "question": (
            "How many distinct communities are there, and what is the distribution "
            "of community sizes?"
        ),
    },
    {
        "name": "portfolio_intra_vs_cross_community_transfers",
        "question": (
            "What fraction of transfer volume flows between accounts in the same "
            "community versus across communities?"
        ),
    },
]

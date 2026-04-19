"""Category 3 — Rollups over already-labeled communities.

GDS produced the community labels and the ring-candidate flag. These questions
characterize the already-labeled set with the rollup metrics a business
stakeholder would request about any pre-defined segment.
"""

QUESTIONS = [
    {
        "name": "rollup_ring_candidate_total_balance",
        "question": (
            "For ring-candidate communities taken together, what is the total balance "
            "held by their members and what share of the book do they represent?"
        ),
    },
    {
        "name": "rollup_ring_candidates_by_region",
        "question": (
            "Break down the ring-candidate community set by region: how many candidates "
            "sit primarily in each region, and what is their average member count?"
        ),
    },
    {
        "name": "rollup_internal_vs_external_transfer_ratio",
        "question": (
            "For each ring-candidate community, what is the ratio of internal transfer "
            "volume between members to external transfer volume outside the community, "
            "and how does that ratio distribute across the candidate set?"
        ),
    },
    {
        "name": "rollup_internal_transfer_fraction_comparison",
        "question": (
            "For ring-candidate communities, how does their internal transfer ratio "
            "compare to non-candidate communities of similar size?"
        ),
    },
]

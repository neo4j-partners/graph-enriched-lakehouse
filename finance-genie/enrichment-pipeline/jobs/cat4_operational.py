"""Category 4 — Operational and investigator workload questions.

Once structure is a column it can drive queue and capacity questions an
operations team would ask about any segment.
"""

QUESTIONS = [
    {
        "name": "operational_review_queue_size",
        "question": (
            "How many accounts would need investigator review if the bar is high "
            "risk tier, and what is the regional breakdown of that workload?"
        ),
    },
    {
        "name": "operational_ring_concentration_by_region",
        "question": (
            "Which regions have the highest concentration of accounts in ring "
            "candidate communities per thousand accounts?"
        ),
    },
    {
        "name": "operational_ring_candidate_total_balance",
        "question": (
            "What is the total balance held in accounts assigned to ring-candidate "
            "communities, and how does it compare to total balance in the overall book?"
        ),
    },
    {
        "name": "operational_community_top_ranked_accounts",
        "question": (
            "How many accounts rank first in their community by similarity score, "
            "and how are they distributed across regions?"
        ),
    },
]

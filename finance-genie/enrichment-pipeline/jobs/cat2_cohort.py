"""Category 2 — Cohort comparisons across tiers.

Two-cohort BI comparisons where the cohort definition comes from the graph.
Questions on balance and holder age were dropped because the synthetic dataset
distributes those attributes identically between ring-member and baseline
accounts — questions that land flat were replaced with transfer-behavior and
score comparisons where the data has real signal.
"""

QUESTIONS = [
    {
        "name": "cohort_merchant_spend_mix",
        "question": (
            "How does merchant-category spending mix differ between ring-community "
            "accounts and the baseline?"
        ),
    },
    {
        "name": "cohort_internal_transfer_fraction",
        "question": (
            "For accounts in ring-candidate communities, what fraction of their "
            "transfer volume stays within the community versus flows outside it, "
            "compared to non-ring accounts?"
        ),
    },
    {
        "name": "cohort_risk_score_distribution",
        "question": (
            "How does the distribution of risk scores differ between ring-candidate "
            "and non-ring accounts?"
        ),
    },
    {
        "name": "cohort_transfer_count_comparison",
        "question": (
            "What is the average transfer count per account within ring-candidate "
            "communities versus the general account population?"
        ),
    },
]

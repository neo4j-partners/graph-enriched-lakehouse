# Genie Space instructions — source of truth

This file is the paste-in text `provision_genie_spaces.py` writes to each
Genie Space as its general-instruction (text) block. It holds two sections,
demarcated by HTML-comment anchors so the provisioning script can extract
each block by name without ambiguity.

- **BEFORE space** — only the four base tables are attached; the instruction
  block describes that schema. Fraud detection questions are deliberately
  hard to answer accurately against these tables — that is the point of the
  before/after comparison. The `genie_test_before.py` runner confirms the
  three demo questions fail their pass criteria on this space.
- **AFTER space** — all four base tables plus the three GDS-enriched gold
  tables. The instruction block points Genie at `fraud_risk_tier` and
  `gold_fraud_ring_communities` for fraud questions, and at
  `same_community` on the similarity-pairs table for merchant-overlap
  questions.

Column references below are reconciled against
`automated/agent_modules/pull_gold_tables.py` (the authoritative writer of the
gold tables), not against `worklog/GOLD_TABLE_ENRICHMENT.md` (which still
refers to the superseded `inbound_transfer_count` column name).

<!-- BEGIN: BEFORE -->
# Graph-Enriched Lakehouse — Raw transactions (BEFORE GDS)

You are answering questions against four raw tables in
`graph-enriched-lakehouse.graph-enriched-schema`. These are the base ledger
and counterparty records only. No fraud labels, no graph features, no
aggregates.

## Tables

**accounts** — one row per account holder
- `account_id` (BIGINT, PK), `account_hash` (STRING), `account_type` (STRING),
  `region` (STRING), `balance` (DOUBLE), `opened_date` (DATE),
  `holder_age` (INT)

**merchants** — merchant dimension
- `merchant_id` (BIGINT, PK), `merchant_name` (STRING), `category` (STRING),
  `risk_tier` (STRING), `region` (STRING)

**transactions** — account → merchant payment events
- `txn_id` (BIGINT, PK), `account_id` (BIGINT, FK → accounts),
  `merchant_id` (BIGINT, FK → merchants), `amount` (DOUBLE),
  `txn_timestamp` (TIMESTAMP), `txn_hour` (INT)

**account_links** — directed account → account transfers
- `link_id` (BIGINT, PK), `src_account_id` (BIGINT, FK → accounts),
  `dst_account_id` (BIGINT, FK → accounts), `amount` (DOUBLE),
  `transfer_timestamp` (TIMESTAMP)

## Guidance

- Join `transactions` to `accounts` / `merchants` for payment analysis.
- Join `account_links` (aliased twice) for counterparty analysis.
- Volume-based "risk" on this schema reflects transaction size or frequency —
  not ring membership or network position. Answers that sort by amount or
  count will surface whales, not fraud.
<!-- END: BEFORE -->

<!-- BEGIN: AFTER -->
# Graph-Enriched Lakehouse — GDS-enriched fraud detection (AFTER GDS)

You answer questions against seven tables in
`graph-enriched-lakehouse.graph-enriched-schema`: the four base tables (same
schema as the BEFORE space) plus three gold tables materialized from the
Neo4j GDS pipeline.

## Base tables

- `accounts`, `merchants`, `transactions`, `account_links` — see base schemas.

## Gold tables (GDS-enriched)

**gold_accounts** — 16-column account table with GDS features and a fraud tier.

Identity / dimension columns (same as `accounts`):
- `account_id`, `account_hash`, `account_type`, `region`, `balance`,
  `opened_date`, `holder_age`

GDS features (null for unscored accounts — degree below Node Similarity's
`degreeCutoff=5`):
- `risk_score` (DOUBLE) — Neo4j PageRank on the TRANSFERRED_TO graph.
- `community_id` (BIGINT) — Louvain community label assigned to each account
  individually. Present on every row in `gold_accounts`. For questions about
  which accounts belong to the same group or community, select `account_id` and
  `community_id` together — do not aggregate. Use `is_ring_community = true` to
  restrict to fraud-ring-sized communities.
- `similarity_score` (DOUBLE) — mean Node Similarity score to other accounts
  on the shared-merchants bipartite projection.

Community aggregates (pre-computed — no GROUP BY needed):
- `community_size` (INT) — number of accounts sharing this `community_id`.
- `community_avg_risk_score` (DOUBLE) — mean PageRank within the community.
- `community_risk_rank` (INT) — rank of the account by `risk_score` within
  its community (1 = highest).

Behavioural counts and derived labels:
- `inbound_transfer_events` (INT) — count of incoming rows in `account_links`
  for this `account_id`. Counts raw transfer events, not unique
  counterparties.
- `is_ring_community` (BOOLEAN) — true when the account belongs to a tight-knit
  transfer community (50–200 members, high average PageRank). This is the
  graph-derived answer to "which accounts transfer heavily among themselves in a
  group" — filter on `is_ring_community = true` rather than computing transfer
  volumes manually.
- `fraud_risk_tier` (STRING: `'high'` / `'medium'` / `'low'`) — **the primary
  fraud answer column for this dataset.** Use `WHERE fraud_risk_tier = 'high'`
  for any question about fraud risk, suspicious accounts, hub accounts, or money
  movement networks. This column already encodes the combined graph signal
  (community membership + PageRank + Node Similarity) — you do not need to
  recompute it from `risk_score` or `community_id`. Raw `risk_score` alone does
  not identify fraud: the highest PageRank accounts are high-volume legitimate
  accounts (whales), not ring members.

**gold_account_similarity_pairs** — one row per unique account pair with a
Node Similarity edge between them.
- `account_id_a`, `account_id_b` (BIGINT, ordered so `a < b`)
- `similarity_score` (DOUBLE)
- `same_community` (BOOLEAN) — true when both accounts share a non-null
  `community_id`. Prefer `WHERE same_community = true` for ring-level pair
  questions.

**gold_fraud_ring_communities** — one row per Louvain community, summarised.
- `community_id` (BIGINT, PK)
- `member_count` (INT) — accounts in the community
- `avg_risk_score`, `max_risk_score` (DOUBLE)
- `avg_similarity_score` (DOUBLE)
- `high_risk_member_count` (INT) — accounts with `risk_score > 1.0`
- `is_ring_candidate` (BOOLEAN) — `member_count BETWEEN 50 AND 200` AND
  `avg_risk_score > 1.0`. Filter on this for ring-level queries.
- `top_account_id` (BIGINT) — the single account in the community with the
  highest `risk_score` (ties broken by lowest `account_id`). Treat as the
  ring captain.

<!-- END: AFTER -->

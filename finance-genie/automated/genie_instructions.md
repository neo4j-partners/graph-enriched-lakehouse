# Genie Space instructions — source of truth

This file is the paste-in text `provision_genie_spaces.py` writes to each
Genie Space as its general-instruction (text) block. It holds two sections,
demarcated by HTML-comment anchors so the provisioning script can extract
each block by name without ambiguity.

Column-level descriptions live in Unity Catalog (defined in `sql/schema.sql` for
base tables and `sql/gold_schema.sql` for gold tables). Genie reads
those automatically. These text blocks provide only domain context and table
relationships — not column documentation, not query recipes.

<!-- BEGIN: BEFORE -->
# Financial Account Analytics — Transaction Data

This space covers payment and transfer activity for a financial institution.
Four tables are available in `graph-enriched-lakehouse.graph-enriched-schema`.

## Table relationships

- `accounts` → `transactions` → `merchants`: an account makes payments to merchants
- `accounts` → `account_links` → `accounts`: accounts transfer money directly to other accounts
- `transactions.account_id` joins to `accounts.account_id`
- `transactions.merchant_id` joins to `merchants.merchant_id`
- `account_links.src_account_id` and `account_links.dst_account_id` both join to `accounts.account_id`
<!-- END: BEFORE -->

<!-- BEGIN: AFTER -->
# Financial Account Analytics — Graph-Enriched Schema

This space covers the same payment and transfer data as the base schema, plus
three gold tables that add graph analytics features derived from the account
transfer network. Seven tables are available in
`graph-enriched-lakehouse.graph-enriched-schema`.

## Base tables

`accounts`, `merchants`, `transactions`, `account_links` — same as base schema.

## Gold tables

Three tables add pre-computed network analysis features:

- `gold_accounts` — per-account graph features joined to the account dimension
- `gold_account_similarity_pairs` — pairwise similarity between accounts based on shared merchant visits
- `gold_fraud_ring_communities` — per-community aggregates for communities with anomalous transfer patterns

## Table relationships

Base table joins (same as base schema):
- `transactions.account_id` → `accounts.account_id`
- `transactions.merchant_id` → `merchants.merchant_id`
- `account_links.src_account_id` and `account_links.dst_account_id` → `accounts.account_id`

Gold table joins:
- `gold_accounts.account_id` → `accounts.account_id`
- `gold_account_similarity_pairs.account_id_a` and `account_id_b` → `gold_accounts.account_id`
- `gold_fraud_ring_communities.community_id` → `gold_accounts.community_id`
<!-- END: AFTER -->

-- Base table schema for graph-on-databricks.graph-enriched-schema
--
-- Defines all five base tables with Unity Catalog column-level comments.
-- Column descriptions are the primary signal Genie uses to understand data.
--
-- Executed by upload_and_create_tables.sh before CSV data is loaded.
-- Placeholders ${catalog} and ${schema} are substituted by the shell script.
--
-- To run manually in the Databricks SQL editor, replace placeholders:
--   ${catalog} → graph-on-databricks
--   ${schema}  → graph-enriched-schema

CREATE OR REPLACE TABLE `${catalog}`.`${schema}`.accounts (
    account_id   BIGINT  NOT NULL COMMENT 'Unique account identifier (primary key)',
    account_hash STRING           COMMENT 'Anonymized account identifier derived from the original account number',
    account_type STRING           COMMENT 'Account category: checking, savings, or business',
    region       STRING           COMMENT 'Geographic region where the account was opened',
    balance      DOUBLE           COMMENT 'Current account balance in USD',
    opened_date  DATE             COMMENT 'Date the account was opened',
    holder_age   INT              COMMENT 'Age of the account holder in years'
)
USING DELTA
COMMENT 'Account dimension — one row per account holder';

CREATE OR REPLACE TABLE `${catalog}`.`${schema}`.merchants (
    merchant_id   BIGINT  NOT NULL COMMENT 'Unique merchant identifier (primary key)',
    merchant_name STRING           COMMENT 'Merchant business name',
    category      STRING           COMMENT 'Merchant business category (e.g., retail, food, entertainment)',
    region        STRING           COMMENT 'Geographic region where the merchant operates'
)
USING DELTA
COMMENT 'Merchant dimension — one row per merchant';

CREATE OR REPLACE TABLE `${catalog}`.`${schema}`.transactions (
    txn_id        BIGINT     NOT NULL COMMENT 'Unique transaction identifier (primary key)',
    account_id    BIGINT              COMMENT 'Account that initiated the payment (foreign key to accounts.account_id)',
    merchant_id   BIGINT              COMMENT 'Merchant that received the payment (foreign key to merchants.merchant_id)',
    amount        DOUBLE              COMMENT 'Transaction amount in USD',
    txn_timestamp TIMESTAMP           COMMENT 'Timestamp when the transaction occurred',
    txn_hour      INT                 COMMENT 'Hour of day (0-23) when the transaction occurred'
)
USING DELTA
COMMENT 'Transaction fact table — one row per account-to-merchant payment event';

CREATE OR REPLACE TABLE `${catalog}`.`${schema}`.account_links (
    link_id            BIGINT     NOT NULL COMMENT 'Unique transfer event identifier (primary key)',
    src_account_id     BIGINT              COMMENT 'Account that sent the transfer (foreign key to accounts.account_id)',
    dst_account_id     BIGINT              COMMENT 'Account that received the transfer (foreign key to accounts.account_id)',
    amount             DOUBLE              COMMENT 'Transfer amount in USD',
    transfer_timestamp TIMESTAMP           COMMENT 'Timestamp when the transfer occurred'
)
USING DELTA
COMMENT 'Account-to-account transfer graph — one row per directed transfer event';

CREATE OR REPLACE TABLE `${catalog}`.`${schema}`.account_labels (
    account_id BIGINT  NOT NULL COMMENT 'Account identifier (foreign key to accounts.account_id)',
    is_fraud   BOOLEAN          COMMENT 'Ground-truth fraud label: true if the account is a confirmed fraud ring member'
)
USING DELTA
COMMENT 'Ground-truth fraud labels — one row per account';

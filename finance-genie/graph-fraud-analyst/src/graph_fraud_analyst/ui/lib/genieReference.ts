// genieReference.ts
// Static UI reference content for the Analyze screen. Sample question prompts
// and the schema sidebar are presentational, not API-served, so they live next
// to the UI rather than in the typed OpenAPI client.

export interface TableInfo {
  name: string;
  rows: number;
  cols: string[];
}

export const TABLES: TableInfo[] = [
  {
    name: "fraud_signals.accounts",
    rows: 60,
    cols: [
      "account_id",
      "ring_id",
      "risk_score",
      "account_type",
      "open_date",
      "shared_device_count",
      "shared_ip_count",
    ],
  },
  {
    name: "fraud_signals.transactions",
    rows: 312,
    cols: [
      "txn_id",
      "account_id",
      "merchant_id",
      "amount",
      "txn_date",
      "txn_type",
      "is_flagged",
    ],
  },
  {
    name: "fraud_signals.merchants",
    rows: 5,
    cols: [
      "merchant_id",
      "merchant_name",
      "category",
      "state",
      "total_txn_volume",
    ],
  },
  {
    name: "fraud_signals.graph_edges",
    rows: 447,
    cols: ["source_id", "target_id", "edge_type", "weight"],
  },
];

export const SAMPLE_QUESTIONS: string[] = [
  "Which accounts have the highest risk scores?",
  "Show me all merchants linked to RING-0041",
  "Which accounts share a device with 3 or more other accounts?",
  "What is the total transaction volume per ring, ranked high to low?",
  "Are there merchants receiving funds from both rings?",
];

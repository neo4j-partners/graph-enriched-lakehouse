# Fraud Analyst Application — Design Sketch

---

## Designer Brief

**This section is written for the graphic designer. No technical background required.**

### What is this product?

This is an internal investigation tool used by financial crime analysts at banks and financial institutions. Their job is to catch coordinated fraud before it causes serious financial harm — think organized groups of people (sometimes dozens) working together to steal money by opening fake accounts, routing funds through shell businesses, or exploiting payment systems at scale.

The challenge is that these fraud networks are invisible in normal transaction reports. You can't spot them by looking at one account or one payment in isolation. The pattern only becomes visible when you map out the relationships: who shares a phone number with whom, which accounts all bought from the same obscure merchant within 48 hours, which fake identities all originated from the same IP address. Finding those hidden connections is what this tool is built for.

### Who uses this?

A **fraud analyst** — typically someone who works in a financial crimes or compliance team at a bank. They are detail-oriented, data-driven, and often under pressure to move quickly. They are not software engineers, but they are comfortable working with data and dashboards. They are used to professional, high-stakes environments. Their decisions have real consequences: flagging the wrong account wastes investigative resources; missing a real fraud ring means losses in the hundreds of thousands of dollars.

### What does the tool do — in plain terms?

The application walks the analyst through three steps:

1. **Find the suspects.** The analyst searches a map of financial relationships (like a web of connections between accounts and merchants) to find suspicious clusters — groups of accounts that seem to be operating together, individual accounts with unusually high risk scores, or accounts that sit at the center of many transactions like a hub. This is the "who looks suspicious?" step.

2. **Pull the evidence.** Once the analyst identifies the suspicious patterns worth investigating, they bring that data into a central workspace. This step is about confirming the data transferred correctly — like a detective making sure the case files are complete before the trial. The analyst sees a preview of what came in and whether everything checks out.

3. **Ask questions, get answers.** With the data loaded, the analyst can ask questions in plain English: "Which accounts share a device with three or more other accounts?" or "Are there merchants that received money from both suspicious groups?" The tool answers in plain tables and summaries. At the end, the analyst exports a report listing the specific accounts and merchants they recommend for further investigation.

### The overall feeling this product should convey

- **Serious and trustworthy.** This is a professional compliance tool, not a consumer app. It should feel like something you would find at a financial institution — clean, controlled, precise.
- **Investigative.** The user is doing detective work. There is a sense of uncovering something hidden. The progression through the three steps feels like building a case.
- **Calm under pressure.** Fraud analysts are often working fast. The design should reduce cognitive load, not add to it. No clutter, no decorative noise. Data should be easy to scan.
- **Authoritative output.** The final report needs to feel like a document that could be handed to a compliance officer or legal team. It should look credible and structured.

### Visual direction ideas

- A dark or deep-navy theme would suit the investigative, high-stakes tone, though a clean light mode with strong typographic hierarchy could work equally well.
- Network/graph imagery (nodes connected by lines, web-like structures) is the natural visual metaphor for the underlying concept — coordinated fraud rings are literally networks of people.
- Color could be used meaningfully: risk levels shown in a red/amber/green scale, selected/active items in a strong accent color, neutral background for everything else.
- The three screens should feel like distinct chapters in a workflow — each one has a clear job, and the progression from left to right (search, load, analyze) tells a story.
- Data tables are central to this product. Good table design — readable type, clear row separation, scannable column headers — matters more here than anywhere else.

---

## Background

Financial fraud increasingly operates through coordinated networks: merchants, cardholders, and accounts that appear legitimate in isolation but reveal suspicious patterns when viewed as a graph. A single transaction anomaly is noise; a ring of 40 accounts funneling money through three shell merchants is a signal.

This application gives fraud analysts a structured workflow to move from graph-level suspicion to lakehouse-backed evidence to actionable investigation targets — without requiring them to write Cypher or SQL by hand.

**Primary use case:** A fraud analyst suspects coordinated fraud activity. They surface candidate signals from Neo4j's relationship graph (fraud rings, high-risk accounts, network hubs), load the relevant subgraph data into the Databricks Lakehouse, and then query that data in natural language to produce a prioritized list of accounts and merchants warranting further investigation.

**Why the hybrid architecture matters:** Neo4j excels at finding structural patterns — ring topologies, shortest paths, centrality — that relational databases handle poorly. Databricks excels at large-scale aggregation, ML-scored risk, and governed reporting. The analyst uses each system for what it does best, with a clean handoff between them.

---

## Workflow Overview

```
 [1. Search Neo4j]  →  [2. Load to Lakehouse]  →  [3. Analyze & Report]
   Graph signals         Verify ingestion            Natural language query
   Fraud rings           Delta table preview         Genie-powered Q&A
   Risk scores           Row counts / quality        Guided by available data
   Central accounts      Schema confirmation         Sample questions
```

---

## Screen 1 — Surface Fraud Signals in Neo4j

The analyst defines what kind of pattern they are hunting. Kept intentionally minimal: one choice drives the query.

```
┌─────────────────────────────────────────────────────────────────────┐
│  SIMPLE FINANCE ANALYST                                   [Profile ▾]│
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  What are you looking for?                                           │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  ○  Fraud Rings                                              │   │
│  │     Find clusters of accounts with shared identifiers        │   │
│  │     (device, IP, email domain, phone) cycling funds          │   │
│  │                                                              │   │
│  │  ○  Risk Scores                                              │   │
│  │     Surface accounts and merchants above a risk threshold    │   │
│  │     based on graph centrality and transaction velocity       │   │
│  │                                                              │   │
│  │  ○  Central Accounts                                         │   │
│  │     Identify high-betweenness nodes — accounts that sit      │   │
│  │     on many shortest paths and may be coordinating activity  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ── Filters (optional) ───────────────────────────────────────────  │
│                                                                      │
│  Date range   [ Last 30 days          ▾]                             │
│  Min amount   [ $500                   ]   Max nodes  [ 500    ]     │
│                                                                      │
│                              [ Search Neo4j → ]                      │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  RESULTS                                                     0 rings │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  No results yet. Run a search above.                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**After search — results panel:**

```
├─────────────────────────────────────────────────────────────────────┤
│  RESULTS                                                    12 rings │
│                                                                      │
│  ┌────┬──────────────┬────────┬──────────┬────────────┬──────────┐  │
│  │    │ Ring ID      │ Nodes  │ Vol ($)  │ Shared IDs │ Risk     │  │
│  ├────┼──────────────┼────────┼──────────┼────────────┼──────────┤  │
│  │ ☑  │ RING-0041    │  38    │ $214,880 │ IP, Device │ ██████ H │  │
│  │ ☑  │ RING-0087    │  22    │  $98,320 │ Email      │ █████  H │  │
│  │ ☐  │ RING-0103    │  11    │  $41,500 │ Phone      │ ███    M │  │
│  │ ☐  │ RING-0119    │   9    │  $28,900 │ Device     │ ███    M │  │
│  │ ☐  │ RING-0204    │   6    │  $12,100 │ IP         │ █      L │  │
│  │    │  ...         │        │          │            │          │  │
│  └────┴──────────────┴────────┴──────────┴────────────┴──────────┘  │
│                                                                      │
│  2 selected                        [ Load Selected to Lakehouse → ] │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Screen 2 — Load to Lakehouse

The analyst confirms what data they are ingesting and verifies it landed correctly before moving to analysis.

```
┌─────────────────────────────────────────────────────────────────────┐
│  LOAD TO LAKEHOUSE                           ← Back to Search       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Loading 2 fraud rings into Databricks Lakehouse                    │
│  RING-0041  ·  RING-0087                                            │
│                                                                      │
│  ── Target Tables ─────────────────────────────────────────────── ──│
│                                                                      │
│  fraud_signals.accounts         fraud_signals.transactions          │
│  fraud_signals.merchants        fraud_signals.graph_edges           │
│                                                                      │
│  ── Ingestion Progress ──────────────────────────────────────────── │
│                                                                      │
│  ✓  Accounts extracted from Neo4j          60 nodes                 │
│  ✓  Merchants extracted from Neo4j          5 nodes                 │
│  ✓  Transactions extracted from Neo4j     312 relationships          │
│  ✓  Graph edges extracted                 447 edges                  │
│  ●  Writing to Delta tables...                                       │
│  ○  Verifying row counts                                             │
│  ○  Running quality checks                                           │
│                                                                      │
│  [████████████████████░░░░░░░░░░░░░]  58%                           │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  DATA PREVIEW                            (available after load)     │
│                                                                      │
│  fraud_signals.accounts                                             │
│  ┌──────────────┬──────────────┬───────────┬───────────────────┐   │
│  │ account_id   │ ring_id      │ risk_score│ first_seen        │   │
│  ├──────────────┼──────────────┼───────────┼───────────────────┤   │
│  │ ACC-100291   │ RING-0041    │    0.91   │ 2024-11-03        │   │
│  │ ACC-100302   │ RING-0041    │    0.87   │ 2024-11-05        │   │
│  │ ACC-100488   │ RING-0087    │    0.83   │ 2024-12-01        │   │
│  │  ...         │  ...         │   ...     │  ...              │   │
│  └──────────────┴──────────────┴───────────┴───────────────────┘   │
│                                                                      │
│  Quality checks                                                      │
│  ┌───────────────────────────────────┬──────────┐                  │
│  │ Check                             │ Status   │                  │
│  ├───────────────────────────────────┼──────────┤                  │
│  │ Row count matches graph extract   │ Pending  │                  │
│  │ No null account_id values         │ Pending  │                  │
│  │ risk_score in [0.0, 1.0]          │ Pending  │                  │
│  │ All ring_ids resolve to a ring    │ Pending  │                  │
│  └───────────────────────────────────┴──────────┘                  │
│                                                                      │
│                              [ Continue to Analysis → ]             │
└─────────────────────────────────────────────────────────────────────┘
```

**After load completes:**

```
│  Quality checks                                                      │
│  ┌───────────────────────────────────┬──────────┐                  │
│  │ Check                             │ Status   │                  │
│  ├───────────────────────────────────┼──────────┤                  │
│  │ Row count matches graph extract   │ ✓ Pass   │                  │
│  │ No null account_id values         │ ✓ Pass   │                  │
│  │ risk_score in [0.0, 1.0]          │ ✓ Pass   │                  │
│  │ All ring_ids resolve to a ring    │ ✓ Pass   │                  │
│  └───────────────────────────────────┴──────────┘                  │
│                                                                      │
│  60 accounts  ·  5 merchants  ·  312 transactions  ready            │
│                                                                      │
│                              [ Continue to Analysis → ]             │
```

---

## Screen 3 — Analyze & Report (Genie-Powered)

Natural language query interface backed by Genie. The left panel anchors the analyst — it shows what data is actually available and offers sample questions calibrated to that data. The right panel is the conversation.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  FRAUD ANALYSIS                                               ← Back to Load            │
├──────────────────────────────┬──────────────────────────────────────────────────────────┤
│  DATA AVAILABLE              │  GENIE ANALYSIS                                          │
│                              │                                                          │
│  fraud_signals.accounts      │  Ask a question about the loaded fraud signals.          │
│  60 rows                     │                                                          │
│  • account_id                │  ┌────────────────────────────────────────────────────┐ │
│  • ring_id                   │  │                                                    │ │
│  • risk_score                │  │                                                    │ │
│  • account_type              │  │                                                    │ │
│  • open_date                 │  │                                                    │ │
│  • shared_device_count       │  │                                                    │ │
│  • shared_ip_count           │  │                                                    │ │
│                              │  │                                                    │ │
│  fraud_signals.transactions  │  │                                                    │ │
│  312 rows                    │  │   No questions yet. Try one of the samples on      │ │
│  • txn_id                    │  │   the left, or type your own below.                │ │
│  • account_id                │  │                                                    │ │
│  • merchant_id               │  │                                                    │ │
│  • amount                    │  │                                                    │ │
│  • txn_date                  │  │                                                    │ │
│  • txn_type                  │  │                                                    │ │
│  • is_flagged                │  │                                                    │ │
│                              │  └────────────────────────────────────────────────────┘ │
│  fraud_signals.merchants     │                                                          │
│  5 rows                      │  ┌────────────────────────────────────────────────────┐ │
│  • merchant_id               │  │ Ask anything about the data...              [Ask →]│ │
│  • merchant_name             │  └────────────────────────────────────────────────────┘ │
│  • category                  │                                                          │
│  • state                     │                                                          │
│  • total_txn_volume          │                                                          │
│                              │                                                          │
│  fraud_signals.graph_edges   │                                                          │
│  447 rows                    │                                                          │
│  • source_id                 │                                                          │
│  • target_id                 │                                                          │
│  • edge_type                 │                                                          │
│  • weight                    │                                                          │
│                              │                                                          │
│  ── Sample Questions ──────  │                                                          │
│                              │                                                          │
│  [ Which accounts have the ] │                                                          │
│  [ highest risk scores?    ] │                                                          │
│                              │                                                          │
│  [ Show me all merchants   ] │                                                          │
│  [ linked to RING-0041     ] │                                                          │
│                              │                                                          │
│  [ Which accounts share a  ] │                                                          │
│  [ device with 3 or more   ] │                                                          │
│  [ other accounts?         ] │                                                          │
│                              │                                                          │
│  [ What is the total txn   ] │                                                          │
│  [ volume per ring,        ] │                                                          │
│  [ ranked high to low?     ] │                                                          │
│                              │                                                          │
│  [ Are there merchants     ] │                                                          │
│  [ receiving funds from    ] │                                                          │
│  [ both rings?             ] │                                                          │
│                              │                                                          │
└──────────────────────────────┴──────────────────────────────────────────────────────────┘
```

**After analysis — conversation with results and report panel:**

```
┌──────────────────────────────┬──────────────────────────────────────────────────────────┐
│  DATA AVAILABLE              │  GENIE ANALYSIS                                          │
│  ...                         │                                                          │
│                              │  You: Which accounts have the highest risk scores?       │
│                              │                                                          │
│                              │  Genie: Here are the top 10 accounts by risk score       │
│                              │  across your two loaded rings.                           │
│                              │                                                          │
│                              │  ┌────────────┬───────────┬───────────┬──────────────┐  │
│                              │  │ account_id │ ring_id   │risk_score │ shared_devs  │  │
│                              │  ├────────────┼───────────┼───────────┼──────────────┤  │
│                              │  │ ACC-100291 │ RING-0041 │  0.91     │  7           │  │
│                              │  │ ACC-100302 │ RING-0041 │  0.87     │  5           │  │
│                              │  │ ACC-100488 │ RING-0087 │  0.83     │  4           │  │
│                              │  │ ACC-100571 │ RING-0041 │  0.81     │  6           │  │
│                              │  │  ...       │  ...      │  ...      │  ...         │  │
│                              │  └────────────┴───────────┴───────────┴──────────────┘  │
│                              │                                                          │
│                              │  ACC-100291 and ACC-100571 both share 5+ devices and    │
│                              │  appear in 38% of RING-0041 transactions. Consider      │
│                              │  them priority targets.                                  │
│                              │                                                          │
│                              │  ─────────────────────────────────────────────────────  │
│                              │                                                          │
│                              │  You: Are there merchants receiving funds from both      │
│                              │  rings?                                                  │
│                              │                                                          │
│                              │  Genie: Yes — 2 merchants appear in transactions         │
│                              │  linked to both RING-0041 and RING-0087.                 │
│                              │                                                          │
│                              │  ┌─────────────────┬──────────────┬──────────────────┐  │
│                              │  │ merchant_name   │ category     │ total_vol        │  │
│                              │  ├─────────────────┼──────────────┼──────────────────┤  │
│                              │  │ QuickPay LLC    │ Money Svc    │  $178,400        │  │
│                              │  │ Meridian Store  │ Retail       │   $54,200        │  │
│                              │  └─────────────────┴──────────────┴──────────────────┘  │
│                              │                                                          │
│                              │  ┌────────────────────────────────────────────────────┐ │
│                              │  │ Ask anything about the data...              [Ask →]│ │
│                              │  └────────────────────────────────────────────────────┘ │
│                              │                                                          │
│                              │                      [ Export Report ▾ ]                │
└──────────────────────────────┴──────────────────────────────────────────────────────────┘
```

**Export Report — output:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  INVESTIGATION REPORT                            2026-05-10  14:32  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SOURCE RINGS ANALYZED                                               │
│  RING-0041 (38 accounts)  ·  RING-0087 (22 accounts)                │
│                                                                      │
│  PRIORITY ACCOUNTS FOR INVESTIGATION                                 │
│  ┌────────────┬───────────┬───────────┬──────────────────────────┐  │
│  │ account_id │ ring_id   │risk_score │ Flag                     │  │
│  ├────────────┼───────────┼───────────┼──────────────────────────┤  │
│  │ ACC-100291 │ RING-0041 │  0.91     │ High device share        │  │
│  │ ACC-100571 │ RING-0041 │  0.81     │ High device share        │  │
│  │ ACC-100488 │ RING-0087 │  0.83     │ Cross-ring merchant link │  │
│  └────────────┴───────────┴───────────┴──────────────────────────┘  │
│                                                                      │
│  PRIORITY MERCHANTS FOR INVESTIGATION                                │
│  ┌─────────────────┬──────────────┬──────────────┬──────────────┐  │
│  │ merchant_name   │ category     │ total_vol    │ Flag         │  │
│  ├─────────────────┼──────────────┼──────────────┼──────────────┤  │
│  │ QuickPay LLC    │ Money Svc    │  $178,400    │ Both rings   │  │
│  │ Meridian Store  │ Retail       │   $54,200    │ Both rings   │  │
│  └─────────────────┴──────────────┴──────────────┴──────────────┘  │
│                                                                      │
│  ANALYST NOTES                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  QuickPay LLC is a money services business with no physical  │   │
│  │  location. Recommend SAR filing review.                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│                  [ Download PDF ]   [ Save to Lakehouse ]            │
└─────────────────────────────────────────────────────────────────────┘
```

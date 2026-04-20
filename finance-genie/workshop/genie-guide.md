# Genie Demo Guide

Questions to copy-paste into Genie during the live demo, with brief notes on what each one shows.

---

## BEFORE: Base Silver Tables

These questions run against the base catalog — no graph enrichment yet.

---

### Warm-Up

> Confirms Genie is working and can handle straightforward aggregations. Good opener to establish the baseline before things get interesting.

```
What are the top 10 accounts by total amount spent across all merchants?
```

---

### Analytics Challenge

> Shows Genie handling a harder tabular question — joining two tables and applying a conditional aggregate. Night transactions (hours 0–5) are a known fraud signal. This answer is possible because both dimensions (spend and time-of-day) already exist as columns. Sets up the contrast with the structural questions that follow.

```
Which accounts have both above-average total spend and a night transaction ratio above 20%? Show the top 15 by total spend with their night ratio and account balance.
```

---

### Structural Gap: Hub Detection

> The point where Genie hits its limit — not because Genie is broken, but because the information doesn't exist in the data yet. There's no `risk_score` column, so Genie can only rank by raw transaction volume, which surfaces high-volume legitimate accounts alongside ring members with no way to tell them apart. The miss is the message.

```
Are there accounts that seem to be the hub of a money movement network that are potentially fraudulent?
```

---

### Structural Gap: Community Structure

> Asks Genie to find groups of accounts that transfer money heavily among themselves — the definition of a fraud ring. Without community labels as columns, Genie can only aggregate raw transfer counts, which mixes legitimate high-volume clusters with actual rings and returns no meaningful structure.

```
Find groups of accounts transferring money heavily among themselves.
```

---

### Structural Gap: Merchant Overlap

> Asks which pairs of accounts share the most merchants in common — a co-visitation signal used to surface coordinated activity. Without a similarity score or community column, Genie can attempt the join but can't separate same-ring pairs from coincidental overlap. Expected to return low precision against the fraud ring ground truth.

```
Which pairs of accounts have visited the most merchants in common?
```

---

## AFTER: Graph-Enriched Gold Tables

The pipeline has run. `community_id`, `fraud_risk_tier`, `risk_score`, and `similarity_score` are now ordinary columns. Genie's capability hasn't changed — the catalog has.

---

### 1. Portfolio Composition

Questions about how the book breaks down across structurally-defined segments. Only answerable after enrichment because `community_id` and `is_ring_community` don't exist in the base tables.

---

#### Ring share by region

> Asks what percentage of the book sits in ring-candidate communities, broken out by region. The same question was structurally impossible before enrichment — now it's a standard GROUP BY.

```
What share of accounts sits in communities flagged as ring candidates, broken out by region?
```

---

#### Balance by risk tier

> Splits total account balance between high and low risk tiers. Shows the dollar weight of the structural signal — useful for risk officers who need to know how much capital is exposed.

```
How does total account balance split between the high and low risk tiers?
```

---

#### Community size distribution

> Asks how many communities exist and how their sizes spread. Sets up intuition for how fragmented or concentrated the ring activity is across the book.

```
How many distinct communities are there, and what is the distribution of community sizes?
```

---

#### Intra- vs cross-community transfer volume

> Asks what fraction of transfer volume flows between accounts in the same community versus across communities. A high intra-community ratio is a structural marker of ring behavior — money cycling within a closed group.

```
What fraction of transfer volume flows between accounts in the same community versus across communities?
```

---

### 2. Cohort Comparisons

Two-cohort BI comparisons where the cohort definition comes from the graph. These questions require `community_id` or `fraud_risk_tier` as a filter column.

---

#### Merchant-category spending mix

> Compares merchant-category spending patterns between ring-community accounts and the rest. Fraud rings often concentrate at a narrow set of merchant types. This split only exists now that `community_id` is a column.

```
How does merchant-category spending mix differ between ring-community accounts and the baseline?
```

---

#### Internal transfer fraction

> Asks what share of ring-account transfer volume stays inside the community versus flows out, compared to normal accounts. High internal retention is a hallmark of money-cycling rings and should stand out sharply against the baseline.

```
For accounts in ring-candidate communities, what fraction of their transfer volume stays within the community versus flows outside it, compared to non-ring accounts?
```

---

#### Risk score distribution

> Compares the spread of risk scores between ring-candidate and non-ring accounts. A good visual for showing that the graph signal produces a cleanly separated distribution — not a marginal lift.

```
How does the distribution of risk scores differ between ring-candidate and non-ring accounts?
```

---

#### Transfer count comparison

> Compares average transfer count per account between ring members and the general population. Shows whether ring accounts are more or less active by transaction volume — useful context for investigators sizing case complexity.

```
What is the average transfer count per account within ring-candidate communities versus the general account population?
```

---

### 3. Community Rollups

Rollup questions over the already-labeled ring-candidate set — the same BI aggregations a stakeholder would ask about any pre-defined segment.

---

#### Total balance in ring-candidate communities

> A dollar-exposure question: how much total balance is held by ring-candidate community members, and what fraction of the book does that represent? The kind of number a risk officer or regulator wants on a dashboard.

```
For ring-candidate communities taken together, what is the total balance held by their members and what share of the book do they represent?
```

---

#### Ring candidates by region

> Breaks down where ring-candidate communities are concentrated geographically, including average member count per region. Useful for prioritizing regional investigation teams.

```
Break down the ring-candidate community set by region: how many candidates sit primarily in each region, and what is their average member count?
```

---

#### Internal vs external transfer ratio per community

> For each ring-candidate community individually, shows the ratio of money flowing within the community to money flowing out. Communities with very high internal ratios are the strongest candidates for active cycling behavior.

```
For each ring-candidate community, what is the ratio of internal transfer volume between members to external transfer volume outside the community, and how does that ratio distribute across the candidate set?
```

---

#### Internal transfer ratio vs non-candidates of similar size

> Controls for community size by comparing ring-candidate internal transfer ratios against non-candidate communities of similar size. Isolates the structural signal from the trivial effect that larger communities transfer more among themselves.

```
For ring-candidate communities, how does their internal transfer ratio compare to non-candidate communities of similar size?
```

---

### 4. Operational Workload

Capacity and queue questions an investigations team would ask once structural risk tiers are filterable columns.

---

#### Review queue size by region

> Staffing question: if investigations reviews every high-risk-tier account, how many cases does that create and where are they? Lets a manager size the queue and assign investigators by region before a backlog builds.

```
How many accounts would need investigator review if the bar is high risk tier, and what is the regional breakdown of that workload?
```

---

#### Ring concentration per thousand accounts by region

> Normalizes ring exposure by region size — a raw count would favor large regions. Per-thousand concentration surfaces regions that are disproportionately exposed, regardless of how many total accounts they hold.

```
Which regions have the highest concentration of accounts in ring candidate communities per thousand accounts?
```

---

#### Total balance in ring-candidate accounts vs overall book

> Combines portfolio exposure with the operational framing: how much capital is locked inside ring-candidate accounts, and what share of the total book does that represent? Supports escalation conversations where a dollar figure is needed.

```
What is the total balance held in accounts assigned to ring-candidate communities, and how does it compare to total balance in the overall book?
```

---

#### Top-ranked accounts per community

> Counts accounts that rank first in their community by similarity score and shows their regional distribution. These are the highest-centrality nodes in each ring — the accounts an investigator would prioritize.

```
How many accounts rank first in their community by similarity score, and how are they distributed across regions?
```

---

### 5. Merchant-Side Analysis

Merchant questions that previously had no structural handle. After enrichment, merchant activity can be conditioned on community membership or risk tier.

---

#### Most-visited merchants by ring-community accounts

> Flips the lens from accounts to merchants. Fraud rings often share anchor merchants — for laundering, false receipts, or coordinated activity. Surfacing those merchants lets compliance investigate the merchant relationship, not just the accounts.

```
Which merchants are most commonly visited by accounts in ring-candidate communities?
```

---

#### Transaction volume share from high-risk accounts by merchant category

> For each merchant category, asks what fraction of transaction volume comes from high-risk-tier accounts. Categories with a high share may warrant merchant-level due diligence or enhanced monitoring.

```
For each merchant category, what share of transaction volume comes from accounts in the high-risk tier?
```

---

#### Merchants with customer base concentrated in a single community

> Finds merchants whose customers are unusually clustered into one community. A merchant serving a single tight community is a red flag — it may be an anchor point for a ring rather than a normal retail or service business.

```
Are there merchants whose customer base is disproportionately concentrated in a single community?
```

---

#### Merchants with the largest risk-tier gap vs the overall population

> Compares each merchant's risk-tier customer mix against the book-wide baseline. A large gap means that merchant is serving a significantly riskier (or safer) customer profile than expected — useful for targeted merchant risk reviews.

```
Which merchants show the largest gap between the risk-tier composition of their customer base and the risk-tier composition of the overall account population?
```

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

> Shows Genie handling a harder tabular question — joining two tables and applying a conditional aggregate. Night transactions (hours 0–5) are a known fraud signal. This answer is possible because both dimensions (spend and time-of-day) already exist as columns. Sets up the baseline before the anchor questions run.

```
Which accounts have both above-average total spend and a night transaction ratio above 20%? Show the top 15 by total spend with their night ratio and account balance.
```

---

### Anchor: Merchant Favorites

> The primary anchor question. Asks which merchants high-volume accounts visit most. Volume is the only proxy for ring membership on the base catalog — there is no community column. The result is a popularity ranking that sounds like a real answer. Hold on this result; the after version of this question returns a structurally different list.

```
Which merchants are most commonly visited by accounts with the highest total transaction volume?
```

---

### Anchor: Book Share

> Best-available estimate of how much capital sits in suspicious accounts, using volume decile as a proxy for ring membership. The after version asks the same thing against graph-defined ring candidates.

```
For the top 10% of accounts by transfer volume, what is the total balance held and what share of the book do they represent?
```

---

### Anchor: Investigator Review Queue

> Volume cutoff as a stand-in for a risk tier. Shows what a queue sizing looks like when the threshold is a transaction count, not a structural signal.

```
How many accounts are in the top 10% by transfer volume, and what is the regional breakdown?
```

---

### Anchor: Internal vs External Transfer Ratio

> Repeat-transfer frequency as a proxy for community insularity. The after version measures the same thing against actual community membership.

```
What fraction of total transfer volume flows between accounts that have transacted with each other more than five times, versus accounts with no prior relationship?
```

---

### Anchor: Merchant Community Concentration

> Co-transaction frequency as a proxy for community cohesion. The after version asks which merchants serve a customer base concentrated in a single graph-defined community.

```
Are there merchants where the majority of transaction volume comes from accounts that also transact heavily with each other?
```

---

## AFTER: Graph-Enriched Gold Tables

The pipeline has run. `community_id`, `fraud_risk_tier`, `risk_score`, and `similarity_score` are now ordinary columns. Genie's capability hasn't changed — the catalog has.

Start with the anchor question. It is the same question that opened the BEFORE section, now asked against the enriched catalog. Show both results side by side and let the gap land before moving on.

---

### Anchor: Merchant Favorites

> Closes the before/after pair. The before answer was a popularity ranking of merchants among high-volume accounts. This answer is a different list — the merchants where ring-candidate community members cluster disproportionately. The gap is the demo's central argument.

```
Which merchants are most commonly visited by accounts in ring-candidate communities?
```

---

### Anchor: Book Share

> Closes the before/after pair for the book share question. Before: total balance held by the top 10% by transfer volume. After: total balance held by ring-candidate community members and their share of the book. Same shape, structurally different segment definition.

```
For ring-candidate communities taken together, what is the total balance held by their members and what share of the book do they represent?
```

---

### Anchor: Investigator Review Queue

> Closes the before/after pair for the review queue question. Before: accounts in the top 10% by transfer volume with a regional breakdown. After: accounts in the high risk tier with the same regional breakdown. A risk manager sees immediately that volume cutoff and structural tier return different counts.

```
How many accounts would need investigator review if the bar is high risk tier, and what is the regional breakdown of that workload?
```

---

### Anchor: Internal vs External Transfer Ratio

> Closes the before/after pair for the transfer ratio question. Before: fraction of volume between repeat-transfer pairs vs. unrelated pairs. After: per-community internal vs. external transfer ratio measured against actual community membership.

```
For each ring-candidate community, what is the ratio of internal transfer volume between members to external transfer volume outside the community?
```

---

### Anchor: Merchant Community Concentration

> Closes the before/after pair for the merchant concentration question. Before: merchants where volume comes from mutually active accounts. After: merchants whose customer base is disproportionately concentrated in a single community.

```
Are there merchants whose customer base is disproportionately concentrated in a single community?
```

---

### Fill-In / Q&A

Additional questions for extended demos or Q&A. All require the enriched Gold tables.

---

#### Ring share by region

> What percentage of the book sits in ring-candidate communities, broken out by region.

```
What share of accounts sits in communities flagged as ring candidates, broken out by region?
```

---

#### Balance by risk tier

> Splits total account balance between high and low risk tiers. Shows the dollar weight of the structural signal.

```
How does total account balance split between the high and low risk tiers?
```

---

#### Community size distribution

```
How many distinct communities are there, and what is the distribution of community sizes?
```

---

#### Intra- vs cross-community transfer volume

```
What fraction of transfer volume flows between accounts in the same community versus across communities?
```

---

#### Merchant-category spending mix by cohort

```
How does merchant-category spending mix differ between ring-community accounts and the baseline?
```

---

#### Internal transfer fraction vs baseline

```
For accounts in ring-candidate communities, what fraction of their transfer volume stays within the community versus flows outside it, compared to non-ring accounts?
```

---

#### Risk score distribution

```
How does the distribution of risk scores differ between ring-candidate and non-ring accounts?
```

---

#### Transfer count cohort comparison

```
What is the average transfer count per account within ring-candidate communities versus the general account population?
```

---

#### Ring candidates by region

```
Break down the ring-candidate community set by region: how many candidates sit primarily in each region, and what is their average member count?
```

---

#### Internal vs external ratio vs non-candidates of similar size

```
For ring-candidate communities, how does their internal transfer ratio compare to non-candidate communities of similar size?
```

---

#### Ring concentration per thousand accounts by region

```
Which regions have the highest concentration of accounts in ring candidate communities per thousand accounts?
```

---

#### Top-ranked accounts per community

```
How many accounts rank first in their community by similarity score, and how are they distributed across regions?
```

---

#### Transaction volume share from high-risk accounts by merchant category

```
For each merchant category, what share of transaction volume comes from accounts in the high-risk tier?
```

---

#### Merchants with the largest risk-tier gap vs the overall population

```
Which merchants show the largest gap between the risk-tier composition of their customer base and the risk-tier composition of the overall account population?
```

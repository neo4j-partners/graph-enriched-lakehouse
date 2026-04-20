---
marp: true
theme: default
paginate: true
---

<style>
section {
  --marp-auto-scaling-code: false;
}

li {
  opacity: 1 !important;
  animation: none !important;
  visibility: visible !important;
}

.marp-fragment {
  opacity: 1 !important;
  visibility: visible !important;
}

ul > li,
ol > li {
  opacity: 1 !important;
}
</style>

# Graph-Enriched Lakehouse

Combining Databricks Genie with Neo4j Graph Data Science

<!--
One-line argument: financial crime is a network problem, the row
is the wrong unit of analysis, and we close that gap by running
Neo4j GDS as a silver-to-gold enrichment stage in front of
Databricks Genie.
-->

---

## What This Talk Covers

1. **The problem.** Fraud rings are network patterns; row-level analytics cannot see them
2. **The graph advantage.** Why graph databases surface what SQL cannot
3. **GDS as the enrichment engine.** Three algorithms, three structural dimensions written to Delta
4. **The pipeline.** How graph intelligence lands in the lakehouse
5. **What Genie unlocks.** Question classes that open up on enriched data
6. **Where it applies.** The general pattern beyond fraud rings

<!--
Short agenda. The audience gets oriented in ten seconds and you
get to point at the BEFORE/AFTER as the demo anchor. Everything
else is scaffolding around that single comparison.
-->

---

## Financial Crime Is a Network Problem

- **Criminals organize, coordinate, and move money in networks.** The gap in most fraud systems is not the rules
- **The gap is the unit of analysis:** rules fire against individual transactions, but fraud rings operate as connected patterns across dozens of accounts and thousands of transactions
- **The individual event looks clean.** The connected pattern does not
- **Result:** coordinated schemes evade detection while false-positive rates commonly run into the high double digits across published industry surveys

<!--
The last bullet is the payload but say it carefully. "Above 90%"
is a widely-cited figure but sourcing it mid-deck slows the
story. "High double digits across published industry surveys" is
defensible without citation and still makes the point: the
baseline is broken, and it is broken because the unit of
analysis is wrong.
-->

---

## A Fraud Ring Is a Subgraph

- **Finding a ring means finding the shape:** a cluster of accounts moving money densely among themselves
- **The pattern appears anywhere in the network,** without knowing in advance which accounts to start from
- **A fraud ring is not a property of any individual transaction.** It is the pattern of connections between accounts
- **No row-level aggregation can produce a network property**

<!--
A ring is a shape, not a row. You cannot reach it by summing
columns or joining tables. Sets up the next slide, which names
the data structure that can represent and traverse those
connections efficiently.
-->

---

## Why a Graph Database

- **A graph database is the only data store** where you can describe a pattern, a subgraph shape, and find every instance efficiently, without a predetermined starting point
- **A traditional database needs a starting point.** It needs a specific account ID or customer number to begin a search
- **A graph database needs only a description of the pattern,** and finds every place that pattern exists in the network
- **The graph provides the data structure and traversal capability.** Detection comes from the queries written against it
- **The question for an analytics team on Databricks:** how do you bring that graph intelligence into the lakehouse you already operate, without rebuilding the analytics stack around a new query layer?

<!--
The pivot slide. Traditional databases are point-lookup machines;
graph databases are pattern-matching machines. The closing bullet
is the bridge to the rest of the talk: we are not rebuilding the
analytics stack, we are landing graph intelligence in the
lakehouse as enriched Delta columns.
-->

---

## What Genie Excels At

- **High-quality text-to-SQL translator** over Delta tables: aggregation, grouping, filtering, ranking, top-N, cohort comparisons, time-series rollups
- **BEFORE the demo space:** Genie handles account balances, transfer volumes, merchant categories, regional activity without difficulty
- **That is the baseline that matters:** Genie doing its designed job well on the catalog the customer already runs
- **Genie's capability does not change after enrichment.** What changes is the set of dimensions it can group by, filter on, and compare across

<!--
Do not damn Genie with the structural contrast. The AFTER demo
does not make Genie better; it gives Genie new dimensions to
operate over. That framing matters. Customers evaluating Genie
on its merits need to hear it is working as designed.
-->

---

## What Falls Outside Genie on Base Silver

- **Structural questions live in network topology,** not in the rows of a table
- **"Which accounts are central in the transfer network?"** No SQL aggregation computes eigenvector centrality
- **"Which accounts form tightly-interconnected communities?"** No GROUP BY groups by interaction density
- **"Which accounts route through the same merchants?"** No join computes Jaccard overlap of neighborhood sets
- **This is not a test of Genie.** It is a test of whether the answer exists in the tables at all. Against base Silver, it does not

<!--
The setup for the next slide. Structural answers do not live in
the Silver tables. But that is not where the story ends. The
harder problem is what Genie does when it is asked them anyway.
-->

---

## The Harder Problem: Confident Wrong Answers

- **Non-deterministic SQL shape is the visible variance.** The deeper problem is harder to see during a demo
- **On structural-discovery questions, Genie answers with full confidence, and returns wrong answers.** Not wrong SQL. Wrong answers
- **Example:** "Are there accounts that seem to be hubs of a money-movement network?" Genie ranks by transfer volume, count, or balance and returns an authoritative-looking list
- **The list is wrong** because transfer volume is not network centrality. The question asks for structural position in a graph; the table contains only row-level aggregates
- **Precision and recall collapse.** Proxy columns correlate loosely with centrality but do not measure it. Fraud captains route volume through structure, not mass. The actual hubs are often missed entirely

<!--
The hardest thing to convey in a demo is what analysts cannot
see. Non-deterministic SQL is visible. The query shape changed,
the chart title moved. Confident wrong answers are invisible.
A ranked list comes back, the analyst acts on it. The issue is
not bad SQL. The issue is that transfer volume and network
centrality are different quantities, and flat rows cannot convert
one into the other. This is the motivation for enrichment.
-->

---

## What GDS Excels At

- **GDS runs inside the graph database** and operates on the network as a whole rather than on individual rows
- **Output is deterministic given a fixed graph projection.** Same projection, same scores, every time
- **Five algorithm families:** centrality, community detection, similarity, pathfinding, node embeddings. This pipeline uses three

<!--
Keep this slide general. The next three slides each cover one
algorithm in detail; this one sets the category and the
reproducibility property. That reproducibility matters when
scores become columns in a catalog that a non-deterministic
translator queries.
-->

---

## PageRank → `risk_score`

- **Eigenvector centrality over the account-to-account transfer graph**
- **Measures structural position, not local counts.** An account with ten connections to highly-connected accounts ranks higher than one with fifty connections to peripheral accounts
- **Output:** one float per node representing centrality in the transfer network
- **On the demo dataset:** the fraud population averages **3.65×** the centrality of non-fraud accounts

<!--
This is exactly the quantity that proxies like transfer volume
approximate badly. Ring captains route volume through structure,
so PageRank surfaces them even when their raw throughput looks
normal. 3.65× on the demo is the measured separation.
-->

---

## Louvain → `community_id` / `fraud_risk_tier`

- **Modularity-optimal community partition.** Groups accounts into communities that maximize within-community edge density relative to a random baseline
- **Ignores attribute labels entirely.** Two merchants in different industries and different regions land in the same community if their transaction flows are tightly interwoven
- **Output:** one integer per node for community membership. `fraud_risk_tier` is derived from membership: accounts in ring-candidate communities land in the high tier
- **On the demo dataset:** each of the ten synthetic rings lands in its own community with **100% ring coverage**; average community purity is 70%

<!--
Louvain partitions by behavior, not by attributes. The 70%
purity number is honest: each ring-candidate community holds
~100 ring members and ~44 non-ring accounts absorbed by the
modularity objective. That is a Louvain tradeoff, not a GDS
failure. Worth naming directly if the audience pushes on
false positives.

Note fraud_risk_tier is a derived column, not a direct GDS
output. Worth calling out so the architecture diagram makes
sense two slides later.
-->

---

## Node Similarity → `similarity_score`

- **Jaccard overlap of shared-merchant sets,** computed over the bipartite account-merchant transaction graph
- **Two accounts that never transacted directly** can score high on similarity if they route through the same merchants
- **Output:** one float per node pair representing structural overlap
- **On the demo dataset:** fraud ring members score **1.98×** higher than the non-fraud population on average
- **Degree cutoff:** accounts with fewer than five unique merchant visits are excluded; 3.2% of ring members fall below

<!--
The "shared neighborhood" question. Ring members visit anchor
merchants at elevated rates, which produces the Jaccard
separation. The degree cutoff is the honest caveat: accounts
that barely interact get excluded.
-->

---

## The Enrichment Pipeline

- **Load:** Spark Connector reads Silver tables from Unity Catalog and loads account + transaction records into Neo4j Aura **as a property graph**
- **Compute:** GDS runs PageRank, Louvain, Node Similarity against the full network
- **Enrich:** Pipeline writes results back to the Gold layer as plain Delta columns: `risk_score`, `community_id`, `similarity_score`, plus derived `fraud_risk_tier`
- **Query:** Genie queries enriched Gold tables directly, treating graph-derived columns as ordinary dimensions

<!--
Four steps. Structural analysis runs once per pipeline cycle;
every downstream consumer reads the results as columns. The
graph analysis is invisible to the query layer.
-->

---

## Architecture at a Glance

```
Unity Catalog Silver          Neo4j Aura + GDS               Unity Catalog Gold
+-------------------+         +-------------------+          +-------------------+
| accounts          |         | PageRank          |          | risk_score        |
| transfers         |--load-->| Louvain           |--write-->| community_id      |
| merchants         |         | Node Similarity   |          | similarity_score  |
| transactions      |         | property graph    |          | fraud_risk_tier*  |
+-------------------+         +-------------------+          +-------------------+
                                                                      |
                                                             * derived from
                                                               community_id     |
                                                                                v
                                                             +-------------------+
                                                             | Databricks Genie  |
                                                             | text-to-SQL       |
                                                             +-------------------+
```

- **The graph and the warehouse are connected entirely through enriched Delta tables.** No live query path between them

<!--
The asterisk on fraud_risk_tier is deliberate. Three algorithms
produce three direct outputs; the tier is a derived categorical
that makes downstream SQL cleaner. Call it out so the column
count does not confuse anyone.

The no-live-query property is the architectural commitment that
lets security review, MRM, and platform teams sign off on the
pattern. Nothing in the graph reaches production queries except
what the pipeline has already materialized to Gold.
-->

---

## BEFORE / AFTER: One Question, Two Catalogs

**Analyst question:** *"Which accounts look like hubs of a money-movement network?"*

| | BEFORE, on base Silver | AFTER, on enriched Gold |
|---|---|---|
| **Column Genie reaches for** | `SUM(transfer_amount)` | `risk_score`, written by PageRank |
| **What is actually measured** | Transaction throughput | Eigenvector centrality |
| **Result set** | High-throughput accounts: payroll, payment processors, corporate treasuries | Actual structural hubs, including ring captains |
| **Precision / recall** | Low; the proxy correlates loosely with centrality | Recovers fully: correct quantity, correct retrieval |
| **Analyst experience** | Confident, authoritative-looking, wrong | Consistent run over run |

<!--
This is the anchor slide of the talk. One question, two
catalogs, two fundamentally different answers. The BEFORE column
is what Genie returns against base Silver today, and it will
look plausible. The AFTER column is what the same question
returns after enrichment.

The key tell is the "Column Genie reaches for" row. It is not
that Genie fails; Genie does exactly what a text-to-SQL engine
should do. The column inventory determined the answer. Change
the inventory, change the answer.

Practical demo tip: on the live system, run the BEFORE query
and the AFTER query side by side and screenshot both into this
slide before presenting.
-->

---

## Deterministic Foundation, Non-Deterministic Translation

- **GDS outputs are reproducible** given a fixed projection. Same projection, same scores, every time
- **Genie's text-to-SQL translation is non-deterministic.** The same question can generate different SQL shapes across runs: `RANK()=1` one time, `LIMIT 100` the next, `PERCENTILE` the time after that
- **That variance is how text-to-SQL works.** Fighting it by pinning the model is a losing effort
- **The fix is underneath, not around.** Put the signal in deterministic columns produced upstream. Variance can only permute *how* the signal is presented, never *whether* it exists
- **Consequence:** an analyst-facing experience that behaves consistently run over run, without requiring Genie itself to be deterministic

<!--
This is the architectural claim that answers "can we trust
Genie?" You do not need a deterministic LLM. You need a
deterministic column inventory underneath a non-deterministic
translation layer. The LLM rewrites the SQL shape on every run;
the underlying answer does not change because the columns it is
generating SQL against do not change.

This also closes the loop from the Confident Wrong Answers
slide earlier. That was about the absence of the right column;
this is about what the right column buys you once it exists.
-->

---

## What the Enriched Catalog Unlocks

- **Structural segments:** `community_id`, `fraud_risk_tier`. Categorical labels that behave like any warehouse dimension, but the label comes from network topology, not a row-level attribute
- **Structural scores:** `risk_score`, `similarity_score`. Continuous features that can be bucketed, thresholded, averaged, or ranked like any numeric column
- **Community-level aggregates:** `gold_fraud_ring_communities` pre-joins structure to account attributes, so Genie can answer at the community grain without reconstructing membership itself
- **Every classic BI question over a segment** becomes available over a segment that is structurally defined. The SQL shapes are standard. The dimensions are new

<!--
Frame it as dimensions, not capabilities. Genie's SQL vocabulary
did not grow; the column inventory did. Three scalar columns
plus a pre-joined community table, and classic BI starts
producing answers that were unreachable before.
-->

---

## Retrieval Is Correct; Interpretation Has a Layer

| Question type | Example | What Genie returns |
|---|---|---|
| **Aggregate over a structural segment** | "How does avg risk score compare between tiers?" | Self-explanatory: a clean GROUP BY / AVG |
| **Retrieve structural rank directly** | "Which accounts are most structurally central?" | Correct retrieval of `risk_score` DESC, no proxy |

- **After enrichment, both question types return the correct quantity.** The SQL and the values are right
- **The second type carries an interpretation layer** the first does not. The top-`risk_score` accounts may sit in the large background community, not in a ring-candidate community, because PageRank measures centrality and Louvain measures community, and they are different things
- **Rule of thumb for the demo:** favor aggregate-over-segment questions on stage. They require no graph-theory primer to interpret. Structural-rank questions are correct but invite the "why aren't these in the ring?" follow-up

<!--
Reconciles with the earlier slide: retrieval is correct; the
interpretation nuance is that PageRank and Louvain measure
different things, and a high-PageRank account in a benign
community is not a contradiction; it is the two measures
doing their jobs. The demo stays on the first row because it
plays cleanly. The second row is demoable but requires the
presenter to narrate the interpretation.
-->

---

## AFTER Demo: Five Question Classes Unlocked

1. **Portfolio composition over structural segments:** share of accounts in ring-candidate communities, balance split across risk tiers, community-size distribution
2. **Cohort comparisons across tiers:** balance, age, transaction count, regional mix, merchant-category spending, high vs. low tier
3. **Rollups over ring-candidate communities:** total balance, regional breakdown, internal-vs-external transfer ratio
4. **Operational and investigator workload:** review queue sizing, regional concentration, exposure rollups
5. **Merchant-side questions that had no handle before:** merchants serving ring communities, tier composition of merchant customer bases

<!--
One slide covers what five slides used to. The structure is
still visible. Each class corresponds to a question family an
analyst already knows how to ask, but the audience gets the
scope in under a minute. Pair with the next slide for concrete
examples.
-->

---

## One Question from Each Class

- **Composition:** *What share of accounts sits in ring-candidate communities, by region?*
- **Cohort:** *How do balance, age, and transaction count compare between the high-risk and low-risk tiers?*
- **Rollup:** *For each ring-candidate community, what is the ratio of internal transfers to external transfers?*
- **Workload:** *How many accounts need investigator review if the bar is the high-risk tier, and what is the regional breakdown?*
- **Merchant:** *Which merchants are most commonly visited by accounts in ring-candidate communities?*

<!--
Pick three of these for the live portion. Composition and
cohort are the safest plays. Standard BI shapes over a new
dimension, clean bar charts, no interpretation layer. Rollup
and workload play well to ops and audit audiences. Merchant is
the "oh, this opens new investigations" moment.
-->

---

## Where This Pattern Applies

- **Fraud-ring surfacing:** tight-community trading, shared merchant preferences that do not fit the background distribution
- **Entity resolution:** collapsing customer, device, and household records that refer to the same real-world entity based on shared attributes and topology
- **Supplier-network risk:** tiers of supplier exposure, single points of failure, concentrations of risk in multi-tier supply graphs
- **Recommendation structure:** communities of users, products, or content with shared consumption patterns as features for downstream recommenders
- **Compliance network review:** counterparty clusters and beneficial-ownership paths that require human review under regulatory frameworks

<!--
Generalize the pattern. Anywhere the answer lives in
relationships rather than individual rows, GDS-as-silver-to-gold
applies. The algorithm changes; the architecture does not.
-->

---

## Why This Framing Passes Regulatory Review

- **GDS does not label fraud.** The Gold columns are features: `risk_score` is a float, `community_id` is an integer, `fraud_risk_tier` is a string
- **Each column has a published mathematical definition.** PageRank, Louvain, and Jaccard are all documented, with reproducible computation under a fixed projection
- **The analyst, investigator, or downstream model adjudicates.** GDS narrows the search space; humans and downstream systems make the call
- **"Three columns with published definitions and reproducible computation"** is defensible under Model Risk Management review. *"The graph database found the fraud"* is not

<!--
This is the defensible framing for regulated environments. GDS
does not produce verdicts. It produces three features whose
mathematical definitions are published in the GDS documentation
and whose values are reproducible given a fixed projection.
Whatever reads the columns adjudicates: investigator triage,
supervised classifier, analyst in Genie. MRM stands for Model
Risk Management; if the audience is non-regulated, retitle the
slide.
-->

---

## Key Takeaways

- **The unit of analysis matters.** Rows cannot represent the patterns fraud rings produce; subgraphs can
- **Flat tables drive confident wrong answers** on structural questions. Genie will rank by proxies that correlate loosely with the right quantity. The issue is column inventory, not SQL
- **GDS as silver-to-gold** writes three deterministic structural columns that Genie reads as ordinary dimensions
- **Deterministic foundation under non-deterministic translation** produces consistent analyst-facing answers without pinning the LLM
- **After enrichment, classic BI shapes answer questions that had no handle before:** composition, cohort, rollup, workload, merchant
- **The pattern generalizes** to any workload where the answer lives in relationships

<!--
Six points. Unit of analysis, confident wrong answers, pipeline
shape, determinism claim, what opens up, generality. The
confident-wrong-answers bullet is the sharpest. It reframes
the whole discussion around column inventory, not tool choice.
-->

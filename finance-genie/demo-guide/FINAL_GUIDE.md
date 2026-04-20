# Graph-Enriched Lakehouse: Combining Databricks Genie with Neo4j Graph Data Science

*For solutions engineers and demo practitioners preparing for live delivery. This is a prep guide, not a production benchmark or technical paper.*

---

## The Graph Enrichment Pipeline

Financial crime is a network problem. Criminals organize in networks, coordinate in networks, and move money through networks. The gap in most fraud detection systems is not the rules. The gap is the unit of analysis: rules fire against individual transactions, but fraud rings operate as connected patterns across dozens of accounts and thousands of transactions. The individual event looks clean. The connected pattern does not. That mismatch is why coordinated schemes evade detection while false positive rates run above 90%.

A fraud ring is a subgraph. Finding it means finding the shape, a cluster of accounts moving money densely among themselves, anywhere it appears in the network, without knowing in advance which accounts to start from. A graph database is the only data store where you can describe a pattern, a subgraph shape, and find all instances of that pattern efficiently, without a predetermined starting point. A traditional database needs a starting point, a specific account ID or customer number, to begin a search. A graph database needs only a description of the pattern, and finds every place that pattern exists in the network. The graph provides the data structure and traversal capability. Detection comes from the queries written against it.

For organizations already running analytics on Databricks, the question is how to bring that graph intelligence into the lakehouse they already operate, without rebuilding the analytics stack around a new query layer. That is what this demo shows.

Databricks Genie excels at traditional BI questions: what has happened, how much, and where. Ask it which accounts had the highest transfer volume last quarter, which merchants drove the most activity, or which regions showed unusual spend patterns. It translates those questions into SQL against the underlying Delta tables and returns an answer in seconds. For understanding historical trends, aggregating activity across any dimension, and surfacing what the data contains, Genie is the right tool.

Neo4j GDS is designed for a different question class: structural analysis. Which accounts are central to the flow of money in a transfer network? Which accounts form communities based on how densely they transact with each other? Which accounts share the same merchant relationships, even without transacting directly? These questions cannot be expressed as joins over flat rows. A fraud ring is not a property of any individual transaction; it is the pattern of connections between accounts. No row-level aggregation can produce a network property. GDS computes three structural answers: centrality, community membership, and neighborhood similarity. The enrichment pipeline materializes the results as plain columns in the lakehouse.

Graph enrichment is the mechanism that connects Neo4j Graph Data Science to Databricks Genie. The enrichment pipeline reads Silver tables from Unity Catalog, loads the account and transaction records into Neo4j as a property graph, runs graph algorithms against the network, and writes the results back to the Gold layer as plain Delta columns. Genie queries those columns the same way it queries any other column in the catalog. The graph analysis is invisible to the query layer; what Genie sees is ordinary tabular data with dimensions that did not exist before the pipeline ran.

The Finance Genie demo shows what happens when both tools do their designed job and the enrichment pipeline connects them. A synthetic fraud dataset loads into Unity Catalog Silver tables. GDS runs as the silver-to-gold enrichment stage: PageRank, Louvain, and Node Similarity process the account-transfer graph and write three scalar columns back into the Gold layer. Structural analysis happens here, in the graph stage, before Genie is involved. The BEFORE Genie Space runs against the unenriched Silver tables. The AFTER Genie Space runs against the enriched Gold tables.

The contrast is the demo's argument. On base Silver tables, structural questions fall outside what Genie can answer. Not because Genie falls short, but because the information is not there. It exists only in the network topology GDS has not yet computed. On enriched Gold tables, the question class shifts entirely: portfolio composition by community, cohort comparisons between risk tiers, community rollups, merchant-side analysis conditioned on community membership. Genie answers them because the enrichment pipeline has written structural dimensions into the catalog as columns. The enrichment pipeline is not better algorithms applied to the same data. It is a different data structure applied to the same records, producing dimensions that flat rows cannot represent.

**The key framing to hold throughout:** GDS surfaces structural patterns that help identify potential fraud. It does not label fraud. The Gold columns are features: `risk_score` is a float, `community_id` is an integer, `fraud_risk_tier` is a string. The analyst, investigator, or downstream model adjudicates. GDS narrows the search space. Humans and downstream systems make the call.

---

## What Genie excels at

Genie is a high-quality translator of analyst questions into SQL over Delta tables. It is at its best on the operations that text-to-SQL systems are engineered for: aggregation, grouping, filtering, ranking, top-N lists, cohort comparisons, time-series rollups, and joins across a small number of tables with clearly labeled columns.

The BEFORE space demonstrates this before any enrichment happens. Against the base Silver tables, Genie handles account balances, transfer volumes, merchant categories, regional activity, and top-account lists without difficulty. That is the baseline that matters: Genie doing its designed job well on the catalog the customer already runs.

The structural questions in the BEFORE demo belong to a different question class: find transfer-network hubs, find groups of accounts moving money heavily among themselves, find accounts with overlapping merchant histories. Asking Genie to resolve them from base Silver tables is not a test of Genie's quality. It is a test of whether the answer exists in the tables at all. It does not. Those answers live in network topology. GDS computes them. Without that structural context, a rule that flags a payment above a threshold fires the same way on the first occurrence and the thirty-sixth. There is no memory of the relationship between that account and that counterparty. That is the context gap that drives false positive rates above 90% in systems built on isolated records.

Genie's capability does not change after enrichment. What changes is that the Gold layer now carries columns whose definitions come from network topology, and Genie applies the same BI operations it has always performed, now over dimensions that did not previously exist.

---

## What GDS excels at

GDS is a library of graph algorithms that operates on the network as a whole rather than on individual rows. The three algorithms in this pipeline each answer a question class that has no SQL equivalent.

**PageRank** answers: which nodes are central to the flow of relationships? Not which nodes have the highest transaction volume, but which nodes the most-connected nodes route their flow through. An account with ten connections to highly connected accounts ranks higher than one with fifty connections to peripheral accounts. PageRank measures structural position; SQL aggregation measures local counts. The output is a float per node representing eigenvector centrality over the transfer graph.

**Louvain** answers: which nodes form communities based on interaction density? Standard segmentation assigns records to groups by their attributes: same geography, same industry code, same risk tier. Those groups reflect the classification applied when the data was collected, not how the entities actually behave in relation to each other. Louvain ignores those labels entirely. It partitions the graph by interaction density, finding communities where nodes connect more densely to each other than to the rest of the network. Two merchants in different industries and different regions land in the same community if their transaction flows are tightly interwoven. Louvain partitions by modularity, finding the community assignment that maximizes within-community edge density relative to a random baseline. The output is an integer per node: community membership.

**Node Similarity** answers: which nodes share the same neighborhood? Not which nodes share an attribute, but which nodes connect through the same set of intermediaries. Two accounts that never transacted directly can score high on similarity if they route through the same merchants. The algorithm computes Jaccard overlap of each node's connection set. The output is a float per node pair representing structural overlap.

Each output is deterministic given a fixed graph projection. Run the same projection twice against the same data and the scores are identical. That property matters when those scores become columns in a catalog that Genie queries non-deterministically. The structural signal is fixed; only the SQL shape Genie generates to retrieve it can vary.

---

## How the enrichment pipeline works

- **Load:** The pipeline reads Silver tables from Unity Catalog and loads them into Neo4j Aura as a property graph.
- **Compute:** GDS runs graph algorithms against the full network, producing centrality scores, community partitions, and structural similarity measures.
- **Enrich:** The pipeline writes those results back to the Gold layer as plain Delta columns: `risk_score`, `community_id`, `similarity_score`.
- **Query:** Genie queries the enriched Gold tables directly, treating graph-derived columns as ordinary dimensions.

The structural analysis runs once per pipeline cycle. Every subsequent Genie query, dashboard, or downstream classifier reads the results as ordinary columns. Each pipeline run refreshes the scores against the current state of the network.

**PageRank → `risk_score`**
Eigenvector centrality over the account-to-account transfer graph. Measures how much transfer volume flows through each account relative to its neighbors' centrality. Converges to a stable value given a fixed graph projection. The fraud population averages 3.65× the centrality of non-fraud accounts on the demo dataset.

**Louvain → `community_id`**
Modularity-optimal community partition. Groups accounts into communities that maximize within-community edge density relative to a random baseline. Each of the ten synthetic fraud rings lands in its own community with 100% ring coverage. Community purity averages 70%, meaning each ring-candidate community contains roughly 100 ring members and ~44 non-ring accounts absorbed by the modularity objective. `fraud_risk_tier='high'` is assigned to all members of ring-candidate communities, 1,440 accounts total rather than 1,000, because the tier follows community membership, not individual ground-truth labels.

**Node Similarity → `similarity_score`**
Jaccard overlap of shared-merchant sets, computed over the bipartite account-merchant transaction graph. Fraud ring members visit the same anchor merchants at elevated rates, which produces Jaccard scores 1.98× higher than the non-fraud population on average. Accounts with fewer than five unique merchant visits are excluded from the bipartite projection by degree cutoff; 3.2% of ring members fall below the cutoff on the demo dataset.

---

The enrichment pipeline writes GDS algorithm results back to the Gold layer as plain columns: network analysis from PageRank, Louvain, and Node Similarity materialized as ordinary Delta fields that Genie queries like any other dimension. Three kinds of graph-derived feature become available:

- **Graph-derived features**: network analysis results from PageRank, Louvain, and Node Similarity stored as plain Gold columns. Genie sees ordinary tabular data with no graph query layer involved.
- **Structural dimensions**: categorical labels derived from graph topology (`community_id`, `fraud_risk_tier`) that Genie groups, filters, and compares across
- **Structural scores**: continuous floats from algorithm outputs (`risk_score`, `similarity_score`) that Genie ranks, buckets, averages, or thresholds
- **Community-level aggregates**: a pre-joined summary table (`gold_fraud_ring_communities`) that Genie queries at the community grain without reconstructing membership

**Structural segments**: `community_id`, `fraud_risk_tier`. These are categorical labels that behave like any other dimension in a warehouse. The difference is that the label comes from network topology rather than a row-level attribute. `community_id` is an integer assigned by Louvain to every account based on its position in the transfer graph. `fraud_risk_tier` is a string, either `high` or `low`, derived from whether an account belongs to a ring-candidate community.

**Structural scores**: `risk_score`, `similarity_score`. These are continuous features that can be bucketed, thresholded, averaged, or ranked like any other numeric column. `risk_score` is PageRank eigenvector centrality over the transfer graph. `similarity_score` is Jaccard overlap of shared-merchant sets, written by Node Similarity. Both are floats. Both behave like any other float column Genie has ever generated SQL against.

**Community-level aggregates**: the `gold_fraud_ring_communities` table. This pre-joins structure to account attributes so Genie can answer questions at the community grain, including total balance across ring-candidate communities, regional breakdown of candidate count, and internal-versus-external transfer ratios, without having to reconstruct community membership itself.

Every classic BI question an analyst would ask about a segment becomes available over a segment that is structurally defined. The SQL shapes are standard. The dimensions are new.

---

## The difference between structural segments and structural questions

Both question types are answerable after enrichment. The difference is what the answer means and whether an analyst can interpret it without a graph-theory primer.

**Structural segment questions** ask Genie to compare, aggregate, or filter over a structural column. "How does average risk score compare between the high and low fraud risk tier accounts?" is a GROUP BY with AVG, the operation Genie is engineered for. It returned 2.42 versus 0.87 in a live test, with a clean table and a bar chart. The answer is self-explanatory. No graph knowledge required to read it.

**Structural questions** ask about network topology directly. "Which accounts are structurally central in this transfer network?" is a legitimate question with a correct answer: rank by `risk_score` descending. Genie can retrieve it. But the result carries a paradox: the accounts with the highest `risk_score`, up to 16.59, belong to the low fraud risk tier, because those highly connected accounts sit in the large background community, not in a ring-candidate community. The data is correct. The framing misleads: an analyst expects the most central accounts to be the most suspicious, which is not what the result says. Interpreting it requires understanding what PageRank measures versus what Louvain measures. That is a graph-theory explanation the demo cannot carry.

The practical rule: if the question asks Genie to *compare or aggregate over* a structural dimension, it is operating inside its designed envelope and the answer is self-explanatory. If the question asks Genie to *identify or characterize* network structure, the answer is correct but requires interpretation the analyst is unlikely to bring. The AFTER demo stays in the first category. Discovery stays with GDS. Characterization stays with Genie.

**Live Q&A response for the PageRank/tier paradox:** If an audience member asks "You said the highest-risk-score accounts have scores above 16. Why are they in the low fraud tier?", the answer is: PageRank and Louvain measure different things. PageRank measures how much transfer flow routes through an account relative to its neighbors' centrality. Louvain measures community density: which accounts transact more densely with each other than with the rest of the network. A hub in the large background community ranks extremely high on PageRank because enormous flow routes through it, but it belongs to a diffuse community, not a tight ring. The fraud signal is community tightness, not raw centrality. That is why `fraud_risk_tier` follows Louvain community membership, not PageRank rank. Both columns are correct. They answer different questions.

---

## Non-deterministic SQL over a deterministic foundation

Genie's text-to-SQL translation is non-deterministic. The same question issued twice can produce SQL with a different shape: a strict superlative using `RANK() OVER ... WHERE rnk = 1` one run, a sampled top-N using `ORDER BY ... LIMIT 100` the next. The SQL is different each time; the answer is correct either time. It is a different view onto the same signal.

That architectural property is what makes the AFTER space reliable. If the gold columns were volatile, two runs against a superlative-shaped query might return completely different accounts, making it impossible to tell whether the signal moved or the SQL did. Because GDS outputs are reproducible given a fixed graph projection, the signal in `risk_score`, `community_id`, and `similarity_score` is identical across every query run. Genie's variance can only change how much of the signal it retrieves, not whether it exists.

A live run against `gold_account_similarity_pairs` illustrates the difference concretely. Genie emitted `RANK() OVER (ORDER BY similarity_score DESC) ... WHERE rnk = 1`, which returned 4 pairs tied at `similarity_score = 0.5`. All 4 were same-ring pairs spanning 2 distinct fraud rings: correct signal, but a thin sample. A subsequent run against the same table produced `ORDER BY similarity_score DESC LIMIT 100`, returning 100 pairs across all 10 rings. Same space, same gold tables, same underlying graph structure; different SQL shape, different sample breadth. The structural signal was present in both results. What varied was how much of it Genie chose to surface.

The practical implication for demo delivery: questions that route through structural score columns will return correct answers on any run, but the specific SQL shape Genie picks affects how many results are returned. If a run surfaces a thin sample and the audience asks why so few records appear, the answer is not that the gold layer is sparse. It is that Genie chose a strict superlative rather than a top-N. Offering a follow-up question that reframes the same retrieval, "show me the 100 pairs with the highest similarity score," typically produces the broader view.

For production-scale threshold calibration and result-count expectations, see [SCOPING_GUIDE.md](../SCOPING_GUIDE.md).

### The harder problem: silent question substitution

Non-deterministic SQL shape is the visible variance. There is a deeper problem that is harder to see during a demo: Genie answers certain question classes with full confidence but answers a different question than the one asked.

The class is structural-discovery questions: "Are there accounts that seem to be the hub of a money movement network that are potentially fraudulent?" Genie will answer. It will rank by transfer volume, or count, or some combination of columns that exist in the table, and return a list. The SQL is correct. The question answered is wrong. Genie silently substituted "which accounts have the highest transfer volume" for "which accounts are structurally central in the transfer network." Transfer volume and network centrality are not the same quantity. An account can move high volume through only a few counterparties; another routes modest volume through a densely connected neighborhood and ranks far higher on PageRank. No amount of SQL over flat rows produces eigenvector centrality.

This is the precision and recall problem for data analyst audiences. For questions with a ground-truth answer, you can score the result set: precision is the share of Genie's returned accounts that are actual network hubs, recall is the share of actual hubs that Genie returned, and F1 is their harmonic mean. On structural-discovery questions against the unenriched Silver tables, precision is low because the proxy columns Genie reaches for, volume, count, and balance, correlate loosely with centrality but do not measure it. Recall is unreliable: captains in a fraud ring route volume through structure, not mass, so the highest-volume accounts are often not the most structurally central ones.

This is not a criticism of Genie. It is the structural question boundary stated precisely. Genie is a high-quality SQL translator. SQL over flat rows cannot compute eigenvector centrality. The enrichment pipeline resolves it by converting the structural quantity into a column before Genie is involved. After enrichment, Genie ranking by `risk_score` descending is not a proxy. It is the correct retrieval of the correct quantity. Precision and recall on that same question class recover fully.

---

## Proposed BEFORE demo questions

The BEFORE space runs against unenriched Silver tables. Ask in two phases: standard BI questions first to show Genie working correctly, then structural-discovery questions to expose the gap. The contrast is the setup the AFTER space depends on.

**Standard BI questions: Genie succeeds. Ask these first.**
- Which accounts had the highest total transfer volume last quarter?
- What are the top ten merchants by transaction count, and what categories do they represent?
- How does average account balance vary by region?

**Structural-discovery questions: Genie substitutes. Ask these second.**
- Are there accounts that appear to be the hub of a money movement network that might be involved in fraudulent activity?
- Which groups of accounts seem to be moving money primarily among themselves?

After the second set, name what happened: "Genie answered the question it could answer with the data it has, not the question we asked. Network topology doesn't exist in these rows. That is what the enrichment pipeline changes."

---

## Proposed AFTER demo questions

Five categories, chosen because they all produce answers that were not possible from the BEFORE catalog and all fall squarely inside Genie's text-to-SQL envelope. A live demo picks three to five questions total. Recommended questions are marked: these have produced clean, self-explanatory results in live testing and require no graph-theory context to read.

### 1. Portfolio composition over structural segments

- What share of accounts sits in communities flagged as ring candidates, broken out by region?
- **Recommended:** How does total account balance split between the high and low risk tiers? Produces a self-explanatory bar chart with a clean GROUP BY and AVG; no graph knowledge required to read the result.
- How many distinct communities are there, and what is the distribution of community sizes?
- What fraction of transfer volume flows between accounts in the same community versus across communities?

### 2. Cohort comparisons across tiers

- **Recommended:** Compare average account balance, average account age, and average monthly transaction count between the high-risk tier and the low-risk tier. Classic cohort comparison; non-technical audiences can read the side-by-side table immediately.
- Do accounts in ring communities concentrate in particular regions or account types, and how does that concentration compare to the overall account population?
- Are ring-community accounts newer or older than the general population?
- How does merchant-category spending mix differ between ring-community accounts and the baseline?

### 3. Rollups over already-labeled communities

- **Recommended:** For ring-candidate communities taken together, what is the total balance held by their members and what share of the book do they represent? Operationally relevant to risk teams; the single-row answer is easy to screenshot and share.
- Break down the ring-candidate community set by region: how many candidates sit primarily in each region, and what is their average member count?
- For each ring-candidate community, what is the ratio of internal transfer volume between members to external transfer volume outside the community?
- Compare average account age and average account balance inside ring-candidate communities against non-candidate communities of similar size.

### 4. Operational and investigator workload questions

- **Recommended:** How many accounts would need investigator review if the bar is high risk tier, and what is the regional breakdown of that workload? Translates directly to staffing conversations; the regional breakdown drives follow-up questions naturally.
- Which regions have the highest concentration of accounts in ring-candidate communities per thousand accounts?
- What is the total balance held in accounts assigned to ring-candidate communities, and how does it compare to total balance in the overall book?
- How many accounts rank first in their community by similarity score, and how are they distributed across regions?

### 5. Merchant-side questions that previously had no handle

- **Recommended:** Which merchants are most commonly visited by accounts in ring-candidate communities? Previously unanswerable from Silver; the result is immediately surprising and visually compelling.
- For each merchant category, what share of transaction volume comes from accounts in the high-risk tier?
- Are there merchants whose customer base is disproportionately concentrated in a single community?
- Which merchants show the largest gap between the risk-tier composition of their customer base and the risk-tier composition of the overall account population?

---

## Where this pattern applies

The enrichment pattern is not specific to financial crime. Any domain where the answer lives in relationships rather than individual rows fits the same pipeline shape: GDS computes the structural quantity, the Gold layer carries it as a column, and every Databricks tool that reads a Delta table reads the enriched column without modification.

- **Fraud-ring surfacing.** Accounts transacting within a tight community, or sharing merchant preferences that do not fit the background distribution. The Finance Genie demo is one instance of this.
- **Entity resolution.** Collapsing customer, device, and household records that refer to the same real-world entity based on shared attributes and interaction topology.
- **Supplier-network risk.** Identifying tiers of supplier exposure, single points of failure, and concentrations of risk in multi-tier supply graphs.
- **Recommendation structure.** Surfacing communities of users, products, or content with shared consumption patterns as features for downstream recommenders.
- **Compliance network review.** Finding counterparty clusters and beneficial-ownership paths that require human review under regulatory frameworks.

---

## Handling tough customer questions

### "The fraud rate is 4%. Real fraud is 0.1%."

The dataset is a pedagogical compression, not a benchmark. At 0.1% base rate and 25,000 accounts, only 25 accounts are fraudulent, not enough to embed ten rings of 50–200 members for Louvain to form the communities the demo depends on. To hit the same structural density at realistic base rates requires roughly one million accounts. The pipeline runs at that scale without code changes; only the data generator parameters change.

The structural signal ratios the algorithms detect, PageRank separation, Jaccard ratio, and community coverage, are theoretically invariant to base rate when ring mechanics scale proportionally. That invariance is the load-bearing claim, not the 4% number.

### "Your dataset was built to make GDS succeed."

It was, and that is the right description of it. The demo dataset is a teaching artifact calibrated to produce observable signal inside a 20-minute window. The honest claim is not production precision. It is that structural signal is unreachable from tabular SQL, and GDS converts it into columns. That claim holds at any base rate, any dataset size, and any ring construction, as long as the relationships are there. GDS will surface them.

### "GDS finds fraud. Can you prove that at scale?"

GDS does not find fraud. It produces three features with published mathematical definitions. PageRank guarantees eigenvector centrality. Louvain guarantees a modularity-optimal community partition. Node Similarity guarantees Jaccard overlap. None of those guarantees is a fraud verdict (see key framing in the opening section).

This framing is what gets through model risk management review. "Three columns with published mathematical definitions and reproducible computation" is defensible. "The graph database found the fraud" is not.

### "What about false positives?"

Community purity on the demo dataset averages 70%. Each ring-candidate community contains roughly 100 ring members and ~44 non-ring accounts absorbed by the Louvain modularity objective. Those 440 accounts across all ten communities are in the high fraud risk tier despite not being ground-truth ring members. That is a Louvain tradeoff, not a GDS failure, and it is honest to name it.

At production scale, `fraud_risk_tier` is recalibrated against the customer's observed distribution. The tier threshold, or equivalent column, is reviewed per dataset. The pipeline shape does not change: projection definition, algorithm configuration, and gold-table DDL remain fixed. What changes is the threshold that determines which communities rise to the candidate tier.

### "The ring construction is engineered for success."

`RING_ANCHOR_PREF=0.35` and `CAPTAIN_TRANSFER_PROB=0.02` are calibrated so Node Similarity and PageRank detect the signal the algorithms are designed for. That is honest engineering of a teaching artifact. The right response: the dataset is built to make the structural signal observable inside a 20-minute window, not to benchmark production precision. The structural claim, that PageRank, Louvain, and Node Similarity surface signal that no tabular aggregation can reach, holds at any base rate and any ring calibration, as long as the relationships exist in the data.

### "Everything looks too clean."

20/20 top-risk accounts as ground-truth fraud, 10/10 community assignments at 100% ring coverage, 100/100 similarity pairs as same-ring: no production fraud system returns numbers like these. Name it directly: the dataset was constructed to produce exactly these results. The demo is a pedagogical compression, not a production audit. The strong claim is not precision at 4% base rate. It is that the structural signal class exists in the network and is unreachable from row-level SQL. That claim holds regardless of how clean the teaching artifact looks.

### "There's no confuser population."

The synthetic data has ring members, captains, whales, and normals. It does not have dense non-ring communities, family units, small-business payroll clusters, commuter corridors, that share merchant preferences for benign reasons. Every Louvain community that matches the ring-size band is a real ring because the data contains no near-misses. At production scale, a confuser cohort exists in real data, and the tier threshold is calibrated against the customer's observed distribution, not against the demo's synthetic rings. The pipeline shape does not change; the threshold does.

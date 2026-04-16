# Advancing the Finance Genie Demo

## Why this redesign is needed

The current demo shows three fraud patterns, each calibrated so that one Neo4j Graph Data Science algorithm surfaces it cleanly. The pedagogy is tidy, but testing revealed a weakness. When a Genie user prompts with even moderately thoughtful language about money movement networks, Genie generates a one-hop bidirectional cycle-detection query in plain SQL and returns fraud ring members without any graph algorithm at all. The PageRank story in particular is weakened by this result: what the demo claims requires graph iteration is, under the right prompt, approximable in SQL that a capable text-to-SQL system will write on the first try.

The deeper issue is framing. The current demo positions graph algorithms as query-time machinery that finds fraud. That framing invites the counter-argument that has just been demonstrated — if a well-prompted SQL query can reach the same answer, the graph engine is a luxury, not a necessity. The stronger and more defensible framing is that graph algorithms are not competing with SQL at query time. They are competing with Spark feature engineering upstream of a classifier. The question the demo should answer is whether the structural features a fraud classifier needs can be engineered in Databricks without a graph engine.

This document proposes restructuring the demo around that stronger argument.

## The pivot from query-time to feature-engineering-time

The honest concession is that Databricks ML can absolutely classify fraud given the right features. Gradient boosting on a well-engineered feature table is a strong baseline and for most fraud patterns it is the production answer. The question is where the features come from.

For local graph features — in-degree, out-degree, clustering coefficient, shared counterparty counts, simple two-hop aggregates — Spark is a perfectly good substrate. A skilled data engineer can write these aggregates and a classifier will use them. Any fraud pattern whose signal reduces to "count something one or two hops out" is fair game for a tabular pipeline, and the demo should not pretend otherwise.

For global, iterative structural features — random walk embeddings, sparse random projections, iterative modularity optimization, embedding-based structural equivalence — Spark does not provide them. GraphFrames exists but lacks first-class support for Node Similarity, Node2Vec, and FastRP, and its community detection is weaker than Neo4j Graph Data Science by every published benchmark. This is where the demo's argument is strongest, and this is where the redesigned fraud patterns should live.

The pivot matters because it changes what a skeptical reviewer has to concede. Under the old framing, a reviewer can rightfully say "a cleverer SQL query finds this." Under the new framing, a reviewer has to say either "Spark has a graph library I can use" — which is not true at the level the demo needs — or "I can engineer these features by hand" — which becomes the substance of the demo itself. The demo shows them trying and failing.

## What embeddings actually do, in plain English

Node2Vec walks the graph by taking random steps from each node and remembers the sequences of nodes it visits. It then trains a small model on those sequences and produces a dense vector for each node — roughly a hundred numbers that place the node in a coordinate system where structurally similar nodes land near each other. Two accounts that occupy the same kind of position in the transfer graph end up close in this coordinate system regardless of whether they share any specific counterparty, merchant, or time pattern.

FastRP is the simpler and faster cousin. It starts by assigning each node a random vector, then iteratively mixes each node's vector with the average of its neighbors' vectors. After two or three rounds, each node's vector reflects both its immediate connections and the character of its two-hop neighborhood. The output is the same shape as Node2Vec — a dense vector per node — but it is produced by matrix operations rather than random walks, and it scales more gracefully.

Neither method is a classifier. Both produce structural coordinates. The classification step downstream uses the same gradient boosting or logistic regression a Databricks ML pipeline would use. The reason Databricks cannot drop into the pipeline as a replacement is that Databricks has no way to produce those structural coordinates in the first place. You cannot write SQL that asks for a node's position in the global transfer graph. You cannot express a random walk as a set of joins without the query planner fighting you. You cannot do iterative neighbor mixing in pure SQL without materializing intermediate tables that grow at every step.

This is the line the demo needs to draw clearly. The graph engine is not replacing the classifier. It is replacing the feature engineering step that sits upstream of the classifier, and it is replacing it with features that the tabular side cannot engineer at all.

## Three redesigned fraud patterns

Each of the three patterns below carries a single property: its discriminating signal lives in global graph structure and cannot be captured by any hand-engineered tabular feature that fits in a Spark pipeline. Each pattern replaces one of the three current patterns and makes a stronger version of the same argument.

### Pattern one: ghost mule laundering

Fraud money does not travel directly from source to destination. It passes through three to four layers of intermediate accounts before cashing out. Each intermediate account — a ghost mule — looks clean by every local feature. Its balance sits in the normal range, its transaction hours are normal, its merchant mix is normal, its raw transfer count is unremarkable. It is only suspicious because of who it passes money to and from, and only when you follow those connections for several hops.

The terminal fraud accounts are the actual cash-out points. They share one property: random walks starting from known fraud sources land on them far more often than chance would suggest. This is exactly what personalized PageRank measures and what Node2Vec's random walks encode when the embeddings are later clustered.

A Databricks ML team trying to catch this pattern by hand would need to engineer a feature like "fraction of this account's inbound money that, traced through four layers, originates from a flagged source." Computing that feature requires a recursive SQL query whose intermediate result set explodes after two or three hops on a dense transfer graph, and the flagged source set is not fixed — as new fraud is discovered, the set grows, and every recursive query has to be rerun from scratch. This is iteration disguised as feature engineering, and Spark is the wrong substrate for it.

Pattern one makes the case for embedding-based centrality. Plain PageRank is the first-order version of the argument; Node2Vec with personalization is the general case. The demo should show both.

### Pattern two: structural role fraud

Fraud accounts in this pattern play one of three roles. Collectors take many small inbound transfers and make one large outbound transfer. Layerers take a few inbound transfers and pass them on immediately, holding almost nothing. Cashout accounts take one inbound transfer and buy from a narrow rotating set of merchants. Each role has a structural signature, but no single feature separates fraud from normal within a role. A normal account can be a collector. A normal account can be a layerer.

What distinguishes fraud is the combination of role and neighborhood: a collector whose counterparties are layerers whose counterparties are cashout accounts. The pattern is defined by second-order and third-order structure, not by anything local to the account itself. This is what graph embeddings are designed to capture. FastRP is particularly well suited here because its iterative neighbor mixing is exactly the right granularity for role discovery — two or three passes of mixing capture the role of an account, the roles of its neighbors, and the roles of its neighbors' neighbors in a single vector.

A Databricks ML team can engineer role indicators by hand. They can compute in-degree to out-degree ratios, average neighbor degree, clustering coefficient, and a dozen similar aggregates. They will get partial lift because the within-role distribution of those features does drift slightly for fraud accounts. What they cannot engineer is the interaction term — "this account plays the collector role and is surrounded by accounts that play the layerer role and are themselves surrounded by cashout accounts." That is a higher-order feature that a tabular pipeline cannot express without enumerating every possible combination of role-of-neighbor-of-neighbor, and the combinatorics make the attempt hopeless. Embeddings encode it for free.

Pattern two is the strongest argument in the redesigned demo because it is the pattern most clearly impossible in Spark feature engineering. A reviewer who wants to rebut the demo has to either accept that embeddings are necessary or enumerate every interaction term by hand, and the enumeration does not converge.

### Pattern three: bipartite hidden community

Fraud rings share merchants, but not in the way Jaccard can detect. Account A uses five merchants. Account B, also in the ring, uses five different merchants. The two accounts have zero shared merchants, so any pairwise Jaccard similarity is zero. A merchant-overlap aggregate finds nothing at the pair level.

The hidden structure is that both accounts' merchants are used by a small set of other accounts that are also in the ring. Two fraud accounts are similar not because they share merchants, but because their merchants are connected through a shared customer base — a structural overlap that lives two hops away in the bipartite account-merchant graph.

FastRP run on the combined account-merchant graph captures this cleanly. After two iterations of neighbor mixing, each account's vector reflects both the merchants it used and the character of those merchants' other customers. Fraud accounts in the same ring end up with similar vectors because they populate the same connected subgraph, even though no two of them directly share a merchant.

A Databricks ML team can compute two-hop merchant similarity by hand with a wide join, but the join scales poorly on realistic data volumes, the resulting similarity matrix is dense rather than sparse, and the feature produced is itself a graph algorithm written in SQL. The tabular version of this feature is a graph algorithm in disguise, and the demo should say so.

Pattern three replaces the anchor-merchant Jaccard pattern. The old pattern was defensible only because Jaccard itself is awkward to express in Genie's generated SQL. The new pattern is defensible because the feature itself cannot be engineered in Spark without writing a graph algorithm by hand.

## Changes to the dataset generator

The generator needs to produce three new structural properties alongside the existing tables. The description here is in plain prose.

For ghost mule laundering, the generator places fraud accounts into multi-layer flow graphs rather than into fully connected rings. Each flow graph has a source tier of accounts that receive external deposits, two or three middle tiers of ghost mules, and a terminal tier of cash-out accounts. Transfers flow strictly from earlier tiers to later tiers, with enough randomization that no two flow graphs have identical topology. The number of flow graphs, the account count per tier, and the transfer volume per link all become configuration knobs in the same style as the current ring count and within-ring probability.

For structural role fraud, the generator assigns roles — collector, layerer, cashout — to both fraud and normal accounts in approximately the same proportions, so that role alone does not separate fraud from normal. The separation comes from neighborhood: fraud accounts in a given role are preferentially connected to fraud accounts in the adjacent role, while normal accounts in the same role are connected to a random mix. The tabular marginal distributions remain almost identical; the joint distribution across three hops is what carries the signal.

For the bipartite hidden community, the generator assigns each ring a pool of merchants and then has each fraud account in the ring draw a non-overlapping subset of that pool. The connecting structure is maintained by the merchants themselves — every merchant in the pool is used by multiple fraud accounts in the ring, so the bipartite graph has a dense core even though no two fraud accounts share a merchant directly. This is a small change to how the anchor merchants are sampled but a large change in what a direct-overlap aggregate can detect.

Tabular signals — balance, age, transaction hour, transaction amount — should remain nearly identical between fraud and normal, as they already are. The point of the redesign is not to hide the signal in more places, but to move the entire signal into structure that tabular feature engineering cannot recover.

## Changes to the verification framework

The existing verifier checks three structural properties: whale inflation of raw inbound centrality, within-ring transfer density, and anchor-merchant Jaccard. The redesigned verifier needs different checks that correspond to the new patterns.

For ghost mule laundering, the verifier should confirm two things. First, terminal cash-out accounts have elevated personalized PageRank relative to the source set compared to an arbitrary sample of accounts with the same local degree. Second, ghost mules themselves have essentially normal local features — their degree, their balance, their merchant mix, their transaction hours are statistically indistinguishable from a matched normal control group. If either check fails, the pattern has leaked tabular signal and the generator needs to be retuned.

For structural role fraud, the verifier should confirm that within each role, fraud and normal accounts are indistinguishable by single features, but a small embedding-plus-clustering pipeline separates them cleanly. This check requires running a lightweight graph embedding step inside the verifier, which is a new dependency — the verifier was previously pure Python over pandas and will now need a graph library. A reasonable choice is to run the verification embedding in a small Python graph library rather than requiring Neo4j, so the verifier remains runnable without a live Aura instance.

For the bipartite hidden community, the verifier should confirm that pairwise Jaccard similarity of direct merchant sets among fraud accounts in a ring is essentially zero, while two-hop bipartite similarity is elevated by a measurable margin. The first half confirms the absence of a tabular shortcut; the second half confirms the presence of the embedding-surfaceable signal.

The Genie CSV verification modes stay conceptually the same. A workshop participant runs Genie against the Delta tables, exports the top-ranked accounts or account pairs as a CSV, and the verifier scores that CSV against the ground truth. The difference is that passing now requires the output of an embedding pipeline, not the output of cycle detection.

## Changes to the notebooks

Notebook 02 — the Neo4j Graph Data Science guide — needs to extend the existing PageRank, Louvain, and Node Similarity steps with Node2Vec and FastRP runs. The new algorithms write their output back to the accounts table as embedding vector columns and, for clustering, derived label columns. The existing algorithms stay in place because they still carry the first act of the demo; the new algorithms carry the stronger second act.

Notebook 03 — the modeling notebook — needs a stronger tabular baseline. Right now the baseline uses raw account columns, which makes the graph lift look larger than it would against a competent tabular pipeline. The strengthened baseline should include hand-engineered local graph features computed in Spark: in-degree, out-degree, average neighbor degree, clustering coefficient, shared counterparty counts with a sampled set of reference accounts, and two-hop inbound totals. The graph-augmented model then adds the GDS embeddings and cluster labels on top of that stronger baseline. The lift measured this way is the honest number — the improvement from structural embeddings over hand-engineered local graph features, not over no graph features at all.

The modeling notebook should also report two specific things that the current version does not. First, the rank correlation between FastRP cluster membership and ring membership, reported as a single number that summarizes how cleanly the embedding recovers ground truth. Second, the fraction of terminal cash-out accounts recovered by personalized PageRank compared to the fraction recovered by the best tabular model. These two numbers are the demo's punchline in quantitative form, and they should appear in the closing slide of the workshop.

## The honest framing

The redesigned demo should be explicit about what it claims and what it does not.

It claims that three specific fraud patterns require graph-native feature engineering to detect. It claims that Databricks does not provide first-class support for the algorithms needed — Node2Vec, FastRP, structural community detection, bipartite embeddings — and that GraphFrames, while present in the ecosystem, is not a sufficient substitute for the algorithms the demo uses. It claims that the classification step downstream is the same gradient boosting Databricks ML would use in either case, and the question the demo answers is where the features come from.

It does not claim that Genie cannot find fraud. Genie can approximate one-hop and two-hop patterns with a well-crafted prompt, and the demo should concede this explicitly in the opening. It does not claim that tabular models fail at fraud detection — they work, they catch most fraud in production, and adding graph structural features produces a realistic three to eight percent AUC lift over a well-engineered tabular baseline, not the ten-times-stronger signal the current synthetic dataset exhibits.

This honesty is load-bearing. The reason to show the demo is to make the case that graph-native features belong in a production fraud detection pipeline alongside tabular features, not to claim that graph algorithms make tabular analysis obsolete. A reviewer who walks away convinced of the stronger claim is more valuable than a reviewer who caught the demo overstating its hand.

## Risks and open questions

The strongest risk is that Databricks ships a native graph library that supports Node2Vec, FastRP, or equivalent embeddings. If that happens, the feature engineering argument weakens. GraphFrames has been in this adjacent space for years without catching up to Neo4j Graph Data Science, and no announced roadmap puts Databricks at parity in 2026, but the demo should acknowledge the possibility in a footnote rather than pretending it cannot happen. The argument survives as long as graph algorithms remain second-class in the Spark ecosystem, which is the current state of the world and appears likely to remain so through the near term.

A secondary risk is that the redesigned patterns become too abstract for a ninety-minute workshop. Ghost mules and structural roles are less visually obvious than whales and rings. The notebook explanations and the diagrams in the admin guide will need to carry more of the pedagogical load, and the workshop facilitator will need to spend more time on intuition-building before the code runs.

A third risk is that the embedding pipeline takes longer to run on the workshop cluster than PageRank or Louvain did. Node2Vec in particular is heavier than PageRank, and a twenty-five-thousand-account graph may push the runtime past the comfortable window for a live demo. The mitigation is to pre-compute embeddings for the workshop and load them from a checkpoint, showing the algorithm run on a smaller sample for pedagogical clarity.

An open question is whether to keep any of the current patterns as a warm-up. Keeping them lets participants build intuition on simple cases before hitting the harder ones. Cutting them keeps the demo focused and avoids anchoring participants on the weaker version of the argument. A middle path is to keep the PageRank pattern as a simple opening example, acknowledge in the narration that it is approximable in SQL under thoughtful prompting, and use that acknowledgment as the explicit motivation for the harder patterns that follow. This middle path is the recommendation.

## Implementation sequence

The redesign is substantial but can be staged so that each step produces a runnable checkpoint.

The first stage updates the dataset generator to produce the three new patterns alongside the existing tables. The generator changes are contained to a single file and a handful of new configuration knobs, and they do not disturb the rest of the pipeline. At the end of this stage, the generator produces a dataset that satisfies both the old and new verification checks.

The second stage updates the verifier with the new structural checks and extends the ground truth JSON to include the new pattern metadata — source sets for personalized PageRank, role assignments per account, bipartite ring merchant pools. This is the stage that introduces a new Python dependency for the lightweight verification embedding.

The third stage extends notebook 02 with Node2Vec and FastRP runs. The existing PageRank, Louvain, and Node Similarity steps remain in place at the top of the notebook as the first act. The new algorithms appear below as the second act. Write-back to Delta adds new embedding columns on the accounts table.

The fourth stage updates the modeling notebook. The tabular baseline is strengthened with hand-engineered local graph features. The graph-augmented model adds the new embeddings on top. Two new reported numbers anchor the closing slides: the FastRP cluster recovery of ring ground truth, and the personalized PageRank recovery of terminal cash-out accounts.

The fifth and final stage updates the README, admin guide, and Genie test protocol to reflect the new framing. The narrative moves from query-time to feature-engineering-time. The opening concedes Genie's approximate one-hop capabilities. The body explains the three new patterns in terms of what features they require and why those features cannot be produced in Spark. The closing reports the honest AUC lift numbers against the strengthened baseline. This is where the demo's credibility is established and where the version of the argument that survives reviewer pushback lives.

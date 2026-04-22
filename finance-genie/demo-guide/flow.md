# Demo Flow

> **Core goal of this rewrite:** Don't explain the enrichment pipeline before showing the payoff. Lead with one fraud question and two answers — before and after enrichment — and let the gap speak for itself. The anchor question must produce a difference that is immediately legible on common sense alone, without graph-theory knowledge. The before answer should sound plausible but be structurally wrong; the after answer should be specific and actionable. The audience's question — "how did you get that?" — is the invitation to explain the architecture. The explanation earns its place because they asked for it.
>
> **Framing: expansion, not limitation-recovery.** Pitch the enriched lakehouse as unlocking a new set of questions for Genie, not as patching a Genie shortcoming. The before/after is a demonstration of that unlock; it is not an argument that Genie is broken.
>
> **Time budget: 15 minutes, three parts — anchor, architecture, pipeline.** The anchor opens with the before/after question and its two answers. The architecture section explains what Neo4j adds. The pipeline section shows how the features that produced the second answer are built. Question selection needs to respect this envelope — an anchor that requires setup before the two answers make sense does not fit.
>
> **Reference shape for the gap: the FINRA demo.** Phillip's FINRA demo for the Wells Fargo investment community asked which asset managers were most exposed to the Iran conflict. Without graph RAG, Genie returned descriptors (funds with high oil exposure, funds with high defense exposure); with graph RAG, it returned the actual top 10 asset managers by name. Descriptors vs. named entities is the model of a legible gap. If the before/after on a candidate question is not as visible as that, keep looking.


# Current Flow

**Anchor**

1. **Fraud doesn't happen in one account:** Money laundering rings, mule operations, and coordinated schemes spread activity across dozens of accounts — deliberately, to evade per-account detection. The scheme is a shape: a cluster of accounts moving money densely among themselves. Each transaction looks clean in isolation; the pattern across accounts does not. A row-level aggregation cannot produce a property that only exists in the connections between accounts.

   *Alternative framing — **Coordinated schemes hide between the rows**:* Structuring, layering, and mule networks intentionally split activity across many accounts so no single account trips a threshold. The scheme is in the movement *between* accounts, not in any row — a network property row-level detection cannot produce.
2. **Merchant favorites (anchor question):** Run "Which merchants are most commonly visited by accounts in ring-candidate communities?" against the raw lakehouse (before) and the enriched lakehouse (after). Before: top merchants by overall visit count — popular chains that sound like a real answer. After: a specific list of merchants where ring-community members cluster disproportionately. Show both side by side; let the audience evaluate the gap without domain expertise required; no architecture yet.

   *Presenter cue — hold on the two answers until someone asks "how did you get that?" That question is the invitation into Architecture. If nobody asks, offer it: "does anyone want to know how we got to that specific list of merchants?"*

**Architecture**

3. **Some questions are about connections and patterns, not about sums and averages of accounts:** How central an account is in the flow of money, how tightly a group of accounts trades within itself, whether two accounts route through the same merchants. The answer is in the pattern, not in any one account.
4. **SQL traversal starts from an account; a graph database starts from a pattern:** To answer a connection question in SQL, you need to know which account to start from — a specific account ID or customer number. A graph database needs only a description of the pattern, and finds every place that pattern exists in the network.
5. **Graph database and lakehouse work together:** The graph is the right data layer for connection questions; the lakehouse is the right layer for aggregates, joins, and the business questions Genie already handles well. Compute the connection patterns in the graph, land them as columns in the lakehouse, let Genie answer against them.

**Pipeline**

6. **Load — Silver into Neo4j:** Account and transaction records from the existing lakehouse map into Neo4j Aura as a network of connected entities.
7. **Run GDS — patterns become columns:** PageRank surfaces accounts central to money flow (→ `risk_score`); Louvain finds clusters trading tightly together (→ `community_id` / `fraud_risk_tier`); Node Similarity finds accounts sharing the same counterparties (→ `similarity_score`). Same graph in, same scores out, every time.
8. **Enrich — results land in Gold:** Databricks pulls GDS outputs from Neo4j via the Spark Connector, joins with Silver, and writes `risk_score`, `community_id`, and `similarity_score` as plain Delta columns.
9. **Query — auditable by construction:** Nothing in the graph reaches a Genie query until the pipeline has materialized it into the enriched Gold tables. Genie treats graph-derived columns as ordinary dimensions; the audit trail is the Delta table.

**Close**

10. **The graph finds candidates; the analyst finds fraud:** GDS produces structural signals that indicate *ring-like behavior* — community membership, centrality, similarity. Deciding which accounts and merchants warrant investigator time is the analyst's job, done by running ordinary Genie queries against the enriched Gold tables. The "after" questions in this demo (merchant concentration, regional review workload, book share by community) *are* that workflow.
11. **The analyst's toolkit, expanded:** Graph-derived columns unlock a class of questions the analyst couldn't frame against the lakehouse alone — sizing the candidate-ring population as a share of the book, triaging investigator workload by region or risk tier, comparing cohorts defined by community membership against the baseline, and looking at merchants through the lens of their customers' structural signals. The analyst works in Genie the same way they always have; the difference is that `community_id` and `risk_tier` are now available as ordinary dimensions alongside region, product, and balance — `GROUP BY fraud_risk_tier`, not "find the ring." Framed as expansion, not limitation recovery.

**Fill-in / Q&A**

12. **Generalization:** The pattern applies beyond fraud — entity resolution, supplier-network risk, recommendation, compliance review
13. **Defensibility:** GDS produces features with published mathematical definitions; humans and downstream models adjudicate, not the pipeline

# Finding Candidate Rings

The graph finds suspicion; the analyst finds fraud. GDS turns network structure into columns — community membership, centrality, similarity — that flag accounts whose *shape of activity* resembles a ring. It does not prove fraud; the pipeline makes no judgment call. A high-risk community is a candidate, not a verdict. The fraud work is an analyst running ordinary Genie queries against the enriched Gold tables: sizing the candidate population, scoping investigator workload by region, comparing cohorts by risk tier, deciding which accounts and merchants warrant review. The demo's "after" questions are that workflow — traditional analytics conditioned on graph-derived columns.

---

## Anchor Question Candidates

Evaluated against Kapil's criterion: the before answer must sound plausible but be structurally wrong; the after answer must be specific and actionable; the gap must be legible without domain expertise. **Shortlist: 1, 2, 3. Rework before using: 4, 5.**

1. **"Which merchants are most commonly visited by accounts in ring-candidate communities?"** *(cat5)*
   Before: top merchants by overall visit count — popular chains, sounds like a real answer. After: a different, specific list of merchants where ring members cluster disproportionately. Before is a popularity ranking; after is an anomaly signal. Closest to the FINRA pattern Kapil cited.

2. **"For ring-candidate communities taken together, what is the total balance held by their members and what share of the book do they represent?"** *(cat3)*
   Before: Genie computes total balance for the top decile by transfer volume — a reasonable proxy for "suspicious" that any analyst would reach for. After: total balance for graph-identified ring candidates; the share-of-book figure is the executive summary number that risk leadership asks for. The number changes for a reason the audience will want explained.

3. **"How many accounts would need investigator review if the bar is high risk tier, and what is the regional breakdown of that workload?"** *(cat4)*
   Before: Genie guesses a threshold — high-volume accounts above some cutoff — and returns a number. After: specific count from graph-derived tiers plus regional breakdown. A risk manager immediately sees before is a proxy and after is a defensible segment.

4. **"What fraction of total transfer volume flows between accounts that have transacted with each other more than five times, versus accounts with no prior relationship?"** *(cat3, reworked)*
   Before: a frequency proxy for insularity — repeat-transfer pairs as a stand-in for community structure. After: per-community internal vs. external ratios; the insularity is now measured against graph-defined membership, not transactional recurrence. The intuition — money staying inside a tight group is suspicious — lands without graph knowledge.

5. **"Are there merchants where the majority of transaction volume comes from accounts that also transact heavily with each other?"** *(cat5, reworked)*
   Before: Genie identifies merchants served by a cluster of mutually-transacting accounts — a proxy for community concentration using transfer co-occurrence. After: concentration measured against actual community membership; a merchant serving one tight community is a structurally different signal than one with mutually active customers. Before and after are now the same question, one answered with a proxy and one with the structural column.

6. **"For accounts in ring-candidate communities, what fraction of their transfer volume stays within the community versus flows outside it, compared to non-ring accounts?"** *(cat2)*
   Before: overall inbound/outbound transfer stats with no community filter. After: side-by-side cohort comparison showing ring accounts keep far more volume internal. Solid comparison shape but requires understanding ring-candidate to appreciate the after answer.

7. **"Which merchants show the largest gap between the risk-tier composition of their customer base and the overall account population?"** *(cat5)*
   Before: no risk tier, so Genie returns a merchant ranking by volume or category. After: specific merchants with outsized ring-community exposure. The "gap" concept is slightly abstract — requires knowing what risk tiers are to read the after answer.

8. **"How does total account balance split between the high and low risk tiers?"** *(cat1)*
   Before: Genie splits balance by a familiar dimension — region, account type. After: the same split defined by graph-derived tier. Both return a two-way table; the gap is real but subtle — same answer shape, different segment definition.

9. **"What is the average transfer count per account within ring-candidate communities versus the general account population?"** *(cat2)*
   Before: Genie compares high-volume accounts to the overall population — a volume cohort, not a structural one. After: graph-defined communities versus the baseline. Same issue as #8 — the answer shape is identical, the gap is in segment definition only.

---

## Anchor Question Reworks

Each candidate rephrased so the before question is askable against Silver tables (no graph columns) and the after question uses the Gold-layer column the before could not reach. The before uses volume, count, or frequency as a proxy; the gap between the two answers is the demo's argument.

1. **Merchant favorites**
   - Before: "Which merchants are most commonly visited by accounts with the highest total transaction volume?"
   - After: "Which merchants are most commonly visited by accounts in ring-candidate communities?"

2. **Ring candidate book share**
   - Before: "For the top 10% of accounts by transfer volume, what is the total balance held and what share of the book do they represent?"
   - After: "For ring-candidate communities taken together, what is the total balance held by their members and what share of the book do they represent?"

3. **Investigator review queue**
   - Before: "How many accounts are in the top 10% by transfer volume, and what is the regional breakdown?"
   - After: "How many accounts would need investigator review if the bar is high risk tier, and what is the regional breakdown of that workload?"

4. **Internal vs external transfer ratio**
   - Before: "What fraction of total transfer volume flows between accounts that have transacted with each other more than five times, versus accounts with no prior relationship?"
   - After: "For each ring-candidate community, what is the ratio of internal transfer volume between members to external transfer volume outside the community?"

5. **Merchant community concentration**
   - Before: "Are there merchants where the majority of transaction volume comes from accounts that also transact heavily with each other?"
   - After: "Are there merchants whose customer base is disproportionately concentrated in a single community?"

6. **Cohort internal transfer fraction**
   - Before: "For accounts with above-average transfer counts, what fraction of their transfers go to accounts they have previously transacted with, compared to accounts with below-average transfer counts?"
   - After: "For accounts in ring-candidate communities, what fraction of their transfer volume stays within the community versus flows outside it, compared to non-ring accounts?"

7. **Merchant gap**
   - Before: "Which merchants have the most concentrated customer base — where fewer than 20 accounts make up more than half their transaction volume?"
   - After: "Which merchants show the largest gap between the risk-tier composition of their customer base and the overall account population?"

8. **Balance by risk tier**
   - Before: "How does total account balance split between accounts in the top and bottom half by transaction volume?"
   - After: "How does total account balance split between the high and low risk tiers?"

9. **Transfer count cohort**
   - Before: "What is the average transfer count per account among the top 10% highest-volume accounts versus the general account population?"
   - After: "What is the average transfer count per account within ring-candidate communities versus the general account population?"

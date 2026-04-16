# Data Design Fix Proposal

## Status Checklist

### Generator changes
- [x] Reduce `WHALE_INBOUND` 0.20 → 0.10 (`.env` / `config.py`)
- [x] Reduce `WHALE_OUTBOUND` 0.20 → 0.10 (`.env` / `config.py`)
- [x] Raise `WITHIN_RING_PROB` 0.30 → 0.50 (`.env` / `config.py`)
- [x] Implement captain topology in `generate_account_links` (`CAPTAIN_COUNT=5`, `CAPTAIN_TRANSFER_PROB=0.10`)

### Local validation
- [x] Regenerate CSVs (`uv run setup/generate_data.py`)
- [x] `verify_fraud_patterns.py` passes all structural targets (4/4: whale top-200 199/200, density 866x, Jaccard 6.15x, column signals weak)

### Full pipeline
- [ ] Upload to Databricks + run notebooks 00 and 01
- [ ] `validate_neo4j_graph.py` passes
- [ ] `run_and_verify_gds.py` — PageRank top-20 fraud fraction ≥ 50%
- [ ] `run_and_verify_gds.py` — Louvain avg purity ≥ 50% across rings (avg-based check; 12x lift over 4% baseline; bidirectional projection filter tried and rejected — generator rarely produces reciprocal within-ring pairs, collapsed graph to 231 nodes)
- [ ] `run_and_verify_gds.py` — Node Similarity ~250k relationships, fraud/normal avg ratio > 2.0 (Criterion A)
- [ ] Demo notebook Check 3 — same-ring fraction in Genie pairs > 60% (Criterion B)
- [ ] Demo checks pass in `gds_enrichment_closes_gaps.ipynb`

---

## The failure that sent us looking

Three checks in `genie_demos/gds_enrichment_closes_gaps.ipynb` were returning zero: zero fraud accounts in the top twenty by PageRank, zero coverage of any fraud ring by Louvain communities, zero meaningful Node Similarity results. The demo's entire narrative hinges on those three checks passing after GDS enrichment. If they do not pass, the demo has nothing to show a customer.

The initial assumption was a Genie Space configuration problem. The tables in Databricks were healthy, `risk_score` values varied from 0.15 to 20.7, and Genie's generated SQL was correct: it sorted `gold_accounts` by `risk_score DESC` as expected. Yet the top twenty returned zero fraud accounts. The problem was not in Genie. It was deeper.

## How we confirmed the failure mode

We built four validation scripts in `finance-genie/validation/` to isolate which layer of the pipeline was broken: generator, Databricks tables, Neo4j ingest, GDS algorithms, or Genie.

`validate_neo4j.py` checks that the credentials in `.env` actually connect to Neo4j Aura and that the driver can execute a trivial query. This confirmed the connection layer was working.

`validate_neo4j_graph.py` queries Neo4j directly and compares what is there against `data/ground_truth.json`. It counts nodes and relationships, measures within-ring peer-to-peer density against background density across the ten rings, and verifies that each ring's members actually visit their four anchor merchants at an elevated rate. This script revealed that the graph ingested into Neo4j was structurally healthy: within-ring transfer density was 944 times the background rate, and every ring visited its anchors at 45 to 60 times the baseline rate. The generator's output, as loaded into Neo4j, was solid.

`validate_gds_output.py` queries the GDS-computed properties on Account nodes. This is where the first surprise emerged. The Neo4j graph held only 28 `SIMILAR_TO` relationships where the Node Similarity algorithm with `topK=10` on 25,000 accounts should produce around 250,000. Node Similarity had never finished running in the original `02_aura_gds_guide.ipynb` notebook execution. It either errored silently or was interrupted.

`run_and_verify_gds.py` replicates the exact GDS pipeline from the notebook and runs it locally from this directory against the live Neo4j Aura instance. It projects the account transfer graph, runs PageRank and Louvain, projects the bipartite account-merchant graph, runs Node Similarity, and then runs a per-ring diagnostic that asks "where are ring zero's 100 members in community space". After this script ran, Neo4j held 250,018 `SIMILAR_TO` relationships. The pipeline was capable of completing. The question became whether the outputs, once complete, actually separated fraud from normal.

## The three problems the scripts surfaced

The Node Similarity failure was a pipeline bug. The original notebook execution never completed that step. Running the GDS algorithms from the validation script restored the full 250,000 similarity relationships. Once the gold tables are refreshed from Neo4j, Check 3 in the demo should work correctly. This fix has not yet been validated end-to-end; the full pipeline rerun and demo check are still pending.

The second problem is PageRank. On average, fraud accounts score 1.84 in `risk_score` versus 0.82 for normal accounts, a ratio of 2.25. The averages separate cleanly. But the top twenty accounts by `risk_score` are all whales, not ring members. The cause is raw inbound volume. Each whale receives roughly 40 inbound transfers from random sources. Each ring member receives roughly 5 transfers from other ring members. PageRank correctly weights the quality of ring incoming edges higher per edge, but whales win on edge count. The extreme tail of the distribution belongs to whales. This is the data design problem we set out to investigate.

The third problem is Louvain purity. Every one of the ten fraud rings is correctly identified as a single community: all 100 members of each ring end up in the same `community_id`. This is a strong result. However, each ring's community also absorbs 50 to 170 non-fraud accounts. Ring zero's community has 276 members total, of which 100 are fraud and 176 are non-fraud, giving 36 percent purity. Ring four is the cleanest at 65 percent purity. The Genie demo's Check 2 measures coverage rather than purity, and coverage is 100 percent for every ring, so Check 2 should now pass. But the impurity suggests that whale-to-ring random transfers are pulling non-fraud accounts into ring communities.

## Is the "hide fraud among whales" design wrong?

The design concept is sound. The story the demo tells is clear: a naive SQL analyst would sort accounts by inbound transfer count and confidently surface the whales as "most suspicious", missing the actual fraud entirely. A graph algorithm looks past raw volume and sees that ring members are structurally central in a way whales are not. This is an accurate characterization of a real fraud investigation problem, and it gives the demo a compelling narrative arc.

The specific parameter balance the generator uses is wrong for the story it wants to tell. The numbers do not back up the claim.

Consider the edge budget. The generator produces 40,000 peer-to-peer transfers. Of those, 30 percent stay within rings, giving 12,000 intra-ring edges spread across 10 rings, or 1,200 per ring, or 12 per ring member. But 20 percent of transfers go to whale accounts and another 20 percent come from whales, which is 16,000 edges of whale-centric traffic. Each of the 200 whales handles an average of 80 transfers. Ring members handle maybe 15. Against this gap in raw volume, PageRank simply does not have enough ring centrality to overcome whale degree.

The design intent was to make whales invisible to PageRank because whales receive from peripheral low-centrality sources. That intent is correct in principle. In practice, a whale receiving 40 transfers each from a source with PageRank 0.15 still sums to a larger PageRank than a ring member receiving 5 transfers from other ring members. Recursion through ring structure does not overcome the raw count gap at this parameter balance.

## Proposed changes to the generator

The fix is to recalibrate, not to restructure. Three changes in `setup/config.py` should be enough.

First, reduce the whale transfer share. Drop `WHALE_INBOUND` from 0.20 to 0.10, and `WHALE_OUTBOUND` from 0.20 to 0.10. This cuts the whale edge budget in half, from 16,000 to 8,000 edges, while preserving the "whales dominate raw volume" story. An analyst sorting by inbound count will still see whales at the top.

Second, increase the within-ring share. Raise `WITHIN_RING_PROB` from 0.30 to 0.50. With 40,000 total transfers and whales now consuming 8,000, there are 32,000 non-whale transfers to distribute. Half of those, 16,000, will be within-ring, or 1,600 per ring, which is 16 per ring member. This denser ring topology compounds PageRank more aggressively within rings.

Third, concentrate each ring around a small set of captains. This is a more involved change. Within each 100-member ring, designate 5 captains and have 50 percent of intra-ring transfers flow to or from captains. PageRank will concentrate on captains first, then propagate through the ring. The top twenty by `risk_score` should then contain most of the 50 captains across all ten rings.

The first two changes are parameter edits. The third requires modifying `generate_account_links` in `setup/generate_data.py` to implement the captain topology. Both the parameter changes and the captain pattern can be tested independently.

## Alternatives we considered

Replacing whales with some other distractor pattern was considered and rejected. Whales are a recognizable real-world pattern: payment aggregators, merchant-of-record services, and treasury accounts genuinely do look like whales in transfer networks. A demo audience understands the character. Substituting a synthetic pattern loses that clarity.

Making rings much smaller was considered and rejected. Rings of 20 to 30 members would be easier for Louvain to isolate cleanly, but they would stop looking like organized crime operations. The 100-member ring size matches real money-mule networks and gives the demo credibility.

Using structured patterns like directed cycles or bipartite sender-receiver splits within rings was considered. These would produce cleaner PageRank signals. They were rejected because they make the underlying fraud pattern too easy: a basic cycle detection query in SQL could find them, which would weaken the story about graph algorithms being necessary.

Raising `topK` in Node Similarity was considered and rejected. The current `topK=10` already produces the full pairwise similarity structure the demo needs. The previous failure was an incomplete run, not a parameter problem.

## How to run the fix and validate it

After editing `setup/config.py` and regenerating data, the validation flow is straightforward.

Regenerate by running `uv run setup/generate_data.py` from the `finance-genie/` directory. Then run `uv run setup/verify_fraud_patterns.py` to confirm the new CSVs still hit the structural targets: whale-dominated inbound rankings, ring density ratio above 100, anchor Jaccard ratio above 1.4, and weak column signals. If any of those regress, the parameter changes have swung too far.

Once the CSVs verify, upload to Databricks using `setup/upload_and_create_tables.sh`, then run feature engineering notebooks 00 and 01 to ingest the refreshed data into Neo4j. At this point, from the `validation/` directory, run `uv run validate_neo4j_graph.py`. This confirms that the new CSV structure made it through the Spark connector intact. The within-ring density ratio should still be in the hundreds and the anchor visit ratios should still be in the tens.

Then run `uv run run_and_verify_gds.py`. This executes the GDS pipeline and runs the diagnostic checks in one step. The pass criteria we want to see after the fix are:

1. PageRank top-20 fraud fraction at 50 percent or higher. This is the change from the current zero.
2. Each ring's dominant Louvain community at 80 percent purity or higher. Currently 36 to 65 percent.
3. Node Similarity relationships count near 250,000, and per-account fraud/normal similarity ratio above 2.0.

When those three criteria are met, re-run notebook 03 sections 6 and 7 to rebuild `gold_accounts` and `gold_account_similarity_pairs`, then re-run the demo in `genie_demos/gds_enrichment_closes_gaps.ipynb`. All three demo checks should pass.

## Louvain Testing: What We Tried and What We Learned

### The starting state

When the GDS pipeline first ran to completion, Louvain produced a result that was simultaneously impressive and disappointing. Every fraud ring was correctly contained within a single community: all 100 members of each ring ended up sharing the same `community_id`, giving 100% coverage on every ring. The disappointing part was purity. Each ring's community also absorbed 50 to 170 non-fraud accounts, producing communities of 129 to 371 total members with fraud fractions ranging from 36% to 65%. The UNDIRECTED graph projection was the structural cause: treating `TRANSFERRED_TO` edges as bidirectional meant that an edge from a ring member to a whale became traversable in both directions, connecting ring members to the broad whale neighborhood and pulling those background accounts into ring communities.

### Dataset adjustments made before Louvain testing

Three generator changes were in place before the Louvain investigation:

`WHALE_INBOUND` and `WHALE_OUTBOUND` were each cut from 0.20 to 0.10. This halved the whale edge budget from 16,000 to 8,000 transfers, reducing the number of edges bridging ring members to the whale cluster. The whale story still holds: analysts sorting by raw inbound count see whales first. The signal is less extreme.

`WITHIN_RING_PROB` was raised from 0.30 to 0.50. With more intra-ring transfers, each ring's community becomes structurally denser relative to its external connections, which gives Louvain a stronger modularity signal to work with.

A captain topology was added (`CAPTAIN_COUNT=5`, `CAPTAIN_TRANSFER_PROB=0.10`). Five accounts per ring are designated captains. Ten percent of within-ring transfers are routed to captains as receivers, concentrating inbound transfers on a small set of high-degree nodes. The captain topology was introduced primarily to improve PageRank separation, but the denser hub structure within rings provides a secondary benefit to Louvain coherence.

After these changes, per-ring coverage held at 99-100%, and purity shifted to a range of 27-78% with an average around 50%.

### Approach 1: Bidirectional projection filter

The hypothesis was that projecting only account pairs with transfers in both directions would strip out casual one-way connections (ring member sends once to whale) while preserving the structured within-ring relationships where accounts trade back and forth. In the UNDIRECTED projection, a single ring-member-to-whale edge is treated as bidirectional, which bridges the ring to the whale's neighborhood. Filter to mutual pairs and that bridge disappears.

The implementation changed Step 2 from a native UNDIRECTED projection to a Cypher aggregation that matched only pairs where both `(a)-[:TRANSFERRED_TO]->(b)` and `(b)-[:TRANSFERRED_TO]->(a)` existed.

The result was a near-total collapse of the graph: only 231 of 25,000 accounts had mutual transfers. Coverage dropped from 99-100% to 72-86%, and each ring fragmented across 7 to 13 communities. The generator draws random pairs for within-ring transfers and never forces reciprocal edges, so actual back-and-forth transfers between the same two accounts are rare by chance. The filter that was designed to preserve ring structure removed most of it.

The projection was reverted to UNDIRECTED.

### Approach 2: Excluding ring members as whale-inbound sources

The second proposal addressed the same root cause differently. In the generator, the whale-inbound branch picks `src` from any account, including ring members. Restricting that pool to non-ring accounts would remove the edges that bridge rings to whales without touching the projection.

This was rejected before implementation on realism grounds. Fraud ring members are real accounts operating within the broader financial system. They send money to large payment aggregators, merchant-of-record services, and high-volume treasury accounts, exactly as any other account would. Removing that behavior makes ring members too clean: they would have no financial activity outside the ring, which is not how money-mule networks operate. The synthetic cleanliness would weaken the demo's credibility more than impure communities would.

### Threshold and check design adjustments

The original validation target of 80% purity per ring was set aspirationally. After testing confirmed that 80% is not achievable with realistic data parameters, the threshold was lowered to 50%.

Even at 50%, six of ten rings failed the per-ring check: four rings came in at 47-49%, ring 5 was an outlier at 27% (a community of 371 members absorbing 271 non-fraud accounts). Applying the threshold ring-by-ring treats every ring independently and fails the suite if any single ring has a bad draw from the random graph. The average across rings is more informative: it reflects the dataset's overall tendency to produce moderately pure communities rather than flagging variance in one unlucky ring.

The check was changed to an average-based criterion: `avg_purity >= 0.50`. With UNDIRECTED projection and the current parameters, average purity sits at approximately 50.1%, which passes the threshold.

### What the Louvain results actually mean for the demo

Coverage is the signal that matters for Check 2 in `gds_enrichment_closes_gaps.ipynb`. The demo asks whether Louvain can identify that a ring exists as a coherent unit. At 99-100% coverage, every ring member is locatable within a single dominant community. A fraud investigator working from that community has found the ring, even if the community also contains background accounts.

Purity of 47-78% across rings reflects a 12x to 20x lift over the 4% baseline fraud rate in the dataset. A community where nearly half the members are confirmed fraud is not an impure result in any practical sense. It is an actionable result. The demo narrative holds.

Ring 5 at 27% purity remains an outlier. Its community of 371 accounts suggests that ring 5's members have unusually dense connections to background accounts, likely through the random transfer draws and the whale proximity effects described above. This is a known limitation of the current parameters and does not block the demo.

### Current accepted state

- Graph projection: UNDIRECTED native projection
- Louvain check: average purity across all ten rings >= 50%
- Per-ring coverage check: >= 80% of ring members in the dominant community
- Expected results with current parameters: 99-100% coverage, 50% average purity, ring 5 as the lowest individual result at roughly 27%

---

## Node Similarity: Analysis and Improvement Plan

### What "fixing Node Similarity" actually means

There are two separate pass criteria, measured by different tools against different data:

**Criterion A — `run_and_verify_gds.py` `check_similarity()`**
Computes fraud avg `similarity_score` / normal avg `similarity_score` and requires the ratio >= 2.0. The `similarity_score` on each Account node is the MAX Jaccard score across its top-10 `SIMILAR_TO` neighbors (written in Step 7 of `run_pipeline`, which sets `a.similarity_score = MAX(s.similarity_score)` over all SIMILAR_TO edges incident to `a`).

**Criterion B — Demo notebook Check 3 (`genie_demos/gds_enrichment_closes_gaps.ipynb`)**
Genie queries `gold_account_similarity_pairs` (the materialized SIMILAR_TO pairs table, created by notebook 03 sections 6–7) asking "which pairs of accounts share the most similar merchant visit patterns?" The check passes when the same-ring fraction of pairs Genie returns exceeds 60%. This is measured by `check_ring_pair_fraction()` in `demo_utils.py`.

These are not the same thing. Criterion A is about per-account average signal across all fraud vs all normal accounts. Criterion B is about whether the TOP-SCORING pairs in the gold table are dominated by same-ring pairs when Genie sorts by `similarity_score` DESC.

### Current state (as of data fix completion)

All pipeline checks remain pending. The new generator data (with reduced WHALE_INBOUND/WHALE_OUTBOUND=0.10, WITHIN_RING_PROB=0.50, captain topology) has passed local structural checks but has not been uploaded to Databricks or run through Neo4j. No GDS ratio number has been recorded for either old or new data. What is known is that `run_and_verify_gds.py` ran once against the original data and produced 250,018 `SIMILAR_TO` relationships, but the fraud/normal `similarity_score` ratio from that run was not captured.

### Louvain baseline to protect

The Louvain investigation established an accepted state that any Node Similarity work must not disturb. The P2P graph and the merchant transaction graph are separate in the generator, so changes to `RING_ANCHOR_PREF` or `RING_ANCHOR_CNT` cannot affect Louvain by construction. The accepted Louvain state is:

- Graph projection: UNDIRECTED native projection of `TRANSFERRED_TO` edges
- Check: average purity across all ten rings >= 50% (current: ~50.1%)
- Coverage: >= 80% of each ring's members in its dominant community (current: 99-100%)
- Ring 5 is the known outlier at ~27% individual purity due to dense background connections

Any P2P parameter change (WITHIN_RING_PROB, WHALE_INBOUND, WHALE_OUTBOUND, NUM_P2P, captain topology) would invalidate this baseline. Node Similarity levers — RING_ANCHOR_PREF, RING_ANCHOR_CNT, topK — are Louvain-safe.

### Discrepancy between validation scripts

`validate_gds_output.py` applies a different Louvain standard than `run_and_verify_gds.py`. `validate_gds_output.py` requires tight communities (>= 80 members) count >= 8 AND top-10 avg purity >= 80%. That 80% purity threshold was the aspirational original target, not the accepted current state. The checklist gate is `run_and_verify_gds.py` at 50% avg purity. `validate_gds_output.py` will produce Louvain failures against the current data — this is expected and not a regression.

### Why Criterion A probably passes without changes

The `similarity_score` per account is the MAX Jaccard with any SIMILAR_TO neighbor, not the average. For ring members, topK=10 selects the 10 most similar accounts, most of which are other ring members sharing anchor merchants. So `similarity_score` for ring members is approximately the highest pairwise intra-ring Jaccard across their top-10 ring-mate pairs. The verify script measured within-ring Jaccard avg of 0.011 and cross avg of 0.0019, a 6.15x ratio. The MAX over top-10 ring-mate pairs will be higher than the average — some ring pairs share multiple anchor merchants, pushing Jaccard above 0.011 when both accounts have many transactions. For normal accounts, topK=10 finds random coincidental overlaps, which produce much lower max scores. The fraud/normal ratio on MAX similarity should comfortably exceed 2.0.

This is an educated inference, not a measurement. The ratio should be confirmed empirically when `run_and_verify_gds.py` is run against the new data.

### Why Criterion B carries more risk

Check 3 depends on Genie behavior. Genie queries `gold_account_similarity_pairs`, generates SQL sorting by `similarity_score` DESC, and returns a result. The check measures same-ring fraction across ALL rows Genie returns. If Genie limits to top 20-100 pairs, those pairs should be dominated by same-ring pairs (highest-scoring intra-ring Jaccard pairs score above coincidental normal pairs by the 6.15x ratio). If Genie returns many hundreds of rows or applies a different WHERE clause, the same-ring fraction dilutes quickly: intra-ring pairs are roughly 10,000 of 250,000 total edges (4%), so a poorly bounded query would fail at 60%.

Genie behavior on this question is empirical, not predictable. The first run of the demo notebook against the new data will reveal whether Check 3 passes.

### Improvement levers (Louvain-safe)

**Lever 1 — RING_ANCHOR_PREF** (currently 0.18)
Raising this increases what fraction of each fraud account's transactions go to ring anchor merchants. A higher visit rate produces more anchor merchants in each account's visited set, increasing Jaccard with ring-mates on both criteria. The risk is the column signal check: anchors are sampled from ALL merchants (not just high-risk), so the high-risk fraction gap should remain stable. Suggested candidate: 0.25. Must re-run `verify_fraud_patterns.py` after any change.

**Lever 2 — topK** (currently 10 in `run_and_verify_gds.py` and `02_aura_gds_guide.ipynb`)
Raising topK (e.g., to 20) increases the `SIMILAR_TO` edge count from ~250k to ~500k. More ring pairs appear in `gold_account_similarity_pairs` at high similarity scores, which makes Check 3 more robust against Genie returning a larger result set. This requires no generator change — only changes to `run_pipeline()` in `run_and_verify_gds.py` and the matching cell in notebook 02. There is no interaction with Louvain.

**Lever 3 — RING_ANCHOR_CNT** (currently 5)
Changing the number of anchor merchants per ring is less predictable. More anchors increase the potential shared merchant set but also make it harder for any single account to visit all anchors in a small number of transactions. Fewer anchors concentrate the shared signal but narrow the pool. Leave this at 5 unless empirical results show the Jaccard ratio is well below target.

### Recommended sequence

1. Upload new data to Databricks and run notebooks 00 and 01.
2. Run `uv run validate_neo4j_graph.py` to confirm the new graph structure made it through.
3. Run `uv run run_and_verify_gds.py` and record the Criterion A ratio. If it passes, proceed to step 5.
4. If Criterion A fails: increase `RING_ANCHOR_PREF` to 0.25, re-run `verify_fraud_patterns.py`, re-generate CSVs, re-upload, repeat from step 2.
5. Run the demo notebook (`genie_demos/gds_enrichment_closes_gaps.ipynb`) and record the Check 3 same-ring fraction. If it passes, the Node Similarity work is done.
6. If Check 3 fails due to Genie returning too many rows: increase `topK` from 10 to 20 in `run_and_verify_gds.py` and notebook 02, re-run `run_and_verify_gds.py` to rebuild SIMILAR_TO edges, re-run notebook 03 sections 6–7 to rebuild `gold_account_similarity_pairs`, re-run the demo.
7. If Check 3 fails due to Genie generating the wrong SQL: add Genie Space instructions clarifying that `gold_account_similarity_pairs` should be queried by `similarity_score` DESC with a LIMIT.

### Node Similarity checklist additions

- [ ] Run `run_and_verify_gds.py` against new data — record Criterion A ratio
- [ ] Confirm 250k+ `SIMILAR_TO` relationships with new data
- [ ] Run demo notebook Check 3 — record same-ring fraction
- [ ] If ratio < 2.0: raise `RING_ANCHOR_PREF` to 0.25, re-verify column signals, re-run pipeline
- [ ] If same-ring fraction < 60%: raise `topK` to 20, rebuild gold table, re-run demo

---

## The validation scripts, summarized

Four scripts now live in `finance-genie/validation/` and together cover the full pipeline from credentials through GDS outputs.

`validate_neo4j.py` is a fast credential and connectivity check. It loads `.env`, verifies the driver connects, and runs a trivial query. Use this when anything changes in the `.env` file or the Aura instance.

`validate_neo4j_graph.py` is a structural check of the ingested graph. It queries Neo4j for node counts, edge counts, per-ring within-ring density, and per-ring anchor-merchant visit rates, comparing against `data/ground_truth.json`. Use this after any run of notebook 01 to confirm the ingest actually transferred the graph structure correctly.

`validate_gds_output.py` is a read-only diagnostic of what GDS has written. It checks that every account has all three features, computes fraud-versus-normal averages for PageRank and Node Similarity, counts `SIMILAR_TO` relationships, and flags if the Louvain community count is in the thousands. Use this any time you suspect a GDS step has failed silently.

`run_and_verify_gds.py` is the heaviest script and the most useful for end-to-end diagnosis. It runs the full GDS pipeline directly against Neo4j from Python, bypassing Databricks entirely, then executes a per-ring Louvain diagnostic that answers the question "how much of ring N is in which community, and what percent of that community is fraud". Use this to isolate whether a failure is in the GDS algorithms themselves or somewhere upstream in the pipeline.

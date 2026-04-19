# ENRICHED_GENIE: What Genie should actually show after enrichment

## The mistake the current demo makes

The AFTER Genie Space is pointed at the same three fraud-discovery questions the BEFORE space is asked. On the AFTER side the questions return clean results, but only because the gold table contains a pre-computed `fraud_risk_tier` column and a pre-computed `is_ring_community` flag. Genie is not discovering anything. It is reading a column that was already labeled upstream by GDS, and the question "which accounts are in rings" reduces to "select where fraud_risk_tier equals high." That is a lookup, not an answer to the question the demo pretends to ask.

The confusion is that Genie appears to have gained a capability it did not gain. Genie is still a text-to-SQL surface. What changed is the catalog it reads. Asking Genie to "find fraud" over a table with a pre-labeled fraud column makes Genie look like a fraud detector, which invites the exact skepticism the REVIEW document warns about. The detection happened in GDS. Genie is just printing the answer back.

## What Genie is genuinely strong at

Genie is a high-quality translator of analyst questions into SQL over Delta tables. It is at its best on the operations that text-to-SQL systems are engineered for: aggregation, grouping, filtering, ranking, top-N lists, cohort comparisons, time-series rollups, and joins across a small number of tables with clearly labeled columns. The BEFORE space already demonstrates this strength on the raw transaction data, where Genie handles any tabular question about balances, transfer volumes, merchant categories, and per-region activity without difficulty.

The fraud questions in the current AFTER demo do not exercise this strength. They exercise Genie's ability to read a single boolean column. A demo that lands the "same spend, strictly more answers" message needs to show Genie doing what Genie does well, over a catalog that now contains structurally-defined dimensions that did not previously exist.

## What the enriched catalog actually unlocks for Genie

After enrichment, the gold schema carries three new kinds of dimension that Genie can group by, filter on, rank by, and compare across:

1. **Structural segments**: `community_id`, `is_ring_community`, `fraud_risk_tier`. These are categorical labels that behave like any other dimension in a warehouse. The difference is that the label comes from network topology rather than a row-level attribute.

2. **Structural scores**: `risk_score`, `similarity_score`, `community_avg_risk_score`. These are continuous features that can be bucketed, thresholded, averaged, or ranked like any other numeric column.

3. **Community-level aggregates**: `community_size`, `community_risk_rank`, and the whole `gold_fraud_ring_communities` table. These pre-join structure to account attributes so Genie can answer questions at the community grain without having to reconstruct community membership itself.

Every classic BI question an analyst would ask about a segment becomes available over a segment that is structurally defined. The SQL shapes are standard. The dimensions are new.

## Proposed demo questions for the AFTER space

Five categories of question, chosen because they all produce answers that were not possible from the BEFORE catalog and all fall squarely inside Genie's text-to-SQL envelope. A talk track can pick three.

### 1. Portfolio composition over structural segments

The analyst is asking "how much of my book is in this segment" rather than "who is in the segment." Genie excels at these, and they are only answerable because the segment column now exists.

- What share of accounts sits in communities flagged as ring candidates, broken out by region?
- How does total account balance split between the high and low risk tiers?
- How many distinct communities are there, and what is the distribution of community sizes?
- What fraction of transfer volume flows between accounts in the same community versus across communities?

### 2. Cohort comparisons across tiers

Classic two-cohort BI comparison, newly possible because the cohort definition now comes from the graph.

- Compare average account balance, average account age, and average monthly transaction count between the high-risk tier and the low-risk tier.
- Do accounts in ring communities concentrate in particular regions or account types, and how does that concentration compare to the overall account population?
- Are ring-community accounts newer or older than the general population?
- How does merchant-category spending mix differ between ring-community accounts and the baseline?

### 3. Rollups over already-labeled communities

GDS produced the community labels and the ring-candidate flag. The questions here do not ask Genie to find communities. They ask Genie to characterize the already-labeled set with the kind of rollup metric a business stakeholder would request about any pre-defined segment.

- For ring-candidate communities taken together, what is the total balance held by their members and what share of the book do they represent?
- Break down the ring-candidate community set by region: how many candidates sit primarily in each region, and what is their average member count?
- For each ring-candidate community, what is the ratio of internal transfer volume between members to external transfer volume outside the community, and how does that ratio distribute across the candidate set?
- Compare average account age and average account balance inside ring-candidate communities against non-candidate communities of similar size.

### 4. Operational and investigator workload questions

Once structure is a column, it can drive the same queue and capacity questions an operations team would ask about any segment.

- How many accounts would need investigator review if the bar is high risk tier, and what is the regional breakdown of that workload?
- Which regions have the highest concentration of accounts in ring candidate communities per thousand accounts?
- What is the total balance held in accounts assigned to ring-candidate communities, and how does it compare to total balance in the overall book?
- How many accounts rank first in their community by similarity score, and how are they distributed across regions?

### 5. Merchant-side questions that previously had no handle

Merchants were always in the catalog, but the BEFORE catalog had no way to group them by the structural cohort they serve. After enrichment, merchant questions can be asked conditionally on community membership or risk tier.

- Which merchants are most commonly visited by accounts in ring-candidate communities?
- For each merchant category, what share of transaction volume comes from accounts in the high-risk tier?
- Are there merchants whose customer base is disproportionately concentrated in a single community?
- Which merchants show the largest gap between the risk-tier composition of their customer base and the risk-tier composition of the overall account population?

## What should stay off-limits for Genie even after enrichment

The integrity of the framing depends on not asking Genie to do GDS's job. Three kinds of question should remain in the BEFORE space only, or be dropped entirely, because moving them to AFTER makes Genie look like it discovered structure it did not discover:

- "Find the fraud rings." The AFTER answer is a SELECT on a pre-labeled column. This is the core mistake the current demo makes.
- "Which accounts are hubs of money movement." Same pattern. The hub label lives in `risk_score`, which GDS computed.
- "Group accounts by transfer behavior." Louvain already did this. Genie is reading the group, not forming it.

The honest version of the BEFORE-to-AFTER comparison is that the BEFORE space cannot answer structural questions at all, and the AFTER space answers portfolio, cohort, community, operational, and merchant questions that have structural segments as dimensions. The discovery stays with GDS. The analyst-facing layer stays with Genie. Each system does its designed job.

## How this changes the existing demo

This is a replacement of the AFTER question set, not a relabel of the existing one. Two concrete changes follow.

### BEFORE and AFTER ask different classes of question

The BEFORE space keeps the three current structural questions: hub detection, community structure, and merchant overlap. They fail on the base tables because the answers live in network topology, not in row-level aggregates. That failure is the load-bearing evidence for the demo's claim about what tabular SQL cannot reach.

The AFTER space drops those three questions and takes the five categories proposed above. The contrast the audience sees is not "same question, better answer." It is "the analyst brings a structural discovery question to the BEFORE catalog and gets nothing back, then brings portfolio, cohort, operational, community-rollup, and merchant-composition questions to the AFTER catalog and gets the answers a business stakeholder would actually want." Discovery stays upstream in GDS. Analyst-facing queries move to whatever shape the analyst naturally asks once the structural dimensions exist.

### Verification splits by space: ground truth for BEFORE, captured-response evaluation for AFTER

The current `TEST_CASES` in `jobs/genie_run.py` grade every question with the same `check_fn` family: ring coverage, same-ring fraction, precision against known ring-member account IDs. That pattern is the right shape for BEFORE, where the question is "did Genie recover the ring structure from base tables" and the demo controls a known ground truth it can grade against. It is the wrong shape for AFTER, where the questions are portfolio, cohort, operational, community-rollup, and merchant-composition questions that do not have a ring-membership answer key.

BEFORE keeps the ground-truth pattern unchanged. Each structural question is graded against the known ring labels the generator produced, and an honest recovery miss is reported as evidence rather than as a test failure. The teaser question added to BEFORE (a preview of an AFTER-class question) is reported as "not available on this catalog" without a ground-truth check; its role is narrative, not measurement.

AFTER separates the act of asking from the act of grading, across two phases of this plan. The asking-and-capturing runner lives in Phase 4 and produces no grade; it records the SQL Genie generated, the rows it returned, and any summary text, and writes that bundle to the results volume as the demo's field artifact. Grading lives in Phase 5 and operates on the captured bundle, using two evaluation approaches that never require a reference answer: response-shape and coverage checks, which declare what shape a substantive answer should carry and mark Genie answered when the response matches, and an LLM-as-judge pass that grades each response against a short rubric without seeing a reference query. Both approaches honor the key guideline — Genie is never told how to answer — and both produce automated verification without a hand-written SQL answer key.

## Implementation plan

### Key guideline

The demo never tells Genie how to answer. No SQL in the question, no column hints, no suggested joins, no reference query injected into the Genie Space. Every question is asked in plain business language exactly as an analyst would ask it, and Genie's response is captured as-is. The plan's purpose is to evaluate how well Genie handles each question and to show which classes of question Genie is good at. What Genie is allowed to read is the Unity Catalog table and column comments already in place; anything beyond that would contaminate the evaluation.

### Scope for this pass

Every change in this plan applies only to `finance-genie/automated/`. The workshop path at `finance-genie/workshop/` stays untouched. The workshop is a hands-on lab with its own pacing and narrative constraints, and folding it into this plan would double the surface area and delay the automated demo. The workshop adopts any of these changes on its own timeline, after the automated path stabilizes.

### Phase 1: Evaluate whether the generated dataset still fits

The generator in `setup/generate_data.py` is calibrated for the current fraud-discovery demo. Its ring count, ring size band, anchor merchant preference, and captain transfer probability exist to make GDS's structural signal observable inside a workshop timebox. The new question set does not rely on the same calibration, so Phase 1 is a read-and-decide pass on the generator rather than a code change.

Four questions to answer from the generator and one sample output:

- Do account attributes (balance, holder age, region, account type) carry meaningful differences between ring-member accounts and the baseline population, or do ring members look identical on row-level columns? Cohort comparison questions in Category 2 need at least modest attribute-level signal, otherwise the demo prints "no material difference" and lands flat.
- Are regions distributed broadly enough to make regional breakdowns in Categories 1 and 4 informative, or is the population concentrated in a small number of regions?
- Does the transaction generator produce enough merchant-category variety to support Category 5's merchant-side questions?
- Does the transfer generator produce enough internal-vs-external volume variance to make Category 3's ratio question interesting?

Phase 1 completes with one of three decisions: the dataset supports the new question set as-is, a small set of additive tweaks to the generator (for example a regional skew on ring accounts, or a balance tilt that correlates with community membership) makes the cohort and operational questions compelling, or the dataset stays as-is and specific questions are dropped because the data cannot animate them. No ring-structure parameters change under any outcome. The structural signal stays calibrated as it is.

### Phase 2: Split the Genie runner into two scripts with different purposes

`jobs/genie_run.py` today runs both spaces against one `TEST_CASES` list and grades them with one `check_fn` family. That shape fit when BEFORE and AFTER asked the same questions. It does not fit when BEFORE demonstrates an honest recovery gap and AFTER answers a different class of question.

Phase 2 splits the runner into two purpose-built scripts. `jobs/genie_run_before.py` runs the structural-discovery questions against the BEFORE space and grades honest misses as passes. `jobs/genie_run_after.py` runs the new BI-style questions against the AFTER space and grades responses against reference aggregates computed directly from the warehouse. Shared helpers (Genie client wrapping, response parsing, logging, artifact writing) move to a small support module both scripts import from. `jobs/compare_report.py` either adapts to summarize two independent runs side by side, or retires in favor of each runner writing its own artifact with a thin index page linking to both.

### Phase 3: Update the BEFORE Genie flow

The three existing BEFORE questions (hub detection, community structure, merchant overlap) stay. Their ground-truth `check_fn` implementations stay, because those checks measure whether Genie can recover ring structure from base tables and the demo still wants to show that it cannot.

Phase 3 also adds one teaser question to the BEFORE run, drawn from the AFTER category set. The teaser question is *What share of accounts sits in communities flagged as ring candidates, broken out by region?* Asked against the BEFORE catalog it cannot land cleanly because the community label and ring-candidate flag do not exist in base tables; Genie either reports that the columns are missing or returns an off-target response. The teaser's role is to preview what the AFTER catalog will answer, so a reader of the BEFORE artifact sees both the structural-recovery gap and a concrete example of a business question waiting on enrichment. The portfolio-composition shape earns the teaser slot because its dependence on the community flag and the regional breakdown is immediately visible in Genie's response.

What also changes is the output framing. The BEFORE script reports each structural question as an honest structural-recovery miss, not as a test failure. The teaser is reported as "not available on the current catalog, answered in the AFTER run." Verdict labels read as evidence rather than shortfall. The closing summary line names the gap the BEFORE run exposes. Artifact vocabulary aligns with the position that Genie is doing its designed job on base tables and the miss is a property of what those tables carry, not a property of Genie.

### Phase 4: Rebuild the AFTER flow around asking and capturing

Phase 4 replaces AFTER's `TEST_CASES` with the five categories of questions proposed above and restructures the runner so it asks each question and captures Genie's response as an artifact. Grading is out of scope for this phase. It lands in Phase 5, after the runner stabilizes and real captured responses exist to design evaluation against.

Every question is asked to Genie exactly as an analyst would ask it, with no SQL in the question and no column hints. For each question the runner captures the SQL Genie generated, the rows returned, and any summary text, and writes the package to the results volume. The captured bundle is the demo's field artifact and the input to the Phase 5 evaluation.

Twenty questions (five categories of four each) is a lot to run on every invocation, so the question bank splits across five sampler files under `jobs/`. Each file holds a cross-cut of the category space so a single file run in isolation exercises the breadth of the demo, and the full bank splits evenly across the five files. A practical layout is four questions per file with each file drawing from four of the five categories on rotation, so that running any single file demonstrates the breadth and running all five covers every question.

The AFTER runner accepts a parameter naming which sampler file or files to run, defaulting to all five. A live demo runs one sampler when time is short. A full automated pass runs all five.

### Phase 5: Add automated evaluation on top of captured responses

Phase 5 layers grading on the responses Phase 4 captures. Two evaluation approaches carry the automated-verification requirement without telling Genie how to answer, and they compose:

- **Response-shape and coverage checks.** Each question declares what shape a substantive answer should carry. A regional-breakdown question is marked answered when the response returns a row per region with a numeric measure. A cohort-comparison question is marked answered when both cohort labels appear with comparable metrics. A top-N question is marked answered when N rows come back with the requested ranking column. Shape checks are cheap and catch non-answers and off-topic responses without prescribing a query.
- **LLM-as-judge scoring.** A judge model receives the question, the data schema description, and Genie's captured response (SQL, rows, and summary), and grades the answer on a short rubric: did the response address what was asked, are the rows sensible given the schema, is the summary coherent with the result. The rubric score is the quality signal. The judge never sees a reference answer, because there is none.

The evaluation artifact reports, per question, the shape-check outcome, the judge score, and a pointer to the captured response bundle from Phase 4 for inspection. The demo carries this artifact into customer conversations as evidence of where Genie does well on the enriched catalog and where it does not.

Phase 5 decisions to finalize before shipping: which model does the judging, where the rubric lives so it versions alongside the questions, and whether shape checks and judge scoring ship together or shape checks land first with judge scoring as a follow-up.

### What else needs to happen alongside these phases

Several surfaces change in lockstep with the script work but are not themselves script work:

- `automated/README.md` needs to reflect the new AFTER question set, state the BEFORE-and-AFTER split in the revised form, and link the two run artifacts.
- `ARCHITECTURE.md`'s description of Genie's role needs updating so the silver-to-gold narrative matches what AFTER now demonstrates.
- The AFTER block in `genie_instructions.md` can name the community, risk-tier, and similarity dimensions more prominently now that the question set leans on them.
- `SCOPING_GUIDE.md` picks up a paragraph describing the new AFTER demonstration so prospects arrive with calibrated expectations for what the live run will cover.
- REFINE_DEMO's Phase 1 vocabulary (`HUB CANDIDATES SURFACED` and its siblings) was designed for AFTER answering the three original questions. Under this plan those labels no longer describe AFTER, so they either retire or migrate into the BEFORE script as honest-miss verdicts.

### Decisions captured

- This plan is orthogonal to REFINE_DEMO. No file REFINE_DEMO covers is touched under this plan.
- No SQL is ever injected into a question or held as a reference answer.
- Grading is not part of Phase 4. It lives in Phase 5, after the ask-and-capture pipeline stabilizes.
- All five AFTER categories are in the question bank. The twenty questions split across five sampler files and a parameter chooses which files run; the default runs all five.
- BEFORE keeps its existing ground-truth `check_fn` implementations and adds one teaser question drawn from an AFTER category, previewing what the AFTER run answers.
- The confuser cohort and scale companion run after this plan, not before.
- The workshop path stays out of scope.

### Remaining open questions

- **Sampler file composition.** Four questions per file across five files gives a clean twenty, but the per-file category rotation is a Phase 4 detail. Any preference on whether each file skips a different category, or whether files are grouped by category instead of rotating across them?

## The pattern this demonstrates

The enriched catalog is the story. Three Delta columns and one rollup table added to a gold schema the customer already owns, consumed by a Genie Space the customer already runs. The same SQL shapes. The same warehouse. A strictly larger set of questions the business can put to the analyst-facing layer, because the dimension vocabulary now includes community membership, structural centrality, and merchant-overlap similarity alongside region, account type, and balance.

The fraud-ring case is one instance. The same pattern applies anywhere the business cares about a segment whose definition lives in relationships rather than in any single row: supplier-network cohorts, customer clusters with shared reference patterns, device fleets with structural affinity, entity-resolution groups. In every case the GDS stage produces the segment label as a column, and Genie answers the portfolio, cohort, and operational questions the business was always going to ask about that segment, the moment it became a dimension.

Same Databricks spend. Strictly more answers, asked and answered in the interface the analyst already uses.

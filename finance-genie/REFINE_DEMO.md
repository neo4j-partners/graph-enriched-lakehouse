# REFINE_DEMO: Implementation plan for the Finance Genie demo

## Open questions before implementation

1. **Scope.** Which phases should I execute in this pass? The plan stages them as "one day" (0+1), "three days" (adds 2+5), "one week" (adds 3), "longer runway" (adds 4). Default assumption if unspecified: Phases 0, 1, 2, 5 — the text-only phases that ship a coherent story without regenerating data or running a million-account job.

*NOTE*: Yes Phases 0, 1, 2, 5 —

2. **README.md Overview.** The Phase 0 target prose replaces the opening of the Overview. Should I (a) read the current Overview and hand you a surgical diff to approve before writing, or (b) execute the replacement directly, preserving the workshop/automated split and navigation links as called out?

*NOTE*: execute the replacement directly preserving existing content. 


3. **`automated/README.md` non-determinism paragraph.** Does the `RANK()=1` vs `LIMIT 100` worked example already live somewhere in the repo that I should move to the top, or should I draft it fresh from the pipeline's actual behavior? If drafting fresh, any prior run artifacts I should ground the numbers in?

*NOTE*: It's explained in the top of the automated/README.md

4. **`ARCHITECTURE.md` insertion point.** The new "What each GDS algorithm guarantees" section lands "after the existing stage write-ups" — do you want me to confirm the exact heading I'll insert after before editing, or trust my read of the file?


*NOTE*: i trust you.

5. **Phase 1 label strings.** Want me to list the current verdict labels and summary line in `jobs/genie_run.py` and `jobs/compare_report.py` for your review before changing them, or proceed directly to the target vocabulary?

*NOTE*:list the current verdict labels and summary line and then ask me to review .

6. **Field deck.** Phase 2's completion check says `SCOPING_GUIDE.md` is linked "from the first slide of the field deck." Does that deck exist in the repo, or is `TALK_TRACK.md` (Phase 5) the slide that link lives on?

*NOTE*: `TALK_TRACK.md` (Phase 5) the slide that link lives on

7. **Footer on every output artifact.** Phase 1 says the synthetic-dataset footer appears "on every output artifact written to `RESULTS_VOLUME_DIR`." Does that include JSON artifacts, or only the human-readable markdown/log outputs?

*NOTE*: skip that is overkill

8. **Tone guardrail.** All new prose is written forward-only as capability expansion of the lakehouse. No "previously," "now instead," or comparative framing against prior versions of the demo. Confirming this is the intended register before I start drafting.

*NOTE*: confirmed.

## About this document

This plan is written for the Databricks team and their partners. It describes how Neo4j GDS runs as a complementary silver-to-gold enrichment stage inside the Databricks Lakehouse, producing Delta columns that Genie and every other Databricks tool read without interface changes.

## Headline: Spending Same, Getting More

One sentence, held constant across every surface (README, opening slide, job output footer, closing line of the talk track):

> Same Databricks spend. Strictly more answers.

Two longer phrasings for surfaces where a one-liner reads thin:

> Your Databricks investment now answers a strictly larger set of questions.

> Every Databricks seat reads structural features alongside the row-level aggregates it already queries.

Hold one phrasing per surface so the audience hears the same idea three or four times in a session without noticing. The pitch is positive-sum for Databricks: every license, cluster hour, warehouse, and Genie seat the customer already pays for continues to be used, and Neo4j adds a small Aura instance plus a silver-to-gold enrichment stage that unlocks structural questions the lakehouse could not previously answer.

## How the value story is positioned

This section is the single authoritative source for the demo's positioning. Phase 0 and Phase 5 reference the ideas below by name rather than restating them. The demo's narrative rests on six reinforcing ideas; a strong talk track uses three of them in sequence.

**GDS fits naturally as a silver-to-gold enrichment stage.** The Databricks audience already owns medallion architecture, feature stores, and silver-to-gold transforms as vocabulary. Neo4j GDS is another transform in that sequence. Its input is relationships from Delta, its output is three scalar columns (`risk_score`, `community_id`, `similarity_score`), and its place in the DAG sits between the existing silver tables and the gold tables Genie reads. The fraud use case is one instance; the same pattern applies to supply-chain traceability, entity resolution, recommendation structure, and compliance network analysis.

**GDS and Genie play complementary roles.** Genie's job is translating analyst questions into SQL. GDS's job is translating relationship topology into scalar features. Each system operates inside its designed envelope and hands its output to the other. Genie is a flexible natural-language surface over Delta tables; placing mathematically stable graph features upstream of it means Genie has strong scalar columns to generate SQL against, which directly improves answer quality on structural questions.

**The deterministic handoff strengthens Genie's answers.** GDS algorithms have published convergence properties. PageRank converges to eigenvector centrality. Louvain converges to a modularity-optimal community partition. Node Similarity computes exact Jaccard overlap above a degree cutoff. These outputs are reproducible given a fixed projection, which means the gold columns Genie reads carry stable signal. Placing deterministic compute upstream of a natural-language translation layer is the architectural pattern that produces consistent analyst-facing answers.

**The analyst's interface does not change.** After enrichment the analyst sees three new columns in the gold schema. `risk_score` is a float. `community_id` is an integer. `similarity_score` is a float. No new data types, no new query interface, no new tool for the analyst to learn. The same Genie Space answers the same kinds of question against the richer catalog. Adoption is fast because the surface area the customer is accepting is three Delta columns, not a new product.

**The lakehouse gains a relationship-aware primitive.** The Databricks Lakehouse is already strong at aggregation, filtering, time-series analysis, and every operation that reads rows independently. Adding GDS gives it one more primitive: relationship-aware computation materialized as Delta columns. Questions like "which accounts are structurally central in this transfer network?" become answerable because the catalog now contains the column that answers them. This is capability expansion of the lakehouse the customer already owns.

**What each GDS algorithm guarantees.** PageRank guarantees eigenvector centrality. Louvain guarantees a modularity-optimal community assignment. Node Similarity guarantees Jaccard overlap. Each output is a feature with a published mathematical definition. The downstream consumer (a Genie analyst, a supervised classifier, a dashboard, a fraud investigator triaging a ranked list) adjudicates the result. GDS narrows the search space from every account to a ranked candidate set; the customer's existing Databricks-hosted workflow makes the final call.

## Phase 0: Narrative and framing (half day, text only)

Edits to three markdown files. No code changes. Every narrative change below implements one or more of the ideas in "How the value story is positioned" above; use that section as the source of the positioning and the prose below as the ready-to-paste target language.

**`finance-genie/README.md`.** Replace the Overview opening with target prose of the form:

> The Finance Genie demo shows what becomes possible when Neo4j GDS runs as a silver-to-gold enrichment stage inside a Databricks Lakehouse. The pipeline reads relationships from the existing silver tables, runs three deterministic graph algorithms in Neo4j Aura, and writes three scalar columns (`risk_score`, `community_id`, `similarity_score`) back into the gold layer. Genie, SQL warehouses, dashboards, and downstream ML read those columns without any interface change. The fraud use case is one instance of a broader pattern that applies any time the answer lives in relationships rather than individual rows.

Keep the remainder of the existing Overview (the workshop/automated split, the navigation links) intact.

**`finance-genie/automated/README.md`.** Keep the one-line purpose statement. Immediately below it, surface the Genie non-determinism discussion (including the worked `RANK()=1` vs `LIMIT 100` example) as the first substantive paragraph. The framing: deterministic graph features upstream give Genie stable columns to generate SQL against, which is why the AFTER space produces consistent structural answers. Link to `SCOPING_GUIDE.md` (Phase 2) from the same section.

**`finance-genie/ARCHITECTURE.md`.** Add a new section titled "What each GDS algorithm guarantees" after the existing stage write-ups. Three short paragraphs, one per algorithm, each naming the mathematical guarantee (eigenvector centrality for PageRank, modularity-optimal community partition for Louvain, Jaccard overlap for Node Similarity) and the downstream consumer (investigator, classifier, Genie, dashboard) that adjudicates the feature.

**Completion check.** Phase 0 is complete when the `README.md` Overview opens with the target prose above, `automated/README.md` leads with the non-determinism paragraph immediately after the purpose statement, and `ARCHITECTURE.md` contains the new guarantees section.

## Phase 1: Output vocabulary (half day, string edits only)

`jobs/genie_run.py` emits per-question verdict labels and a closing summary. Set them to feature-framed vocabulary so the sample output the demo prints matches the story the narrative tells.

Target labels:

- `HUB CANDIDATES SURFACED` for the hub-detection question.
- `COMMUNITY STRUCTURE SURFACED` for the community-structure question.
- `MERCHANT-OVERLAP CLUSTERS SURFACED` for the merchant-overlap question.
- Closing summary line: `Summary: Structural signal surfaced in N/3 tests. Candidates returned for investigator review.`

Add a one-line footer to every run on both BEFORE and AFTER spaces:

> Synthetic dataset. Structural-signal ratios are theoretically scale-invariant; absolute precision numbers reflect the teaching dataset. See `SCOPING_GUIDE.md` for production-scale guidance.

`jobs/compare_report.py` uses the same vocabulary so the BEFORE/AFTER markdown comparison reads consistently.

**Completion check.** Phase 1 is complete when a sample run against either Genie Space prints the new per-question labels on all three questions, the closing line reads `Summary:`, and the footer appears on every output artifact written to `RESULTS_VOLUME_DIR`.

## Phase 2: Use case scoping guide (one hour, new file)

Create `finance-genie/SCOPING_GUIDE.md`, roughly one page, describing where this enrichment pattern applies well on Databricks and what adjustments the customer should plan for as their dataset grows. Written for a Databricks AE or partner SE to forward to a customer ahead of a meeting, so the customer arrives with calibrated expectations.

Four short sections:

1. **What this pattern produces.** GDS writes three scalar columns to the Delta gold layer. Any Databricks tool that reads a Delta table reads the enriched columns without modification.

2. **Where it applies well.** Fraud-ring surfacing, entity resolution across customer data, supplier-network risk analysis, recommendation structure, and compliance network review. Each is a workload where the answer lives in relationships rather than individual rows.

3. **Dataset size and calibration.** The live workshop dataset (25,000 accounts, 4% ring membership) is calibrated for an observable signal inside a 20-minute demo window. The pipeline shape (projection definition, algorithm configuration, gold-table DDL) is unchanged at production scale; the signal parameters inside the data generator and the verification thresholds in `verify_gds.py` are reviewed per dataset. Signal ratios the algorithms detect are theoretically invariant to base rate when ring mechanics scale proportionally. Phase 4 of this plan publishes an empirical result set that verifies the claim at one million accounts and 0.1% ring membership.

4. **What to plan for at production scale.** A larger Aura instance for the GDS stage, a larger investigator or model capacity downstream to triage a longer candidate list, and a base-rate-aware threshold on `fraud_risk_tier` or the equivalent column. The Databricks side of the pipeline (ingest, gold production, Genie Space, validation) scales on the same warehouse and cluster configuration the customer already runs.

**Completion check.** Phase 2 is complete when `SCOPING_GUIDE.md` exists in `finance-genie/`, runs under two pages, and is linked from the top of both READMEs and the first slide of the field deck.

## Phase 3: Confuser cohort (optional, one to two days)

Adds realism to the synthetic data. Extend `setup/generate_data.py` with one new cohort: small non-ring communities of 20-80 accounts that share merchant preferences and transfer patterns for benign reasons (family units, commuter corridors, small-business payroll clusters, university cohorts). Introduce two to three cohorts totaling a few hundred accounts. Add `NUM_CONFUSER_COHORTS` and `CONFUSER_SIZE_RANGE` to the generator configuration, mirroring the existing ring-generation logic without captain absorption and without intra-ring transfer elevation.

Regenerate data, rerun the full pipeline, and update `diagnostics/verify_fraud_patterns.py` and `validation/verify_gds.py` to expect some non-ring communities in the candidate-size band. Update the sample output embedded in `automated/README.md` so the published artifact matches the new data. The community-structure story then becomes "GDS produced a ranked candidate list where real rings sit above benign lookalikes," which matches what a production fraud workflow actually consumes.

Skip if the time budget does not allow. Phases 0, 1, and 2 produce a coherent demo without it.

**Completion check.** Phase 3 is complete when regenerated data includes at least two confuser cohorts, the pipeline runs end-to-end against it, `verify_gds.py` reports rank separation between ring communities and confuser communities, and the sample output in `automated/README.md` reflects the new data.

## Phase 4: Scale companion (optional, overnight plus publishing)

Run the existing pipeline once offline at `NUM_ACCOUNTS=1_000_000`, `FRAUD_RATE=0.001`, ring size held in the current band. The generator and pipeline are already parameterized; no code changes required. Capture the `verify_gds.py` summary and the Genie run artifacts. Publish them under `finance-genie/scale_companion/` as a static result set with a one-page README showing that the signal ratios held at production base rate and that the pipeline itself ran unchanged.

Skip if Aura capacity at that scale is not available in the current time budget. Its sole purpose is to give any Databricks customer asking about scale a second result set they can forward.

**Completion check.** Phase 4 is complete when `finance-genie/scale_companion/` contains the `verify_gds.py` summary, the Genie run JSON artifacts from both BEFORE and AFTER spaces, and a one-page README reporting the signal ratios at production scale.

## Phase 5: Field talk track (half day, prose only)

Produce `finance-genie/TALK_TRACK.md`, a short script that a Databricks account team or partner SE can read off a slide. The talk track draws its positioning directly from "How the value story is positioned" above; select three of the six ideas and sequence them as open, middle, and close.

Recommended sequence:

1. **Open** with **GDS fits naturally as a silver-to-gold enrichment stage** so the audience knows where the work lands in the architecture they already run.
2. **Pivot** on **The deterministic handoff strengthens Genie's answers** to explain why the order of compute matters, then show the BEFORE and AFTER Genie runs as evidence.
3. **Close** on **The lakehouse gains a relationship-aware primitive** to land capability expansion, and end on the headline sentence: `Same Databricks spend. Strictly more answers.`

Handle scale questions by referencing `SCOPING_GUIDE.md` directly rather than carrying scale material on the slide.

**Completion check.** Phase 5 is complete when `TALK_TRACK.md` exists, runs to no more than one slide of bullet points, references the three named sections from "How the value story is positioned" rather than restating them, and closes with the headline sentence.

## What stays unchanged

Every piece of the existing pipeline survives intact:

- `setup/generate_data.py` (unless Phase 3 is undertaken; the change in that phase is additive)
- All GDS algorithm code and parameters in `validation/run_gds.py`
- `jobs/neo4j_ingest.py`, `jobs/pull_gold_tables.py`, `jobs/validate_gold_tables.py`
- All Delta schemas in `sql/schema.sql` and `sql/gold_schema.sql`
- Genie Space table bindings, sample questions, and instruction text (the honest Genie behavior on base tables is what the demo depends on; adding SQL hints to rescue specific findings would weaken the comparison)
- All verification thresholds in `jobs/gold_constants.py` and `validation/verify_gds.py`
- The parameters and ring structure that make the algorithms' mathematical guarantees visible inside a workshop timebox

The mathematics and the plumbing are already in place. The work is in the surfaces the customer reads.

## Execution order under time constraints

- **One day available:** Phases 0 and 1. The narrative and output vocabulary ship a demo that tells the capability-expansion story on every surface a customer sees.
- **Three days available:** add Phases 2 and 5. The scoping guide and the talk track turn the demo into something the Databricks field can carry into customer meetings with minimal preparation.
- **One week available:** add Phase 3. The confuser cohort is the highest-impact technical improvement available and lifts the demo toward a more production-realistic shape.
- **Longer runway:** add Phase 4. Publishing a production-scale result set pre-empts the scale question for any customer who asks.

## Close

The Finance Genie demo shows what becomes possible when Neo4j GDS runs as a silver-to-gold enrichment stage inside a Databricks Lakehouse. The Databricks tools the customer already uses (Unity Catalog, Genie, SQL warehouses, dashboards, downstream ML) read three new Delta columns and start answering questions that were previously out of reach. The customer keeps every license, every workflow, and every analyst interface, and the existing Databricks investment does more work.

Same Databricks spend. Strictly more answers.

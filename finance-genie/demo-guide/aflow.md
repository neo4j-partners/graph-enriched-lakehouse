# Automated Pipeline Rework Plan

## The Core Shift

The current BEFORE run is a failure test. It asks three structural-topology questions that Genie cannot answer from flat rows, expects no meaningful response, and labels each result "STRUCTURAL GAP CONFIRMED." That framing makes Genie look broken.

The new flow inverts this. The BEFORE run asks a question Genie can answer from the base Silver tables, successfully and fluently, and returns a plausible-sounding list of merchants. The problem is that the answer is wrong: it ranks merchants by overall visit volume, which is a popularity ranking, not a fraud signal. The AFTER run asks the related enriched question and returns a visibly different list of merchants where ring-community accounts cluster disproportionately. The gap between the two lists is the demo's argument. The framing is expansion, not limitation recovery.

This distinction is the hinge the plan turns on. Every change below follows from it.

---

## Step 0: Verify the Merchant Lists Separate (Blocking Gate)

Before changing any code, run both anchor queries against the current data and compare the two merchant lists:

- **Before query**: top merchants by visit count across all accounts, no enrichment, against Silver tables only
- **After query**: top merchants by visit count filtered to accounts whose `fraud_risk_tier` is `high` in `gold_accounts`, joined to the transactions table

The two lists need to be visibly different. Not statistically different. Visibly, immediately different in a way someone without domain knowledge can see at a glance. The FINRA benchmark from `flow.md` is the standard: the before answer should look like a generic popularity ranking (high-volume chains), and the after answer should look like a specific, anomalous set of merchants that no ordinary popularity argument would surface.

The separation risk is real. Anchor merchants currently receive roughly 35 extra visits from ring members on top of a base visit rate of about 33 per merchant. That may not be enough to push them off the overall-popularity leaderboard, which would make the two lists overlap heavily and collapse the demo's argument. If the lists do not separate clearly, increase `RING_ANCHOR_PREF` and/or `RING_ANCHOR_CNT` in `config.py`, regenerate the data, and re-run `validation/verify_gds.py` to confirm GDS signal still clears its thresholds. Do not proceed to any code changes in the pipeline until this gate passes.

---

## Step 1: Strip the Ground-Truth Metric Framework from the BEFORE Run

The following machinery in `jobs/01_genie_run_before.py` has no role in the new flow and should be removed entirely:

- The three structural-discovery questions: hub detection, community structure, and merchant overlap
- The precision@20, ring-coverage fraction, and same-ring-pair-fraction computations that measured Genie's answers against `ground_truth.json`
- The verdict strings "STRUCTURAL GAP CONFIRMED" and "UNEXPECTED SIGNAL FOUND"
- The teaser question asking what share of accounts sit in ring-candidate communities by region, and the "NOT AVAILABLE ON THIS CATALOG" response pattern

The `GROUND_TRUTH_PATH` variable should stay in `.env` because `validate_gold_tables.py` still needs it. It just stops being a dependency of the BEFORE Genie run.

The BEFORE run's only job in the new flow is to ask one question against the Silver tables and capture what Genie returns.

---

## Step 2: Replace the BEFORE Questions with the Before-Anchor Question

The single question for the BEFORE run, asked against Silver tables only:

> Which merchants are most commonly visited by accounts with the highest total transaction volume?

Genie can answer this. It will return a list of merchants ranked by visit count from high-volume accounts. That list is the before answer: a plausible result that any analyst would reach for, produced entirely from row-level SQL, that says nothing about ring structure.

The artifact records the question text, the SQL Genie generated, the merchant names and visit counts returned, and any summary text Genie produced. There is no grading. The artifact is simply the answer Genie gave.

---

## Step 3: Restructure the AFTER Run Around the Anchor

The AFTER run in `jobs/05_genie_run_after.py` should open with the after-anchor question, then continue with the category sampler questions as supporting material.

**The anchor question**, asked first and stored at the top level of the artifact:

> Which merchants are most commonly visited by accounts in ring-candidate communities?

This query requires `gold_accounts` filtered by `fraud_risk_tier` joined to the Silver transactions table. Confirm the join path works before treating this as done.

**The category sampler questions** follow the anchor without changes. They represent the analyst workflow described in flow steps 10 and 11: ordinary Genie queries over enriched Gold columns, framed as the expanded toolkit rather than the demo's headline. All five categories remain. They move to a second section of the artifact, clearly labeled as supporting questions rather than the anchor.

Inside `cat5_merchant.py`, add the after-anchor question as the first item in the `QUESTIONS` list so it can be selected deterministically when time is short, without relying on random sampling.

---

## Step 4: Update the Artifact Schema

`jobs/_genie_run_artifact.py` defines the JSON structure written to the UC Volume.

For the BEFORE artifact: remove the verdict, expected-outcome, and metric fields. The BEFORE result is not pass/fail. Add a top-level `anchor` object containing the question text, SQL, merchant list, and summary.

For the AFTER artifact: add the same top-level `anchor` object for the anchor question. Keep the existing structure for category-sampler results and label them as supporting questions.

In `setup/report.py`, the comparison output should produce a side-by-side view of the two anchor answers: the BEFORE merchant list on the left, the AFTER merchant list on the right. This is the artifact the presenter puts on screen at the top of the demo.

---

## Step 5: Update the Genie Space Sample Questions

`setup/provision_genie_spaces.py` configures both spaces with sample questions that Genie uses to calibrate its behavior. Replace the current structural sample questions.

**BEFORE space** (Silver tables only): replace sample questions with the before-anchor question and one or two other volume-proxy questions from the reworks list in `flow.md`, such as the top-10%-by-transfer-volume book share question. These orient the space toward row-level, volume-based answers.

**AFTER space** (Silver plus Gold tables): replace sample questions with the after-anchor question and the shortlisted after questions from `flow.md`: ring-candidate book share and investigator review workload. These orient the space toward community-based, tier-filtered answers.

---

## Step 6: Review `genie_instructions.md`

The instructions embedded in the Genie spaces help Genie understand what the tables contain and what kinds of questions belong to each space.

For the AFTER space, confirm that the instructions describe `gold_accounts.fraud_risk_tier` and `community_id` clearly enough that Genie filters on them correctly when asked about ring-candidate communities. If the instructions currently explain those columns in terms of "ring-candidate detection" or similar framing that requires GDS context to interpret, rewrite them to describe the columns in plain business terms: `fraud_risk_tier` classifies accounts by their structural position in the transfer network, `high` means the account belongs to a cluster with elevated internal transfer density.

Remove any language that frames the demo around what Genie cannot do. The instructions should describe what the enriched catalog makes available, not what the base catalog lacked.

---

## Scope Boundary: Single Anchor

This plan uses **merchant favorites** as the sole anchor question. The before question asks which merchants high-volume accounts visit most; the after question asks which merchants ring-community accounts visit most. Book share and investigator workload from the shortlist move to the category sampler section as supporting after-questions.

This matches the presenter cue in `flow.md`: hold on the two answers until someone asks how the second list was generated. One before answer and one after answer. The audience's question is the invitation to explain the architecture.

---

## What Does Not Change

- The four pipeline jobs that run between the two Genie runs: Neo4j ingest, GDS execution, Gold table production, and Gold table validation
- Data generation unless Step 0 reveals a separation problem
- The Gold table schema and the three Gold tables themselves
- `validation/` and `diagnostics/` scripts
- `ground_truth.json` and `validate_gold_tables.py`
- The CLI runner and job submission infrastructure
- The `_demo_utils.py` Genie API wrappers

# Proposal: Updating `slides/slides.md` to Match `flow.md`

## What changes in the deck

The current deck builds the argument bottom-up: problem → Genie baseline → graph database → GDS → pipeline → payoff. The audience only sees the payoff after ~12 slides of scaffolding.

`flow.md` inverts this. The deck now runs in three parts over 15 minutes:

1. **Anchor** — one fraud question with a before answer and an after answer, side by side. Let the gap speak before any architecture is introduced.
2. **Architecture** — triggered by the audience question "how did you get that?". Explain why SQL cannot reach the after answer and why a graph database can, then show how graph and lakehouse work together.
3. **Pipeline** — Load, GDS, Enrich, Query. How the columns that produced the after answer are built.

A short **Close** reframes the work as expansion of the analyst's toolkit (not a Genie fix). **Fill-in / Q&A** slides cover generalization and defensibility.

Framing shift to apply throughout: *expansion, not limitation recovery*. The enriched lakehouse unlocks a new class of questions for Genie. It is not a patch for a Genie shortcoming.

## Slide-by-slide mapping

Style stays as today: short bold lead, one-line follow-up, four to five bullets max. Do not paste the prose paragraphs from `flow.md` into slides — those paragraphs are the reasoning behind the slide, belong in speaker notes, and should be compressed to a single takeaway on the slide itself.

### Title (keep as-is)

`# Graph-Enriched Lakehouse` / `Combining Databricks Genie with Neo4j Graph Data Science`. No change.

### "What This Talk Covers" (rewrite)

Replace the six-point agenda with the new three-part structure:

1. **Anchor** — one fraud question, two answers
2. **Architecture** — why the second answer needed a different data layer
3. **Pipeline** — how the columns behind the second answer are built

Plus a closing line about where the pattern applies.

### Dataset + silver model image (keep)

`Demo Data Set: Synthetic Banking Network` and the `silver-data-model.png` slide stay. Both are still the right lead-in to the anchor.

---

### Anchor section (new shape)

**Slide A1 — "Fraud Doesn't Happen in One Account"**
Replaces `Financial Crime Is a Network Problem` and `A Fraud Ring Is a Subgraph`. One slide, four bullets:

- Rings, mule operations, structuring: activity spread across dozens of accounts on purpose
- Each transaction looks clean in isolation
- The scheme is a shape across accounts, not a row
- Row-level aggregation cannot produce a property that lives in connections

**Slide A2 — "Merchant Favorites: One Question, Two Answers"**
This is the anchor reveal. Two columns side by side, no architecture yet.

Question: *"Which merchants are most commonly visited by accounts in ring-candidate communities?"*

| Before (raw lakehouse) | After (enriched lakehouse) |
|---|---|
| Top merchants by overall visit count — familiar chains, sounds plausible | Specific list of merchants where ring-community members cluster disproportionately |

Closing bullet: *"Same question. Different answer. Which one would you investigate?"*

Speaker note: hold on the two answers until someone asks "how did you get that?" — that is the invitation into Architecture. If nobody asks, offer it.

This slide replaces the current `Genie on the Enriched Catalog: One Question, Two Sources`, which had the same question but only showed the after side and was positioned late. Move it to the front and give it a before column.

---

### Architecture section (three slides, compressed from six)

**Slide B1 — "Some Questions Are About Connections, Not Sums"**
Replaces `Structural Questions Require a Different Data Layer`. Three-bullet version:

- How central an account is in the flow of money
- How tightly a group of accounts trades within itself
- Whether two accounts route through the same merchants

Closing bullet: *"The answer is in the pattern, not in any one account."*

**Slide B2 — "SQL Starts from an Account. A Graph Starts from a Pattern."**
Merges `Why a Graph Database Answers What SQL Cannot` and `What We Need: Better Columns`. Three bullets:

- SQL needs a starting point — a specific account ID
- A graph database needs only the pattern and finds every instance
- Structural questions need a data layer built for connections

**Slide B3 — "Graph and Lakehouse Work Together"** (new, replaces `What Genie Excels At` and adjacent slides)

- Graph is the right layer for connection questions
- Lakehouse is the right layer for aggregates, joins, and the BI questions Genie already handles well
- Compute patterns in the graph → land as columns in the lakehouse → Genie queries them as ordinary dimensions

This is the pivot that reframes the work as expansion. It also absorbs what the current `What Genie Excels At` slide was trying to say (Genie is working as designed; we are adding dimensions).

---

### Pipeline section (keep most of current; trim)

**Slide C1 — "The Enrichment Pipeline"** (keep)
Current four-step Load/Compute/Enrich/Query slide is well-scoped. Keep as-is.

**Slide C2 — "Architecture at a Glance"** (keep)
The ASCII diagram slide. Keep. It is the best single-picture summary of the pipeline.

**Slide C3 — "Sample GDS Algorithms"** (keep, merge the "What GDS Excels At" slide into speaker notes)
Current slide has the three-algorithm summary. Drop the standalone `What Graph Data Science Excels At` slide — the determinism claim moves into speaker notes here, and the category-of-five-algorithm-families point is not load-bearing in the new flow.

Drop the current `Genie in Action on the Existing Catalog` slide from the main flow. It was the baseline proof in the old deck; in the new flow it is neither anchor nor architecture nor pipeline, and time is tight. Keep as an optional fill-in slide if the audience wants to see Genie on the raw catalog first.

---

### Close (two slides, rewritten)

**Slide D1 — "The Graph Finds Candidates. The Analyst Finds Fraud."**
Replaces the current `GDS Narrows the Search Space. Humans Close It.` slide with a sharper framing:

- GDS produces structural *signals*: community, centrality, similarity
- A high-risk community is a candidate, not a verdict
- The analyst runs ordinary Genie queries against the enriched Gold tables to decide what to investigate

**Slide D2 — "The Analyst's Toolkit, Expanded"**
Replaces `What the Enriched Catalog Unlocks`. Three bullets carrying the expansion framing:

- `community_id` and `fraud_risk_tier` sit alongside region, product, and balance as ordinary dimensions
- Questions that had no handle before: candidate-population sizing, regional review workload, merchant concentration by community
- `GROUP BY fraud_risk_tier`, not "find the ring"

Close with the one-liner: *"Same Genie, same SQL. New dimensions. Strictly more answers."*

---

### Fill-in / Q&A (keep two, drop the rest)

Keep:

- `Where This Pattern Applies` — entity resolution, supplier-network risk, recommendation, compliance. Still the right generalization slide.
- A single defensibility slide: GDS produces features with published mathematical definitions; humans and downstream models adjudicate, not the pipeline. Keep the current `GDS Narrows the Search Space. Humans Close It.` framing.

Drop from the main deck (move to fill-in or cut):

- `Going Deeper: Genie's Behavior in Practice` section header — not needed in a 15-minute deck
- `Deterministic Foundation, Non-Deterministic Translation` — architecturally interesting but off-anchor; keep as optional fill-in
- `Genie on Structural Questions: A Precision Problem` — the anchor before/after slide now carries this argument visually

### "Key Takeaways" (rewrite)

Current six-bullet takeaways are tuned to the old structure (column inventory, determinism, BI shapes). Rewrite to the new three-part structure:

- One question, two answers — the gap is the whole argument
- Graph for connection questions, lakehouse for everything Genie already does well
- GDS columns land in Gold as ordinary dimensions; the analyst's toolkit gets bigger, not different

## Material to pull from the old slides

- **v1 `Column Inventory Determines the Answer`** — the "proxies correlate loosely with structural quantities but do not measure them" phrasing is sharp. Consider folding into the Close section if there is room, or into speaker notes for the anchor reveal.
- **v1 `AFTER Demo: Five Question Classes Unlocked` + `One Question from Each Class`** — overlaps with the new `Analyst's Toolkit, Expanded` slide. Mine for example questions; do not re-add the five-class taxonomy, which is too granular for the new envelope.

Do not pull back the three per-algorithm slides from v1 (`PageRank → risk_score`, `Louvain → community_id`, `Node Similarity → similarity_score`). The current consolidated `Sample GDS Algorithms` slide is the right density for a 15-minute deck.

## Final slide order

1. Title
2. What This Talk Covers *(rewritten — anchor/architecture/pipeline)*
3. Demo Data Set
4. Silver Data Model (image)
5. Fraud Doesn't Happen in One Account *(new/rewritten)*
6. **Merchant Favorites: One Question, Two Answers** *(anchor reveal, new)*
7. Some Questions Are About Connections, Not Sums
8. SQL Starts from an Account. A Graph Starts from a Pattern.
9. Graph and Lakehouse Work Together *(new)*
10. The Enrichment Pipeline
11. Architecture at a Glance
12. Sample GDS Algorithms
13. The Graph Finds Candidates. The Analyst Finds Fraud.
14. The Analyst's Toolkit, Expanded
15. Where This Pattern Applies
16. Key Takeaways *(rewritten)*

Fill-in slides after the main deck: Genie in Action on the Existing Catalog; Deterministic Foundation, Non-Deterministic Translation.

## Open questions for Ryan

- The anchor reveal in slide 6 needs an actual before-answer and after-answer screenshot or table, not just descriptors. Do we have runnable queries to capture both? If the before answer is not reproducible on demand from the current Silver tables, the anchor loses its punch.

I'm going to run a live genie demo

- Is the 15-minute envelope firm? The proposed order fits 16 slides in 15 minutes at ~1 min/slide, which is tight for slide 6 (the reveal) — that slide likely wants 2–3 minutes on its own.

no I want the full flow 


# Workshop Refactor Plan

This plan describes how to align the workshop notebooks and guide files with the
flow documented in `demo-guide/flow.md`. No code is included. All changes are
described in plain English at the level of "what to add, remove, or move."

---

## The Core Problem

The current workshop leads with structural gap questions in `01_genie_before`
(hub detection, community membership, merchant pairs). Those questions require
the audience to already understand why network topology matters — otherwise the
misses look like Genie bugs rather than catalog limitations. The flow says the
opposite: lead with one question and two answers, let the gap speak without
domain knowledge, and let the audience's curiosity pull the architecture
explanation out of you.

The after notebook buries the cat5 merchant question last, even though it is the
intended anchor payoff. The before/after pair is not paired — the before answer
lives in one notebook and the matching after answer lives in a different notebook
five steps later.

---

## What Changes, File by File

### `01_genie_before.ipynb`

**Goal:** Open with the before-anchor question. Everything else moves back or
becomes secondary.

1. Add a new section at the top — before the warm-up — titled something like
   "The Anchor Question." Its single question is the before-anchor phrasing:
   "Which merchants are most commonly visited by accounts with the highest total
   transaction volume?" This runs on Silver and returns popular chains by overall
   visit count. That is the before answer: plausible, sounds like a real ranking,
   but structurally wrong because it ranks by volume, not by ring membership.

2. Keep the warm-up and analytics challenge where they are, but position them
   after the anchor question. They demonstrate Genie's baseline competence, which
   is still worth showing — just not before the anchor.

3. Move the three structural gap questions (hub detection, community membership,
   merchant pairs) to the end of the notebook. They become supporting evidence
   that the Silver catalog has no structural handle at all, not the primary
   argument. The anchor question is the primary argument.

4. Update the notebook intro cell to describe the new opening: the notebook now
   starts by asking the before-anchor, then confirms Genie's tabular baseline,
   then shows the structural gaps.

5. Update the summary cell at the bottom to call out the before-anchor answer by
   name and label it as the one the after notebook will revisit.

---

### `05_genie_after.ipynb`

**Goal:** Open with the after-anchor question to close the before/after pair,
then show the remaining categories as "here is what else you can now ask."

1. Move the cat5 merchant question ("Which merchants are most commonly visited by
   accounts in ring-candidate communities?") from position 5 to position 1. It is
   the after-anchor answer — the same question the before notebook opened with,
   now resolved. The audience sees this immediately after the pipeline runs, which
   closes the gap they saw at the start.

2. Keep the other four categories (portfolio composition, cohort comparisons,
   community rollups, operational workload) in their current order, positions 2
   through 5. They demonstrate the breadth of the new question class, which is
   the "expanded toolkit" argument from the flow's Close section.

3. Update the intro cell to make the sequencing explicit: the first question
   completes the before/after pair from the opening; the remaining questions show
   the full analyst toolkit the enriched catalog unlocks.

4. Update the summary cell to reinforce the expansion framing: the anchor closed,
   and here are four more question categories that did not exist before.

---

### `genie-guide.md`

**Goal:** Mirror the notebook reordering so the live-demo copy-paste guide
follows the same sequence.

1. Under **BEFORE**, move the before-anchor question ("Which merchants are most
   commonly visited by accounts with the highest total transaction volume?") to
   the first slot, ahead of the warm-up. Give it a heading like "Anchor Question
   (Before)" with a presenter note: hold on the result; the after answer comes at
   the start of the AFTER section.

2. Keep the warm-up and analytics challenge after the anchor, with their current
   headings and notes.

3. Keep the three structural gap questions after the analytics challenge, with
   their current headings. Their role is unchanged: confirm the Silver catalog has
   no structural handle.

4. Under **AFTER**, move the cat5 merchant question ("Which merchants are most
   commonly visited by accounts in ring-candidate communities?") to the first slot,
   under a heading like "Anchor Question (After)." Add a presenter note: this is
   the same question from the start of BEFORE; show both results side by side and
   let the gap land before moving on.

5. Keep the remaining four categories (portfolio, cohort, community rollup,
   operational workload) after the anchor, in their current order.

---

### `README.md`

**Goal:** Rewrite the descriptions of `01_genie_before` and `05_genie_after` to
reflect the 3-part flow structure (anchor → architecture → pipeline).

1. In the `01_genie_before` description, lead with: the notebook opens with the
   before-anchor question — merchants by volume — then confirms tabular baseline,
   then shows the structural gaps. The before-anchor answer is what the presenter
   holds until the after answer lands.

2. In the `05_genie_after` description, lead with: the first question closes the
   before/after anchor pair; then four more categories show the expanded analyst
   toolkit. Note that the gap between the two anchor answers is the demo's central
   argument.

3. Consider adding a short section at the top of the README that names the
   3-part flow: anchor (before/after pair), architecture (why the graph helps),
   pipeline (how enrichment was built). Readers who are new to the demo should
   be able to orient in two sentences before reading the notebook sequence.

---

## What Does Not Change

- The five notebook content sections themselves (cat1–cat5) are not being
  rewritten, only reordered.
- The structural gap questions in `01_genie_before` stay; they just move to the
  back.
- The pipeline notebooks (`02_neo4j_ingest`, `03_gds_enrichment`,
  `04_pull_gold_tables`) are not touched.
- `GENIE_SETUP.md` and `aura_gds_guide.md` are not touched.
- `06_train_model.ipynb` is not touched.

---

## Open Questions

Before implementing, answers needed on:

1. **Structural gap questions in the before notebook:** The flow.md says lead with
   the anchor and let the gap speak. The structural gap questions (hub, community,
   merchant pairs) are the current anchor — they would be demoted to supporting
   material. Is that the right call, or should they be cut entirely? Keeping them
   shows three independent structural misses, which strengthens the evidence.
   Cutting them keeps the before notebook tighter around the anchor. Which do you
   prefer?

2. **Analytics challenge and warm-up:** The flow puts the anchor first with no
   preamble. Should the warm-up and analytics challenge stay (they frame Genie's
   baseline competence before the anchor), or should the notebook go straight to
   the anchor and skip or shorten them?

3. **Side-by-side presentation:** The flow says show both answers and "let the gap
   speak." In practice, the before answer is in one notebook and the after answer
   is in a different one. Is the intent for the presenter to have both notebooks
   open simultaneously and switch between them, or is there a different
   presentation approach in mind (e.g., a single slide showing both answers, or a
   combined cell that displays both)?

4. **After notebook ordering:** If the cat5 merchant question moves to position 1
   in `05_genie_after`, the remaining four categories follow in their current
   order: portfolio → cohort → community rollup → operational. Is that the right
   order, or should they follow the flow's Close sequence (book share first, then
   investigator workload, then merchant concentration)?

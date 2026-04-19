# Finance Genie — Code Review

## Files over 1,000 lines

One file exceeds the threshold: `setup/verify_fraud_patterns.py` at 1,423 lines.

All other project files are under 500 lines, which is reasonable given their scope. The line count breakdown:

| File | Lines |
|------|-------|
| setup/verify_fraud_patterns.py | 1,423 |
| validation/run_and_verify_gds.py | 491 |
| setup/generate_data.py | 466 |
| jobs/validate_gold_tables.py | 460 |
| jobs/pull_gold_tables.py | 414 |
| jobs/genie_run.py | 346 |
| jobs/demo_utils.py | 327 |
| setup/provision_genie_spaces.py | 326 |

---

## verify_fraud_patterns.py in detail

This is the only file with a real size problem, and the reason is that it has grown to serve four different purposes that are only loosely connected:

**What it currently contains:**

1. Four structural pattern checks against the generated CSVs (whale-hiding, ring density, Jaccard similarity, column signals). This is its original and primary purpose.
2. A snapshot system: building snapshots to JSON, loading them, and comparing two snapshots against a tolerance threshold.
3. A rich terminal rendering layer: two distinct report renderers (one for check results, one for snapshot comparisons), each with their own table-building and color logic.
4. Six Genie output checks: validating CSV exports from Genie runs against ground truth, with an auto-detection function that infers check type from column names. These cover before-GDS and after-GDS cases for centrality, pagerank, louvain, node similarity, community pairs, and merchant overlap.

The Genie output CSV checks (purpose 4 above) account for roughly 400 lines on their own. They were clearly added to an existing structural verification script rather than written as a standalone module. They share no code with the structural checks; they only share the rich renderer and the ground-truth reconstruction logic. The auto-detection approach, while clever, also creates a coupling risk: adding a new Genie check type requires updating the column-signature detection function in this file even though the detection logic has no relationship to structural fraud patterns.

### How to split it

The natural split is into three files:

`setup/checks_structural.py` would contain the four core checks (`check_whale_pagerank`, `check_ring_density`, `check_anchor_jaccard`, `check_column_signals`) plus their shared helpers (`load_data`, `verify_ground_truth_matches`). This is the original soul of the file.

`setup/checks_genie_csv.py` would contain the six Genie output check functions, the CSV type detection function, and `run_genie_csv_check`. None of these depend on the structural checks, and they are conceptually downstream — they validate what Genie said, not what the dataset contains.

`setup/report.py` (or inline into `verify_fraud_patterns.py`) would hold the rich rendering functions and the snapshot comparison logic. These are used by both check families and can be imported by both.

`verify_fraud_patterns.py` itself would then be reduced to the entry point: parsing arguments, calling into the check modules, and dispatching to the renderers.

---

## Long methods

### `check_gds_output` in verify_fraud_patterns.py (lines 1172–1288, ~116 lines)

This method loads a CSV, then runs three independent analysis blocks back-to-back: PageRank distribution, Louvain community purity, and Node Similarity distribution. Each block computes its own averages, checks its own thresholds, builds its own diagnostic message, and assembles its own result dict. They share only the input DataFrame and the fraud ID set. Each block is 30–40 lines and could be extracted as a standalone function (`_check_pagerank_dist`, `_check_louvain_dist`, `_check_nodesim_dist`) with no changes to the callers. The method would then shrink to a coordinator that calls the three functions and returns their results as a list.

### `check_community_purity` in jobs/demo_utils.py (lines 173–268, ~95 lines)

This method handles four structurally different cases — groups with account rows, aggregate-only groups with a ring community map, aggregate-only groups with an `is_ring_candidate` flag, and pairs — each with its own computation and return shape. The four branches are identified early in the function via column detection, but the logic for each branch is long enough that a reader cannot hold all four in their head at once. Extracting each branch into a named helper (`_coverage_from_groups`, `_coverage_from_community_map`, `_coverage_from_ring_candidate_flag`) would make the outer function a simple dispatcher and leave each branch readable on its own. This would also make it easier to add a fifth branch later without the method growing further.

### `render_comparison_report_rich` in verify_fraud_patterns.py (lines 570–660, ~90 lines)

This method builds and prints rich-formatted panel output for snapshot comparisons. It is not long because it does complex logic — most of its length comes from constructing table rows conditionally. It could be shortened by extracting the table-building into a helper, but it is not a correctness or maintenance risk in its current form.

### `_run_checks` in jobs/validate_gold_tables.py (lines 183–382, ~200 lines)

This is the longest method in the jobs directory. It runs six sequential checks, each with its own Spark query, threshold comparison, and problem accumulation. The function is already well-structured: each check has a header comment, the Spark logic is appropriately tight, and the checks are genuinely sequential (check 2 produces `community_to_ring` which check 5 consumes). Splitting it would be premature. The length is justified by the six independent validations it needs to execute. One exception: check 2 is already extracted into `_check_ring_dominance`, which is the right pattern. Checks 4 and 6 are the most self-contained of the remaining five and would be the natural candidates if the function grows further.

### `generate_account_links` in setup/generate_data.py (lines 285–381, ~96 lines)

This function contains a 300,000-iteration loop with four conditional branches — within-ring transfers, whale inbound, whale outbound, and random background. The branches are independent and the comments on each are clear. The function is longer than it needs to be because each branch has its own inline destination-selection logic. Extracting `_pick_within_ring_transfer`, `_pick_whale_inbound_transfer`, and `_pick_whale_outbound_transfer` as small helpers would make the loop body read as a four-way dispatch rather than four embedded procedures. This is the right shape for a loop this size.

---

## Major refactoring and cleanup areas

### Duplicated `.env` injection boilerplate

Every job in `jobs/` that runs on the Databricks cluster contains an identical 8-line block at the top of the file that parses `KEY=VALUE` arguments from `sys.argv` and sets them into `os.environ`. This block is copied verbatim in `genie_run.py`, `validate_gold_tables.py`, `pull_gold_tables.py`, and `neo4j_ingest.py`. Similarly, the 7-line `__file__` / `inspect.currentframe()` fallback for resolving the module directory is duplicated across the same four files.

Both patterns belong in a shared helper, something like `jobs/_cluster_bootstrap.py`, that each job imports. When the cluster execution mechanism changes (or when a new job is added), there is currently one copy per job file to update. This is the single highest-value cleanup in the codebase.

### Ring-by-account lookup rebuilt in every check function

Seven different functions build the same `{account_id: ring_id}` mapping from a ring list: `check_genie_louvain_csv`, `check_genie_similarity_csv`, `check_genie_community_pairs_csv`, `check_genie_merchant_overlap_csv` in `verify_fraud_patterns.py`, and `check_ring_pair_fraction`, `_label_accounts`, `_build_ring_lookup` in `demo_utils.py`. The versions in `verify_fraud_patterns.py` are inline dict comprehensions with no factored helper; `demo_utils.py` has the helper but rebuilds it per call. A single `build_ring_lookup(rings) -> dict[int, int]` defined once and reused everywhere would remove this repetition and make the threshold consistent across all checks.

### `validate_gold_tables.py` duplicates `run_and_verify_gds.py` check logic

`run_and_verify_gds.py` checks PageRank separation, Louvain ring coverage, and Node Similarity ratio against Neo4j directly after GDS runs. `validate_gold_tables.py` runs six similar checks against the Delta Lake gold tables after they are written. These are not identical checks — one uses Neo4j data, the other uses Delta Lake data — but the underlying statistical logic (what constitutes a "passing" ring, what threshold makes a ring candidate) is the same reasoning expressed twice.

More concretely, `gold_constants.py` exists precisely to prevent threshold drift between `pull_gold_tables.py` and `validate_gold_tables.py`. But `run_and_verify_gds.py` defines its own constants (`PR_RATIO_MIN`, `COMMUNITY_PURITY_MIN`, `SIM_RATIO_MIN`, `RING_EXCLUSION_MAX`) without importing from `gold_constants.py`. If `COMMUNITY_AVG_RISK_MIN` changes in `gold_constants.py`, `run_and_verify_gds.py` does not see the update. The two files are currently in sync by coincidence. The relevant constants in `run_and_verify_gds.py` should either import from `gold_constants.py` or `gold_constants.py` should be extended to cover the GDS verification thresholds.

### `check_community_purity` return shape is inconsistent

In `demo_utils.py`, `check_community_purity` returns different dict shapes depending on which branch it takes. The `aggregates_community_map` and `aggregates_ring_candidate` branches return early with a dict that includes `structure_type`, `max_ring_coverage`, `groups_returned`, `total_rows`, and `passed`. The `groups` and `pairs` branches fall through to a common return at the bottom, but only after setting local variables that the aggregate branches never use. A reader tracing the function has to check whether each variable is set in every branch. All return paths should produce the same keys; the early returns are the right pattern but should produce the same shape as the fall-through return.

### Row iteration where vectorized operations would work

`check_genie_similarity_csv`, `check_genie_community_pairs_csv`, and `check_genie_merchant_overlap_csv` in `verify_fraud_patterns.py` all iterate over DataFrame rows with `for _, row in df.iterrows()`. These DataFrames are typically small (Genie result sets), so performance is not a concern. The pattern is consistent across all three functions and is readable. However, the same classification logic is written three times using the same `ring_by_account.get(a)` / `ring_by_account.get(b)` pattern. If all three checks need to be updated — for example, if the same-ring classification logic changes — each function must be edited independently. A shared `classify_pair(a, b, ring_by_account) -> str` helper would consolidate this and prevent the three functions from drifting.

### `build_genie_expected` contains hardcoded account IDs

In `verify_fraud_patterns.py` at line 665, `build_genie_expected` returns a hardcoded list of ten account IDs as the expected Genie test-1 centrality result. This list was recorded from a specific live Genie run and baked into the source file. The function's docstring acknowledges this, noting that users should redirect output to a file and edit the list. But the hardcoded IDs will produce a false failure the first time anyone regenerates the dataset with a different `SEED` value. The function should either be removed (it is not called in the main code path), or replaced with a generation-time artifact stored alongside `ground_truth.json`.

### Unused import in `verify_fraud_patterns.py`

`from rich.console import Group` is imported twice in `verify_fraud_patterns.py` — once at the module level (implicitly, via the `rich` import), and once inline inside `render_report_rich` at line 454 and `render_comparison_report_rich` at line 592. The inline imports suggest the top-level `rich` imports were added at different times without consolidating. All `rich` imports should be at the top of the file.

### `compare_genie_runs.py` duplicates artifact-reading logic from `genie_run.py`

`compare_genie_runs.py` auto-discovers and reads the JSON artifacts written by `genie_run_before.py` and `genie_run_after.py`. The artifact format is defined in `genie_run.py`, but `compare_genie_runs.py` reads it with raw dict access and no shared schema definition. If the artifact format changes — for example, if a key is renamed — `compare_genie_runs.py` will fail silently with a missing key rather than raising a clear error. The artifact format should be read through a shared function or at minimum through explicit key validation.

---

## Implementation Plan

### Status summary

- [x] **Phase 1** — jobs/ bootstrap and consistency (complete)
- [x] **Phase 2** — verify_fraud_patterns.py split and cleanup (complete)
- [x] **Phase 3** — cross-module consolidation and long-method splits (complete)
- [x] **Phase 4** — artifact schema + remaining polish (complete, except optional items)

### Phase 1 — jobs/ bootstrap and consistency

- [x] Create `jobs/_cluster_bootstrap.py` with `inject_params()` and `resolve_here()` helpers
- [x] `neo4j_ingest.py`: replace 15-line inline boilerplate with `_cluster_bootstrap` import
- [x] `genie_run.py`: replace sections 1–2 with `_cluster_bootstrap` import
- [x] `pull_gold_tables.py`: replace sections 1–2 with `_cluster_bootstrap` import
- [x] `validate_gold_tables.py`: replace section 1–2 with `_cluster_bootstrap` import
- [x] `genie_run_before.py` / `genie_run_after.py`: replace inline inject loop with `inject_params()`
- [x] `demo_utils.py` — `check_community_purity`: standardise `passed` threshold to `>= 0.80` across all branches (fall-through used `>`)
- [x] `gold_constants.py`: add GDS verification thresholds (`PR_RATIO_MIN`, `COMMUNITY_PURITY_MIN`, `SIM_RATIO_MIN`, `RING_EXCLUSION_MAX`)
- [x] `validation/run_and_verify_gds.py`: import the four constants from `gold_constants.py` instead of defining them locally

### Phase 2 — verify_fraud_patterns.py split and cleanup

- [x] Extract `setup/checks_structural.py` (four core checks + `load_data` / `verify_ground_truth_matches`)
- [x] Extract `setup/checks_genie_csv.py` (six Genie output checks + CSV type detection + `run_genie_csv_check`)
- [x] Extract `setup/report.py` (rich renderers + snapshot comparison logic)
- [x] Reduce `verify_fraud_patterns.py` to an entry-point dispatcher that imports from the three new modules
- [x] Extract `_check_pagerank_dist`, `_check_louvain_dist`, `_check_nodesim_dist` from `check_gds_output`
- [x] Add shared `classify_pair(a, b, ring_by_account)` helper to consolidate pair classification across `checks_genie_csv.py`
- [x] Consolidate all `rich` imports to module level; remove inline `from rich.console import Group`
- [x] Remove `build_genie_expected` (not called in the main code path; hardcoded IDs produce false failures when `SEED` changes)

### Phase 3 — cross-module consolidation and long-method splits

Ring-lookup consolidation (review §"Ring-by-account lookup rebuilt in every check function") — **light-duplication approach**: each runtime scope (`setup/` vs `jobs/`) has its own helper, with distinct names to signal the different inputs:

- [x] `setup/checks_structural.py`: add `build_ring_index(rings: list[list[int]]) -> dict[int, int]`; `setup/checks_genie_csv.py` and `check_ring_density` import it
- [x] `setup/checks_genie_csv.py`: delete local `_build_ring_by_account`, update the four call sites
- [x] `jobs/demo_utils.py`: rename to `_ring_index_from_list(rings)` and `_ring_index_from_ground_truth(gt)` (distinct names make the two inputs obvious); `check_ring_pair_fraction` now uses `_ring_index_from_list`

`check_community_purity` refactor (review §"Long methods" and §"return shape is inconsistent"):

- [x] Extract `_coverage_from_groups`, `_coverage_from_community_map`, `_coverage_from_ring_candidate_flag`, `_coverage_from_pairs` from `jobs/demo_utils.py`
- [x] Add `_purity_result()` helper so every branch produces the same shape and threshold (`>= 0.80`)

`generate_account_links` branch helpers (review §"Long methods"):

- [x] Extract `_pick_within_ring_transfer`, `_pick_whale_inbound_transfer`, `_pick_whale_outbound_transfer`, `_pick_random_transfer` from `setup/generate_data.py`; loop body is now a four-way dispatch

### Phase 4 — artifact schema + remaining polish

`compare_genie_runs.py` shared schema (review §"compare_genie_runs.py duplicates artifact-reading logic"):

- [x] Add `jobs/genie_run_artifact.py` with `TypedDict` schema (`RunArtifact`, `Case`, `Attempt`, `Metric`, `Summary`) and `load_run_artifact(path)` that validates required keys and raises `ArtifactSchemaError`
- [x] Move shared read helpers (`case_by_name`, `metric_value`, `metric_key`, `last_attempt`) into the same module
- [x] `automated/compare_genie_runs.py` now calls `load_run_artifact` and imports the helpers; schema errors surface as `FAIL` messages instead of silent `KeyError`s

Optional (review flagged as low-risk; defer unless touched):

- [ ] `setup/report.py` — extract table-building helper from `render_comparison_report_rich` (review calls this "not a correctness or maintenance risk")
- [ ] `jobs/validate_gold_tables.py` `_run_checks` — leave as-is per review; revisit only if checks 4 or 6 grow further

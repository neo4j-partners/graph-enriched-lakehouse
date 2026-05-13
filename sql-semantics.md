# SQL Semantics Proposal

## Goal

Create a new standalone top-level sample project named `sql-semantics/` that
tests using dbxcarta from outside the dbxcarta repository.

The first implementation should copy and adapt the existing preset package from:

`/Users/ryanknight/projects/databricks/dbxcarta/examples/finance-genie`

The copied sample should live at:

`/Users/ryanknight/projects/databricks/graph-on-databricks/sql-semantics`

This project should prove that an external repository can package a dbxcarta
preset, install dbxcarta as a dependency, point at existing Finance Genie Unity
Catalog tables, and run the dbxcarta preset workflow without importing from the
`finance-genie/` source tree in this repository.

## Revised Direction

The previous plan described a larger sample with a new text-to-SQL CLI and
Neo4j-backed question memory. That is still useful, but it is too broad for the
first validation step.

The immediate plan is:

- Copy the dbxcarta Finance Genie preset example into a new root-level
  `sql-semantics/` directory.
- Rename the package so it belongs to this repository, for example
  `sql_semantics`.
- Keep the dbxcarta preset contract, readiness check, question upload helper,
  local read-only demo, `.env.sample`, README, and tests from the source
  example.
- Configure the package as an external dbxcarta consumer using a local editable
  dependency on `/Users/ryanknight/projects/databricks/dbxcarta` during
  development.
- Keep the project independent from the existing root-level `finance-genie/`
  source tree. Finance Genie remains only the data producer.

After this works, the project can grow into the larger text-to-SQL and memory
sample.

## Source Preset To Copy

Source directory:

`/Users/ryanknight/projects/databricks/dbxcarta/examples/finance-genie`

Important source files:

- `pyproject.toml`
- `.env.sample`
- `README.md`
- `src/dbxcarta_finance_genie_example/__init__.py`
- `src/dbxcarta_finance_genie_example/finance_genie.py`
- `src/dbxcarta_finance_genie_example/local_demo.py`
- `src/dbxcarta_finance_genie_example/upload_questions.py`
- `src/dbxcarta_finance_genie_example/questions.json`
- `tests/test_preset.py`
- `tests/test_local_demo.py`

Files and directories that should not be copied:

- `.env`
- `.venv/`
- `.pytest_cache/`
- `dist/`
- `__pycache__/`
- generated wheels or local build artifacts

## Target Project Shape

`sql-semantics/` should be a standalone Python package:

- `pyproject.toml`: standalone package metadata.
- `.env.sample`: local operator configuration for Databricks, dbxcarta, and
  Neo4j.
- `README.md`: setup guide for running this sample from the
  `graph-on-databricks` repository.
- `src/sql_semantics/__init__.py`: re-export the preset.
- `src/sql_semantics/finance_genie.py`: adapted dbxcarta `Preset`
  implementation.
- `src/sql_semantics/local_demo.py`: optional read-only local CLI copied from
  the dbxcarta example and renamed.
- `src/sql_semantics/upload_questions.py`: optional question upload helper, if
  still present in the source example.
- `src/sql_semantics/questions.json`: sample analyst questions.
- `tests/test_preset.py`: preset contract tests.
- `tests/test_local_demo.py`: local demo tests.
- `uv.lock`: generated only if needed for this standalone sample.

The package import path should be:

`sql_semantics:preset`

The package name in `pyproject.toml` should be:

`sql-semantics`

## Dependency Model

During local development, `sql-semantics/pyproject.toml` should depend on
dbxcarta through the sibling checkout:

```toml
[tool.uv.sources]
dbxcarta = { path = "/Users/ryanknight/projects/databricks/dbxcarta", editable = true }
```

The normal dependency should still be declared as a package dependency, for
example:

```toml
dependencies = [
    "dbxcarta>=0.2.32",
    "databricks-sdk>=0.40",
    "python-dotenv",
]
```

This keeps the sample honest as an outside consumer while still testing the
local dbxcarta checkout.

## Scope Boundary

Finance Genie owns:

- Data generation.
- Base Unity Catalog tables: `accounts`, `merchants`, `transactions`,
  `account_links`, `account_labels`.
- Optional Gold Unity Catalog tables: `gold_accounts`,
  `gold_account_similarity_pairs`, `gold_fraud_ring_communities`.
- Graph-enriched data pipeline and Genie demo assets.

`sql-semantics` owns:

- The copied and adapted dbxcarta preset.
- Readiness checks for the expected Finance Genie tables.
- Uploading the bundled question fixture to the configured UC Volume.
- Documentation for running dbxcarta from this external sample.
- A small local read-only CLI demo, if retained from the source preset.

`sql-semantics` should not:

- Import modules from root-level `finance-genie/`.
- Call Finance Genie setup code.
- Mutate Finance Genie project files.
- Depend on being inside the dbxcarta repository.

## Preset Defaults

Keep the source example defaults unless testing shows they must change:

- Catalog: `graph-enriched-lakehouse`
- Schema: `graph-enriched-schema`
- Volume: `graph-enriched-volume`
- Required tables:
  - `accounts`
  - `merchants`
  - `transactions`
  - `account_links`
  - `account_labels`
- Optional tables:
  - `gold_accounts`
  - `gold_account_similarity_pairs`
  - `gold_fraud_ring_communities`
- Embedding endpoint: `databricks-gte-large-en`
- Embedding dimension: `1024`
- Client arms: `no_context,schema_dump,graph_rag`
- Semantic inference: enabled
- Criteria injection: disabled

Gold tables should stay optional by default. Strict readiness can require them
when the operator passes the dbxcarta strict optional flag.

## Expected Workflow

Run commands from `sql-semantics/` unless otherwise noted.

1. Install the external sample:

```bash
uv sync
```

2. Print the dbxcarta overlay:

```bash
uv run dbxcarta preset sql_semantics:preset --print-env
```

3. Check table readiness:

```bash
uv run dbxcarta preset sql_semantics:preset --check-ready
```

4. Upload bundled questions:

```bash
uv run dbxcarta preset sql_semantics:preset --upload-questions
```

5. Build and verify the semantic layer with dbxcarta:

```bash
uv run dbxcarta upload --wheel
uv run dbxcarta upload --all
uv run dbxcarta submit-entrypoint ingest
uv run dbxcarta verify
```

6. Optionally run the local demo:

```bash
uv run python -m sql_semantics.local_demo preflight
uv run python -m sql_semantics.local_demo questions
uv run python -m sql_semantics.local_demo ask --question-id fg_q01 --show-context
```

## Phase Checklist

### Phase 1: Copy External Preset Sample

Status: Complete

Checklist:

- Complete: Create root-level `sql-semantics/`.
- Complete: Copy the dbxcarta `examples/finance-genie` sample into
  `sql-semantics/`.
- Complete: Exclude local artifacts: `.env`, `.venv/`, `.pytest_cache/`, `dist/`,
  `__pycache__/`, and generated wheels.
- Complete: Rename package imports from `dbxcarta_finance_genie_example` to
  `sql_semantics`.
- Complete: Rename the exported preset import path to `sql_semantics:preset`.
- Complete: Update `pyproject.toml` package metadata to `sql-semantics`.
- Complete: Configure the local editable dbxcarta dependency to the absolute
  dbxcarta checkout path.

Validation:

- Complete: `uv sync` succeeds from `sql-semantics/`.
- Complete: `uv run python -c "from sql_semantics import preset; print(preset.env())"`
  succeeds.
- Complete: `uv run pytest` passes non-live tests.

### Phase 2: Adapt README And Environment

Status: Complete

Checklist:

- Complete: Rewrite `sql-semantics/README.md` for this repository.
- Complete: Explain that Finance Genie data must already exist in Unity Catalog.
- Complete: Document that dbxcarta is consumed from the sibling checkout during local
  development.
- Complete: Update commands to use `sql_semantics:preset`.
- Complete: Update `.env.sample` comments so they refer to `sql-semantics/`, not
  `examples/finance-genie/`.

Validation:

- Complete: README commands match the actual package path.
- Complete: `.env.sample` has no stale source-example paths.

### Phase 3: Preset Verification

Status: Complete for local verification; live readiness blocked

Checklist:

- Complete: Run preset unit tests.
- Complete: Confirm the preset satisfies dbxcarta `Preset`, `ReadinessCheckable`, and
  `QuestionsUploadable` protocols.
- Complete: Confirm readiness reports required and optional Finance Genie tables
  correctly.
- Complete: Confirm question fixture validation and upload path validation still work.

Validation:

- Complete: Non-live tests pass: `21 passed`.
- Complete: `--print-env` emits the expected Finance Genie dbxcarta overlay.
- Complete: `--check-ready --strict-optional` passes against
  `graph-enriched-lakehouse.graph-enriched-schema`.

### Phase 4: External-Consumer Smoke Test

Status: Blocked on external wheel upload behavior

Checklist:

- Complete: Run the dbxcarta preset CLI from inside `sql-semantics/` for
  `--print-env`.
- Complete: Confirm dbxcarta resolves from
  `/Users/ryanknight/projects/databricks/dbxcarta`.
- Complete: Upload questions to the configured UC Volume.
- Blocked: `uv run dbxcarta upload --wheel` builds the external
  `sql-semantics` wheel, then the dbxcarta runner looks for
  `dist/dbxcarta-*.whl`; the resulting artifact is
  `dist/sql_semantics-*.whl`.
- Blocked: Ingest and verify depend on resolving the wheel-upload behavior.

Validation:

- Complete: The sample runs without importing from dbxcarta
  `examples/finance-genie`.
- Complete: The sample runs without importing from this repository's
  `finance-genie/`.
- Complete: dbxcarta sees `sql_semantics:preset` as a normal external preset
  package.
- Complete: Live readiness and question upload pass with the configured
  `sql-semantics/.env`.
- Blocked: Ingest and verify need a dbxcarta wheel upload path that works from
  the external `sql-semantics` package.

### Phase 5: Deferred Text-To-SQL And Memory

Status: Deferred

Checklist:

- Revisit the original text-to-SQL CLI requirements after the external preset
  smoke test is working.
- Decide whether to extend the copied `local_demo.py` or create separate
  modules for prompt assembly, SQL validation, and memory.
- Decide whether Neo4j memory should share the dbxcarta database or use a
  separate database.
- Decide the default user identity model for remembered questions.

Validation:

- Deferred until the copied preset sample is working end to end.

## Risks

- The copied source example may rely on private dbxcarta client helpers in
  `local_demo.py`. That is acceptable for the first external-consumer test, but
  should be revisited before making this a durable public sample.
- Absolute local dependency paths are correct for this workspace but should be
  documented as local development wiring.
- The sample can pass unit tests without proving live Databricks, Neo4j, or
  UC Volume access. Live smoke tests remain a separate validation step.
- Finance Genie table names and default UC scope may drift. The readiness check
  should make missing tables obvious.

## Completion Criteria

The first delivery is complete when:

- `sql-semantics/` exists as a standalone sample package.
- The package exposes `sql_semantics:preset`.
- The package uses dbxcarta as an external dependency from the sibling checkout.
- Non-live tests pass from `sql-semantics/`.
- The README documents the external-consumer workflow.
- The sample has no import dependency on root-level `finance-genie/` or
  dbxcarta's `examples/finance-genie`.

## Open Questions

- Resolved: Keep `local_demo.py` for parity with the source preset example.
- Resolved: `sql-semantics/.env` now has the required live runner fields.
  Remaining live smoke-test work is blocked by the dbxcarta wheel-upload
  behavior from an external package.
- Resolved: The dbxcarta dependency floor is `>=0.2.35`, matching the sibling
  checkout version used by `uv sync`.

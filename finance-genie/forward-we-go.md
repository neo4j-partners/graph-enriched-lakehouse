# Forward We Go: preflight-only adoption of databricks-job-runner 0.5.1

TLDR. enrichment-pipeline is a simple demo, seldom deployed. The recommended
change is small: bump to 0.5.1 and add a fail-fast preflight that checks the
cluster has the Neo4j Spark connector (Maven) and the `graphdatascience` /
`neo4j` Python packages (PyPI) before a job is submitted. No packaging, no
restructuring, the existing loose-script model is untouched. The larger
bootstrap-from-Volume migration ("Mode 3") is explicitly not being done; the
reason is recorded at the bottom.

## What this buys us (ELI5)

Before a job runs, the runner asks the cluster "do you have the stuff this job
needs?" If not, it stops in about two seconds with a clear message instead of
failing eight minutes into the run. The "stuff" is two kinds of library that
are currently installed on the cluster by hand and mentioned only in code
comments:

- Maven: the Neo4j Spark connector
  (`org.neo4j:neo4j-connector-apache-spark...`), the Java/Scala plugin that
  lets Spark read and write Neo4j.
- PyPI: `graphdatascience` and `neo4j`, the Python packages the job code
  imports.

The preflight only checks; it does not install. For a demo that is rebuilt
rarely, a clear fail-fast at submit time is enough, and manual install stays
manual.

## How it works in 0.5.1 (verified against the library source)

- `Runner(preflights=[...])` runs an ordered, fail-fast hook list inside both
  `Runner.submit` and `Runner.validate`, before any run is created.
- A preflight is `Callable[[WorkspaceClient, str | None, Compute],
  PreflightResult]`. The second arg is the cluster id, or `None` on
  serverless (enrichment-pipeline is classic-cluster, so it is always set).
- `maven_libraries_preflight([DesiredLibrary.maven("<coord>")])` is shipped
  ready to use for the connector.
- There is no shipped PyPI convenience preflight, but the mechanism exists:
  `check_cluster_libraries(ws, cluster_id, [DesiredLibrary.pypi("..."),
  ...])` returns a plan with `.missing` / `.pending` / `.failed`, and
  `format_cluster_library_plan(plan)` renders it. A ~15-line custom preflight
  wraps that exactly like `maven_libraries_preflight` does, returning
  `PreflightResult(ok=..., messages=...)`.

## The change

Status: not started

- 1. Bump `enrichment-pipeline/pyproject.toml`:
  `databricks-job-runner>=0.5.1`. Run `uv lock && uv sync` (the venv is
  currently on a stale 0.4.3, below even today's pin).
- 2. In `cli/__init__.py`, add the preflights to the existing `Runner` (no
  other change to the loose-script setup):
  - `maven_libraries_preflight([DesiredLibrary.maven("<exact connector
    coordinate, see Decision D1>")])`
  - a small custom `pypi_libraries_preflight([DesiredLibrary.pypi(
    "graphdatascience"), DesiredLibrary.pypi("neo4j")])` built on
    `check_cluster_libraries` + `format_cluster_library_plan`, modeled on the
    shipped Maven one (assert-only, never installs).
  - `Runner(..., preflights=[maven_preflight, pypi_preflight])`
- 3. Keep everything else as is: `scripts_dir="jobs"`, `extra_files=
  ["sql/gold_schema.sql"]`, all 14 loose job scripts, the
  `_cluster_bootstrap.py` shim, the `submit` / `upload` / `logs` flow.
- 4. Optionally retire `validation/validate_cluster.py`, since the preflight
  now does the same connector check automatically at submit and validate
  time. Recommendation: keep it for now as a standalone manual check; remove
  later if redundant.

## Decision to confirm before step 2

- D1. Exact Neo4j connector Maven coordinate. The job docstrings and
  `validation/validate_cluster.py` match the prefix
  `org.neo4j:neo4j-connector-apache-spark` and the docstrings name
  `org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3`. Confirm
  the exact Scala/connector version installed on cluster
  `1029-205109-yca7gn2n` so the assertion does not false-fail. If an exact
  version match is too brittle across cluster rebuilds, use
  `DesiredLibrary.maven(..., exact=False)` so it matches on coordinate, not
  version.

## Validation

Status: not started

- V1. With the connector and PyPI libs present on the cluster:
  `python -m cli validate` prints `[ok]` for both preflights, then proceeds
  as before.
- V2. Detach the connector (or one PyPI lib) on the cluster: `python -m cli
  validate` and `python -m cli submit 02_neo4j_ingest.py` both fail fast with
  a named missing-library message and create no run.
- V3. Reattach: a normal `submit 02_neo4j_ingest.py` and
  `submit 03_pull_gold_tables.py` run end to end unchanged.
- V4. A non-connector job (`01_genie_run_before.py`) still submits and runs.
  The preflight asserting connector presence is acceptable here because every
  job in this pipeline runs on the same connector-equipped cluster.

## Rollback

Revert the two lines in `cli/__init__.py` and the version pin. Nothing else
changed, no workspace or Volume state to clean up.

## Why we are not doing the Mode 3 bootstrap migration

Mode 3 (build a wheel, publish it to a stable Volume path, a bootstrap script
installs the wheel plus a pinned dependency closure into a fresh per-run
target on every run) is the 0.5.1 "recommended" model, but it is recommended
for wheel-task projects with frequent or concurrent runs. enrichment-pipeline
is neither:

- It is a demo, seldom deployed. The Mode 3 payoffs (no cluster restart on
  code change, no version bump, per-run isolation, auto-installed deps every
  run) solve pains of frequently-rebuilt or concurrent pipelines. This
  pipeline runs sequentially and rarely, so those pains do not occur.
- The single real benefit for these jobs (fail fast when a prerequisite is
  missing) is fully available without Mode 3, because the preflight hooks run
  on the existing loose-script `submit` path. That is this plan.
- Mode 3 would force a real refactor: a wheel package, a `src/` layout, one
  console entry point with a `JOB=` dispatcher replacing 14 clearly named
  scripts, an exact `pinned_closure` that must be kept correct or runs fail at
  startup, and untangling `_gold_constants` which is shared across the
  connector and non-connector jobs. That cost is not repaid for a demo.

Revisit Mode 3 only if this pipeline later becomes frequently rebuilt, runs
concurrently against a shared cluster, or needs reproducible per-run code
isolation. Until then, preflight-only is the right scope.

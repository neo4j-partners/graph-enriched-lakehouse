# Forward We Go: migrate finance-genie to databricks-job-runner 0.5.1

Goal: move finance-genie off the loose-script `PythonWheelTask`-style upload model
and onto the 0.5.1 bootstrap-from-Volume `SparkPythonTask` model
(`publish_wheel_stable` + `submit_bootstrap` + `maven_libraries_preflight`).
No backward-compatibility shims. The end state is a real wheel package per
subproject, a stable Volume wheel path, per-run isolation, and a fail-fast
preflight on the Neo4j Spark connector.

## What the new model requires (facts, verified against v0.5.1 source)

The bootstrap path is fundamentally different from loose-script upload. It
forces five structural changes:

1. The subproject must be a real installable wheel. `package = false` and the
   missing `[build-system]` block must go. Distribution name becomes the
   `wheel_package` passed to `Runner`.
2. There is exactly one console entry point per submit. `bootstrap.py` resolves
   a single `console_scripts` entry by name from the just-installed wheel and
   calls `entry()`. The current 14 loose job scripts cannot each be a separate
   `SparkPythonTask` anymore. They collapse into one console entry point that
   dispatches on a project param (for example `JOB=02_neo4j_ingest`).
3. The bootstrap never calls `inject_params`. The docstring is explicit: "the
   entry point owns its own parameter and secret-scope injection." The
   `KEY=VALUE` argv tail still arrives (`submit_bootstrap_job` forwards
   `project_params` after the JSON blob), so the `inject_params` logic from
   `_cluster_bootstrap.py` / `_job_bootstrap.py` must move *into* the package
   and run at the top of the console entry point.
4. The project wheel installs `--no-deps` into a fresh per-run target. Every
   runtime dependency the jobs import (`graphdatascience`, `neo4j`, `pandas`,
   `rich`, `databricks-sdk`, etc.) must be enumerated as the
   `BootstrapConfig.pinned_closure`, which is installed `--no-deps` into the
   shared driver env under an `fcntl` lock. A missing transitive dep will fail
   at run startup, not at submit.
5. Maven JVM libraries are not installed by the bootstrap. The Neo4j Spark
   connector stays a cluster-level Maven library and is asserted by
   `maven_libraries_preflight([...])` wired into `Runner(preflights=[...])`.
   `jvm_probe_class` in `BootstrapConfig` makes the bootstrap probe the Spark
   classpath for the connector class before invoking the entry point.

Relevant 0.5.1 API surface:

- `Runner(wheel_package=..., preflights=[...], remote_scripts_dir=...)`
- `Runner.publish_wheel_stable() -> str` (builds wheel, uploads to fixed
  Volume path `<volume>/wheels/<pkg>-stable.whl`, no version bump, returns
  dest). Library-only, no CLI subcommand.
- `Runner.submit_bootstrap(BootstrapConfig, *, run_name_suffix=..., no_wait=...,
  compute_mode=...)`. Library-only, no CLI subcommand.
- `Runner.upload_all()` now also uploads the packaged bootstrap as
  `_dbxrunner_bootstrap.py` via `upload_bootstrap_script` (automatic).
- `BootstrapConfig(wheel_volume_path, pinned_closure, wheel_package,
  console_script, jvm_probe_class=None, per_run_root=None, smoke_imports=[],
  ...)`.
- `from databricks_job_runner.preflight import maven_libraries_preflight`
- `from databricks_job_runner.libraries import DesiredLibrary` ->
  `DesiredLibrary.maven("org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3")`

## Decisions to confirm before Phase 1

These change the shape of the work. Confirm each before starting.

- D1. Scope. enrichment-pipeline is the real target: classic cluster + Neo4j
  Spark connector, where the bootstrap model pays off (no cluster restart on
  code change, per-run isolation, JVM preflight). neo4j-mcp-demo runs
  serverless, has no Neo4j Spark connector, and uses
  `DependencyServerless` with pinned pip deps; the bootstrap model gives it
  little. Recommendation: full migration for enrichment-pipeline; for
  neo4j-mcp-demo only bump the pin and adopt `preflights` if useful, do not
  force the bootstrap model. Confirm whether neo4j-mcp-demo is in or out.
- D2. Job dispatch shape. 14 loose scripts become one console entry point that
  dispatches on a `JOB` param. Confirm the param name and that a single
  per-job submit (one `submit_bootstrap` call per job, `JOB=` selects which)
  is acceptable versus any expectation of parallel multi-task runs.
- D3. pinned_closure source of truth. Recommendation: generate it from the
  resolved lockfile (`uv export --no-hashes --no-dev`) filtered to runtime
  deps, checked into the repo as `pinned_closure.txt` and read by the CLI.
  Confirm this over hand-maintaining the list.
- D4. Package name / layout. Recommendation: rename the distribution to
  `finance_genie_enrichment` with a `src/finance_genie_enrichment/` layout so
  `wheel_package` is unambiguous and importable. Confirm the name.
- D5. Transition policy. Recommendation: stand the bootstrap path up for the
  two connector jobs (`02_neo4j_ingest`, `03_pull_gold_tables`) first, validate
  end to end, then migrate the remaining Genie/test jobs. Confirm phased
  cutover versus a single big-bang switch.

## Phase 1: package the enrichment-pipeline as a wheel

Status: not started

- 1.1 Add a `[build-system]` to `enrichment-pipeline/pyproject.toml`
  (`uv_build`), remove `package = false`, set distribution name per D4, add
  `[project.scripts]` with one console entry point, for example
  `finance-genie-job = "finance_genie_enrichment.run:main"`.
- 1.2 Create `src/finance_genie_enrichment/` and move the `jobs/` modules into
  it as importable modules. Helper modules (`_demo_utils`, `_gold_table_checks`,
  `_gold_constants`, `_genie_run_artifact`, `_neo4j_secrets`) become package
  modules with normal absolute imports. Delete the `sys.path.insert` /
  `resolve_here()` preamble from every job module.
- 1.3 Move `inject_params` (the `KEY=VALUE` argv parser) into the package as a
  function called once at the top of `main()`. Delete
  `jobs/_cluster_bootstrap.py`.
- 1.4 `sql/gold_schema.sql` becomes package data. Either ship it inside the
  package and load it with `importlib.resources`, or keep it as an
  `extra_files` workspace upload. Recommendation: package data via
  `importlib.resources` so the wheel is self-contained; update
  `03_pull_gold_tables` to read it that way.
- 1.5 Build locally (`uv build --wheel`) and confirm the wheel installs and
  the console entry point resolves (`pip install dist/*.whl` in a scratch
  venv, run the entry point with `JOB=...` and dummy params).

## Phase 2: write the job-dispatch entry point

Status: not started

- 2.1 `finance_genie_enrichment/run.py:main()` parses argv: first run
  `inject_params()` to load `KEY=VALUE` into `os.environ`, then read `JOB`
  from env, then dispatch to the corresponding job function.
- 2.2 Each former script (`01_genie_run_before` ... `cat5_merchant`,
  `test_*`) becomes a function or module with a `run()` callable. The `JOB`
  value maps to it via an explicit dict, no dynamic import by filename.
- 2.3 Secret-scope reads (`_neo4j_secrets.load_neo4j_opts`,
  `ws.dbutils.secrets`) are unchanged in behavior; they now run inside the
  installed package instead of a path-injected sibling.
- 2.4 Unknown `JOB` value raises a clear error listing valid jobs.

## Phase 3: wire the new Runner and CLI commands

Status: not started

- 3.1 `cli/__init__.py`: construct `Runner` with `wheel_package` set and
  `preflights=[maven_libraries_preflight([DesiredLibrary.maven(
  "org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3")])]`.
  Confirm the exact Maven coordinate against the cluster
  (`validation/validate_cluster.py` currently matches the prefix
  `org.neo4j:neo4j-connector-apache-spark`).
- 3.2 `publish_wheel_stable` and `submit_bootstrap` have no built-in CLI
  subcommand. Add project CLI commands that wrap them, for example
  `python -m cli publish` and `python -m cli run <JOB>`, where `run` builds
  the `BootstrapConfig` and calls `submit_bootstrap` with
  `project_params` carrying `JOB=<job>` plus the `.env` params the runner
  already forwards. Keep `upload --all` (it now also uploads
  `_dbxrunner_bootstrap.py`).
- 3.3 Build `BootstrapConfig`:
  - `wheel_volume_path` = the dest returned by `publish_wheel_stable()`
  - `pinned_closure` from D3
  - `wheel_package` = D4 name
  - `console_script` = the `[project.scripts]` name from 1.1
  - `jvm_probe_class` = the Neo4j connector DataSource class (confirm exact
    class name on the connector jar; the write format string is
    `org.neo4j.spark.DataSource`)
  - `smoke_imports` = a few critical modules (for example `graphdatascience`,
    `pyspark.sql`) for the post-install shared-env check
- 3.4 Decide and document the new operator flow in
  `enrichment-pipeline/README.md` and `worklog/organize.md`:
  `uv run python -m cli publish` then
  `uv run python -m cli upload --all` then
  `uv run python -m cli run 02_neo4j_ingest` then
  `uv run python -m cli logs`.

## Phase 4: pinned_closure and dependency correctness

Status: not started

- 4.1 Generate the pinned closure from the lockfile (D3). The wheel installs
  `--no-deps`, so the closure must contain every runtime import transitively:
  `graphdatascience`, `neo4j`, `pandas`, `rich`, `python-dotenv`,
  `databricks-sdk`, plus their transitive deps. `pyspark` is provided by the
  cluster and must be excluded.
- 4.2 Add a check that the closure resolves: in a clean container or venv,
  `pip install --no-deps -r pinned_closure.txt` then import `smoke_imports`.
- 4.3 Confirm nothing in the closure conflicts with the Databricks runtime
  preinstalled packages on the target cluster (DBR version of cluster
  `1029-205109-yca7gn2n`). Pin versions that are known-good there.

## Phase 5: end-to-end validation on the connector jobs

Status: not started

- 5.1 Bump `enrichment-pipeline/pyproject.toml` pin to
  `databricks-job-runner>=0.5.1` and `uv lock && uv sync`.
- 5.2 Run the connector preflight in isolation: `python -m cli validate` with
  the cluster connector deliberately detached should fail fast with a named
  missing-library message; reattached should pass.
- 5.3 Full run of `02_neo4j_ingest` via the bootstrap path. Confirm in the
  driver log: one `BOOTSTRAP_MANIFEST` line, the wheel sha, the per-run
  target, smoke-check ok, the JVM probe passing, and the job's own success
  output.
- 5.4 Full run of `03_pull_gold_tables` (writes gold Delta tables, reads
  `gold_schema.sql` as package data). Confirm gold tables and column comments.
- 5.5 Overlapping-run check: submit two runs close together, confirm per-run
  isolation (distinct run tokens, distinct per-run targets) and the closure
  lock serializes without deadlock.

## Phase 6: migrate the remaining jobs and clean up

Status: not started

- 6.1 Migrate the Genie and test jobs (`01_genie_run_before`,
  `05_genie_run_after`, `cat1..5`, `test_*`) into the dispatch map. These have
  no JVM dependency; the preflight skips cleanly for any non-connector run if
  desired, or the connector preflight stays global since all runs use the same
  cluster.
- 6.2 Delete the now-dead loose-script machinery: the old per-script bootstrap
  preamble, `_cluster_bootstrap.py` (already removed in 1.3), and any
  `extra_files` no longer needed once SQL is package data.
- 6.3 Update all docs (`README.md`, `worklog/organize.md`, job docstrings) to
  the `publish` + `upload --all` + `run <JOB>` flow. Remove the old
  `submit <script>` instructions.
- 6.4 Decide neo4j-mcp-demo per D1. If out of scope: bump its pin to
  `>=0.5.1`, `uv lock && uv sync`, leave the serverless model as is. If in
  scope: a separate mini-plan (it has no Maven connector and runs serverless,
  so `pinned_closure` replaces `REMOTE_PIP_DEPENDENCIES` and the JVM probe is
  unused).

## Risks and rollback

- The single-entry-point dispatch is the largest change and touches every job
  module. Phase 5 validates on two jobs before Phase 6 touches the rest, so a
  failure is contained.
- `--no-deps` closure errors surface at run startup, not submit. Phase 4.2
  catches these locally before any cluster run.
- Rollback: the loose-script `submit` path in 0.5.1 is unchanged and still
  works. Until Phase 6.2 deletes the old machinery, reverting `cli/__init__.py`
  and the pin restores the previous flow with no Volume or workspace cleanup
  required.
- The exact Neo4j connector Maven coordinate and the JVM probe class name must
  be confirmed against the live cluster (3.1, 3.3) or the preflight will either
  false-fail or false-pass.

## Open questions for the user

- D1 through D5 above.
- Whether `forward-we-go.md` tracks status inline (Status lines per phase) or
  whether a separate task list is preferred.

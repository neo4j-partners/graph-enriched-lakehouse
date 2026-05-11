"""Neo4j ingest CLI — wires Runner to the accelerator project layout."""

from databricks_job_runner import Runner

runner = Runner(
    run_name_prefix="neo4j_ingest",
    scripts_dir="jobs",
    extra_files=["sql/gold_schema.sql"],
)

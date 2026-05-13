# SQL Semantics Proposal

## Goal

Create a new standalone sample project named `sql-semantics` that demonstrates a dbxcarta-powered semantic layer for the Finance Genie Lakehouse data.

The sample should live in a new root-level directory, `sql-semantics/`, and should not depend on the `finance-genie/` source tree. Finance Genie remains the upstream data producer. The `sql-semantics` sample only assumes the user has already run the Finance Genie setup path that creates the required Unity Catalog tables.

The sample should use `/Users/ryanknight/projects/databricks/dbxcarta` as the local dbxcarta source during development and should show how to:

- Package a dbxcarta preset for the existing Finance Genie tables.
- Build a Neo4j semantic layer over those Unity Catalog tables with dbxcarta.
- Run a simple read-only text-to-SQL flow using dbxcarta graph retrieval.
- Remember each user's prior questions in Neo4j agent memory and use relevant prior questions as prompt context for future SQL generation.

## Proposed Project Shape

`sql-semantics/` should be a separate Python package and operator workflow:

- `pyproject.toml`: standalone package metadata, with a local editable dependency on `/Users/ryanknight/projects/databricks/dbxcarta` for development.
- `.env.sample`: Databricks, dbxcarta, Neo4j, model endpoint, catalog, schema, and volume settings.
- `README.md`: setup guide, prerequisite data setup note, semantic-layer build flow, text-to-SQL demo flow, and troubleshooting.
- `src/sql_semantics/preset.py`: dbxcarta `Preset` implementation for the Finance Genie table contract.
- `src/sql_semantics/questions.json`: sample analyst questions and optional reference SQL.
- `src/sql_semantics/cli.py`: local CLI for readiness checks, semantic-layer commands, text-to-SQL asks, and memory inspection.
- `src/sql_semantics/memory.py`: Neo4j-backed question memory.
- `src/sql_semantics/text_to_sql.py`: graph retrieval, prompt assembly, SQL generation, read-only validation, and execution.
- `tests/`: focused tests for preset readiness, read-only SQL validation, memory Cypher construction, and prompt assembly.

## Scope Boundary

Finance Genie owns:

- Data generation.
- Base Unity Catalog tables: `accounts`, `merchants`, `transactions`, `account_links`, `account_labels`.
- Optional Gold Unity Catalog tables: `gold_accounts`, `gold_account_similarity_pairs`, `gold_fraud_ring_communities`.
- The graph-enriched data pipeline and Genie demo assets.

`sql-semantics` owns:

- A dbxcarta preset that points at the existing Finance Genie Unity Catalog scope.
- Readiness checks that tell the user whether the Finance Genie data exists.
- dbxcarta semantic-layer setup instructions and wrapper commands.
- A simple graph-retrieval text-to-SQL experience.
- Neo4j agent memory for user questions, generated SQL, retrieved schema context, and execution outcomes.

The sample should not import `finance-genie` modules, call Finance Genie setup code, or mutate Finance Genie project files.

## Assumptions

- The default Unity Catalog scope is `graph-enriched-lakehouse.graph-enriched-schema`, matching the validated dbxcarta Finance Genie example.
- The default UC Volume is `graph-enriched-volume`, used for dbxcarta run summaries and uploaded question fixtures.
- The user can override catalog, schema, and volume through environment variables.
- The user has Databricks auth configured locally.
- The user has access to a Databricks SQL warehouse and model serving endpoints for embeddings and chat.
- Neo4j can hold both dbxcarta semantic-layer nodes and `sql-semantics` memory nodes in the same database, provided memory labels and relationship types are namespaced.
- All generated SQL is read-only. The demo should reject mutating SQL before execution.

## Semantic Layer Design

The preset should mirror the dbxcarta Finance Genie example but use a new package identity, such as `sql_semantics:preset`.

Required tables:

- `accounts`
- `merchants`
- `transactions`
- `account_links`
- `account_labels`

Optional tables:

- `gold_accounts`
- `gold_account_similarity_pairs`
- `gold_fraud_ring_communities`

The preset should:

- Return a dbxcarta environment overlay for catalog, schema, volume, summary path, summary table, embedding settings, sample-value settings, semantic FK inference, and client question path.
- Check table readiness through Unity Catalog `information_schema`.
- Upload the sample question fixture to the configured UC Volume.
- Keep Gold tables optional by default so users can demonstrate semantic retrieval over the base dataset first.
- Support a strict mode where missing Gold tables fail readiness.

## Text-To-SQL Design

The first implementation should be a local CLI rather than a UI. This keeps the example easy to run, test, and understand.

The `ask` flow should:

- Accept either an ad hoc question or a question id from `questions.json`.
- Embed the user question with the configured Databricks embedding endpoint.
- Retrieve schema context from dbxcarta's Neo4j semantic layer.
- Retrieve similar prior questions from Neo4j agent memory for the same user or workspace.
- Assemble a prompt containing the current question, dbxcarta schema context, relevant prior question examples, and read-only SQL rules.
- Generate SQL through the configured Databricks chat endpoint.
- Parse and validate that the SQL is a single read-only statement.
- Execute the SQL on the configured Databricks SQL warehouse.
- Store the question, generated SQL, retrieved schema ids, result metadata, and success or failure state in Neo4j memory.

The CLI should also include:

- `preflight`: checks environment, warehouse connectivity, dbxcarta graph presence, and memory graph constraints.
- `questions`: lists bundled sample questions.
- `ask`: runs graph-retrieval text-to-SQL and records memory.
- `memory list`: shows recent questions for a user.
- `memory similar`: shows remembered questions similar to a new question.
- `sql`: executes a manually supplied read-only SQL statement for debugging.

## Neo4j Agent Memory Design

Memory should be stored as first-class Neo4j graph data with labels that do not collide with dbxcarta labels.

Proposed labels:

- `SqlSemanticsUser`
- `SqlSemanticsSession`
- `SqlSemanticsQuestion`
- `SqlSemanticsGeneratedSql`
- `SqlSemanticsRun`

Proposed relationships:

- `(:SqlSemanticsUser)-[:ASKED]->(:SqlSemanticsQuestion)`
- `(:SqlSemanticsSession)-[:CONTAINS]->(:SqlSemanticsQuestion)`
- `(:SqlSemanticsQuestion)-[:GENERATED]->(:SqlSemanticsGeneratedSql)`
- `(:SqlSemanticsQuestion)-[:USED_SCHEMA]->(:Column|Table)`
- `(:SqlSemanticsQuestion)-[:SIMILAR_TO]->(:SqlSemanticsQuestion)`
- `(:SqlSemanticsRun)-[:FOR_QUESTION]->(:SqlSemanticsQuestion)`

The memory write path should store:

- User id or a stable local alias.
- Session id.
- Raw question text.
- Question embedding, if the configured Neo4j version and memory policy allow vector search over memory.
- Generated SQL.
- Read-only validation result.
- Execution status.
- Row count and column names, but not full result sets by default.
- dbxcarta seed ids and retrieved table or column ids.
- Timestamp and model endpoint metadata.

The memory read path should prefer successful prior questions from the same user, then successful prior questions from the same project. Retrieved examples should be short and bounded so they improve SQL generation without overwhelming the prompt.

## Phase Checklist

### Phase 1: Proposal and Sample Contract

Status: In progress

Checklist:

- Complete: Create this proposal.
- Pending: Confirm scope with the user.
- Pending: Confirm the target default Unity Catalog catalog, schema, and volume.
- Pending: Confirm whether Gold tables are optional or required for the first demo.
- Pending: Confirm whether memory can share the existing dbxcarta Neo4j database.
- Pending: Confirm the desired user identity model for memory.

Validation:

- Proposal reviewed and questions resolved or accepted as defaults.

### Phase 2: Project Scaffold

Status: Pending

Checklist:

- Add `sql-semantics/` as a standalone Python package.
- Add `.env.sample`, README, package metadata, and test skeleton.
- Configure dbxcarta as a local editable dependency for development.
- Keep the package independent from the `finance-genie/` source tree.

Validation:

- Local dependency resolution succeeds.
- Package imports without requiring live Databricks or Neo4j connections.

### Phase 3: dbxcarta Preset

Status: Pending

Checklist:

- Implement the `sql_semantics:preset` object.
- Add readiness checks for required and optional Finance Genie tables.
- Add question fixture upload support.
- Add tests for env overlay, identifier validation, table readiness formatting, and question fixture validation.

Validation:

- Preset prints a complete dbxcarta env overlay.
- Readiness reports missing Finance Genie data clearly.
- Readiness passes after the user has created the Finance Genie tables.

### Phase 4: Semantic Layer Build Flow

Status: Pending

Checklist:

- Document the prerequisite Finance Genie data setup step.
- Document dbxcarta secret setup, artifact upload, ingest submission, and verification.
- Add wrapper CLI commands only where they reduce operator friction without hiding dbxcarta behavior.
- Keep destructive Neo4j cleanup out of the normal flow.

Validation:

- dbxcarta ingest completes against the configured UC scope.
- dbxcarta verification reports zero structural violations.
- The semantic graph contains expected `Database`, `Schema`, `Table`, `Column`, `Value`, and `REFERENCES` data for the Finance Genie tables.

### Phase 5: Text-To-SQL CLI

Status: Pending

Checklist:

- Implement `questions`, `preflight`, `sql`, and `ask` commands.
- Use dbxcarta graph retrieval for schema context.
- Generate SQL through the configured Databricks chat endpoint.
- Enforce single-statement read-only SQL before execution.
- Print generated SQL, retrieved context ids, and result rows.
- Add tests for prompt construction and SQL safety checks.

Validation:

- At least three bundled questions generate read-only SQL.
- Generated SQL executes successfully against the warehouse.
- CLI reports useful errors for missing config, missing semantic graph, invalid SQL, or warehouse failures.

### Phase 6: Neo4j Agent Memory

Status: Pending

Checklist:

- Create memory constraints and indexes.
- Store each question, generated SQL, retrieved schema context, and execution outcome.
- Retrieve relevant successful prior questions and include them in prompt context.
- Add memory inspection commands.
- Add tests for memory payload shape and query construction.

Validation:

- A repeated or related question retrieves prior memory.
- Prompt context includes bounded prior examples.
- Memory writes do not modify or delete dbxcarta semantic-layer nodes.

### Phase 7: Documentation and Demo Path

Status: Pending

Checklist:

- Write an end-to-end README path from prerequisite data setup through asking a question.
- Include troubleshooting for Databricks auth, missing UC tables, missing Neo4j credentials, missing vector indexes, and model endpoint failures.
- Add a short demo script that shows first question, remembered follow-up, and memory inspection.

Validation:

- A fresh user can follow the README after setting up Finance Genie data.
- The demo shows semantic retrieval and remembered question context in a single short flow.

## Risks

- dbxcarta currently treats preset packages as external examples. The `sql-semantics` package should follow that pattern cleanly, but local editable dependency wiring must be documented carefully.
- Memory stored in the same Neo4j database as dbxcarta semantic metadata can become noisy if labels are not namespaced and constraints are not explicit.
- Storing full result sets in memory could leak sensitive analytical output. The safer default is to store metadata and generated SQL only.
- Text-to-SQL prompts can regress if too many prior examples are injected. Memory retrieval should cap examples and prefer successful, recent, schema-overlapping questions.
- Finance Genie table names and default UC scope may drift. The preset must make defaults visible and overridable.
- The first implementation should avoid a UI until the CLI flow is stable and testable.

## Completion Criteria

The project is complete when:

- `sql-semantics/` is a standalone sample with no source dependency on `finance-genie/`.
- The README clearly tells users to set up Finance Genie data before running the sample.
- The dbxcarta preset can validate the Finance Genie Unity Catalog tables.
- dbxcarta can build and verify the semantic layer for those tables.
- The CLI can answer read-only natural-language questions through dbxcarta graph retrieval.
- Neo4j memory records user questions and improves follow-up prompts with relevant prior successful questions.
- Tests cover the preset contract, SQL safety checks, prompt assembly, and memory query behavior.

## Open Questions

- Should `gold_*` tables be optional for the first version, or should the sample require the full Finance Genie Gold pipeline?
- Should memory use the same Neo4j database as dbxcarta semantic metadata, or a separate database?
- What should be the default user identity for local demos: explicit `--user`, Databricks username, or local OS username?
- Should the first delivery be CLI-only, or should it include a minimal Databricks App after the CLI is working?
- Should remembered questions be shared across users by default, or isolated per user unless explicitly enabled?

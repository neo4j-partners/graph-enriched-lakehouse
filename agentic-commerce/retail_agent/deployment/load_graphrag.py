"""Build GraphRAG layer using neo4j-graphrag SimpleKGPipeline.

Run after `retail-agent-load-products`. Reads KnowledgeArticle,
SupportTicket, and Review nodes from Neo4j, chunks and embeds them, extracts
Feature/Symptom/Solution entities, then links the new retrieval graph back to
Product nodes.

Runs on a Databricks cluster or as a Databricks Job.
"""

from __future__ import annotations

import asyncio
import sys

import neo4j
from neo4j_graphrag.experimental.components.types import LexicalGraphConfig
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline

from retail_agent.agent.config import CONFIG
from retail_agent.deployment.runtime import inject_env_params
from retail_agent.integrations.databricks.graphrag import (
    DatabricksGraphRAGEmbedder,
    DatabricksGraphRAGLLM,
)


SCHEMA = {
    "node_types": ["Feature", "Symptom", "Solution"],
    "relationship_types": [
        "HAS_FEATURE",
        "HAS_SYMPTOM",
        "HAS_SOLUTION",
        "RELATED_TO",
    ],
    "patterns": [
        ("Feature", "RELATED_TO", "Symptom"),
        ("Symptom", "HAS_SOLUTION", "Solution"),
        ("Feature", "RELATED_TO", "Solution"),
    ],
}


def _get_neo4j_credentials() -> tuple[str, str]:
    """Get Neo4j URI and password from Databricks secrets via dbutils."""
    scope = CONFIG.secret_scope
    uri_key = CONFIG.neo4j_uri_secret
    password_key = CONFIG.neo4j_password_secret

    try:
        from pyspark.dbutils import DBUtils
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()
        dbutils = DBUtils(spark)
        uri = dbutils.secrets.get(scope, uri_key)
        password = dbutils.secrets.get(scope, password_key)
        if uri and password:
            print(f"  Credentials from dbutils secrets ({scope})")
            return uri, password
    except Exception:
        pass

    raise ValueError(
        f"Could not read Neo4j credentials from Databricks secrets "
        f"(scope={scope}, keys={uri_key}, {password_key}). "
        f"Set them with: databricks secrets put-secret {scope} {uri_key}"
    )


def _fetch_documents(driver: neo4j.Driver) -> list[dict]:
    """Fetch document texts from Neo4j nodes created by the product loader."""
    documents: list[dict] = []

    records, _, _ = driver.execute_query(
        "MATCH (ka:KnowledgeArticle) "
        "RETURN ka.article_id AS id, ka.content AS text"
    )
    article_count = 0
    for record in records:
        text = record["text"]
        if text and text.strip():
            documents.append({
                "text": text,
                "metadata": {
                    "source_type": "KnowledgeArticle",
                    "source_id": record["id"],
                },
            })
            article_count += 1
    print(f"  KnowledgeArticles: {article_count}")

    records, _, _ = driver.execute_query(
        "MATCH (st:SupportTicket) "
        "RETURN st.ticket_id AS id, "
        "st.issue_description AS issue, st.resolution_text AS resolution"
    )
    ticket_count = 0
    for record in records:
        parts = [
            value
            for value in (record["issue"], record["resolution"])
            if value and value.strip()
        ]
        if parts:
            documents.append({
                "text": "\n\n---\n\n".join(parts),
                "metadata": {
                    "source_type": "SupportTicket",
                    "source_id": record["id"],
                },
            })
            ticket_count += 1
    print(f"  SupportTickets: {ticket_count}")

    records, _, _ = driver.execute_query(
        "MATCH (r:Review) RETURN r.review_id AS id, r.raw_text AS text"
    )
    review_count = 0
    for record in records:
        text = record["text"]
        if text and text.strip():
            documents.append({
                "text": text,
                "metadata": {
                    "source_type": "Review",
                    "source_id": record["id"],
                },
            })
            review_count += 1
    print(f"  Reviews: {review_count}")

    return documents


def _link_chunks_to_documents(driver: neo4j.Driver) -> None:
    """Create HAS_CHUNK relationships from existing document nodes to chunks."""
    for source_type, label, id_property in [
        ("KnowledgeArticle", "KnowledgeArticle", "article_id"),
        ("SupportTicket", "SupportTicket", "ticket_id"),
        ("Review", "Review", "review_id"),
    ]:
        print(f"  Linking chunks to {label} nodes...")
        driver.execute_query(
            f"""
            MATCH (ch:Chunk)-[:FROM_DOCUMENT]->(d:Document {{source_type: $source_type}})
            MATCH (doc:{label})
            WHERE doc.{id_property} = d.source_id
            MERGE (doc)-[:HAS_CHUNK]->(ch)
            SET ch.source_type = $source_type,
                ch.source_id = d.source_id,
                ch.chunk_id = coalesce(ch.chunk_id, elementId(ch))
            """,
            source_type=source_type,
        )


def _create_chunk_entity_relationships(driver: neo4j.Driver) -> None:
    """Create chunk-to-entity relationships used by agent tools."""
    for entity_label, relationship_type in [
        ("Feature", "MENTIONS_FEATURE"),
        ("Symptom", "REPORTS_SYMPTOM"),
        ("Solution", "PROVIDES_SOLUTION"),
    ]:
        print(f"  Creating {relationship_type} retrieval relationships...")
        driver.execute_query(
            f"""
            MATCH (entity:{entity_label})-[:FROM_CHUNK]->(ch:Chunk)
            MERGE (ch)-[:{relationship_type}]->(entity)
            """
        )


def _create_product_shortcuts(driver: neo4j.Driver) -> None:
    """Create Product-level entity relationships by traversing source docs."""
    for relationship_type, entity_label in [
        ("HAS_FEATURE", "Feature"),
        ("HAS_SYMPTOM", "Symptom"),
        ("HAS_SOLUTION", "Solution"),
    ]:
        print(f"  Creating {relationship_type} shortcuts...")
        driver.execute_query(
            f"""
            MATCH (p:Product)<-[:COVERS|ABOUT|REVIEWS]-(doc)-[:HAS_CHUNK]->(ch)
                  <-[:FROM_CHUNK]-(entity:{entity_label})
            MERGE (p)-[:{relationship_type}]->(entity)
            """
        )


def _create_indexes(driver: neo4j.Driver) -> None:
    """Create vector and fulltext indexes on Chunk nodes."""
    dims = CONFIG.embedding_dimensions

    print(f"  Creating vector index (chunk_embedding, {dims} dims)...")
    try:
        driver.execute_query("DROP INDEX chunk_embedding IF EXISTS")
        driver.execute_query(
            f"""
            CREATE VECTOR INDEX chunk_embedding
            FOR (ch:Chunk)
            ON (ch.embedding)
            OPTIONS {{indexConfig: {{
                `vector.dimensions`: {dims},
                `vector.similarity_function`: 'cosine'
            }}}}
            """
        )
    except Exception as exc:
        print(f"    Vector index note: {exc}")

    print("  Creating fulltext index (chunkText)...")
    try:
        driver.execute_query("DROP INDEX chunkText IF EXISTS")
        driver.execute_query(
            """
            CREATE FULLTEXT INDEX chunkText
            FOR (ch:Chunk)
            ON EACH [ch.text]
            OPTIONS {indexConfig: {`fulltext.analyzer`: 'english'}}
            """
        )
    except Exception as exc:
        print(f"    Fulltext index note: {exc}")


def _print_counts(driver: neo4j.Driver) -> None:
    """Print node and relationship counts for verification."""
    queries = [
        ("Chunks", "MATCH (c:Chunk) RETURN count(c) AS count"),
        ("Documents", "MATCH (d:Document) RETURN count(d) AS count"),
        ("Features", "MATCH (f:Feature) RETURN count(f) AS count"),
        ("Symptoms", "MATCH (s:Symptom) RETURN count(s) AS count"),
        ("Solutions", "MATCH (sol:Solution) RETURN count(sol) AS count"),
        ("FROM_CHUNK rels", "MATCH ()-[r:FROM_CHUNK]->() RETURN count(r) AS count"),
        (
            "FROM_DOCUMENT rels",
            "MATCH ()-[r:FROM_DOCUMENT]->() RETURN count(r) AS count",
        ),
        ("HAS_CHUNK rels", "MATCH ()-[r:HAS_CHUNK]->() RETURN count(r) AS count"),
        (
            "MENTIONS_FEATURE rels",
            "MATCH ()-[r:MENTIONS_FEATURE]->() RETURN count(r) AS count",
        ),
        (
            "REPORTS_SYMPTOM rels",
            "MATCH ()-[r:REPORTS_SYMPTOM]->() RETURN count(r) AS count",
        ),
        (
            "PROVIDES_SOLUTION rels",
            "MATCH ()-[r:PROVIDES_SOLUTION]->() RETURN count(r) AS count",
        ),
        (
            "HAS_FEATURE rels",
            "MATCH ()-[r:HAS_FEATURE]->() RETURN count(r) AS count",
        ),
        (
            "HAS_SYMPTOM rels",
            "MATCH ()-[r:HAS_SYMPTOM]->() RETURN count(r) AS count",
        ),
        (
            "HAS_SOLUTION rels",
            "MATCH ()-[r:HAS_SOLUTION]->() RETURN count(r) AS count",
        ),
        ("NEXT_CHUNK rels", "MATCH ()-[r:NEXT_CHUNK]->() RETURN count(r) AS count"),
    ]
    for label, cypher in queries:
        records, _, _ = driver.execute_query(cypher)
        print(f"  {label}: {records[0]['count']}")


async def load_graphrag() -> int:
    """Build GraphRAG layer using SimpleKGPipeline."""
    inject_env_params()

    print("=" * 60)
    print("GraphRAG Pipeline")
    print("=" * 60)

    print("\nGetting Neo4j credentials...")
    try:
        uri, password = _get_neo4j_credentials()
    except ValueError as exc:
        print(f"  Error: {exc}")
        return 1

    driver = neo4j.GraphDatabase.driver(uri, auth=("neo4j", password))
    try:
        driver.verify_connectivity()
        print("  Connected to Neo4j")

        print("\nFetching documents from Neo4j...")
        documents = _fetch_documents(driver)
        print(f"  Total documents: {len(documents)}")
        if not documents:
            print("\n  No documents found. Has retail-agent-load-products been run?")
            return 1

        print("\nInitializing Databricks model adapters...")
        embedder = DatabricksGraphRAGEmbedder()
        llm = DatabricksGraphRAGLLM()
        print(f"  Embedder: {embedder.model}")
        print(f"  LLM: {llm.model_id}")

        print("\nConfiguring SimpleKGPipeline...")
        pipeline = SimpleKGPipeline(
            llm=llm,
            driver=driver,
            embedder=embedder,
            schema=SCHEMA,
            from_pdf=False,
            lexical_graph_config=LexicalGraphConfig(chunk_id_property="chunk_id"),
            perform_entity_resolution=True,
            on_error="IGNORE",
        )
        print("  Pipeline created")

        print(f"\nProcessing {len(documents)} documents...")
        success = 0
        failed = 0
        for index, document in enumerate(documents, start=1):
            try:
                await pipeline.run_async(
                    text=document["text"],
                    document_metadata=document["metadata"],
                )
                success += 1
            except Exception as exc:
                failed += 1
                source = document["metadata"]
                print(
                    f"  Error on {source['source_type']} {source['source_id']}: "
                    f"{type(exc).__name__}: {exc}"
                )

            if index % 25 == 0 or index == len(documents):
                print(
                    f"  Processed {index}/{len(documents)} "
                    f"(success={success}, failed={failed})"
                )

        print("\nPost-pipeline Step 1: Link chunks to source documents...")
        _link_chunks_to_documents(driver)

        print("\nPost-pipeline Step 2: Create chunk/entity retrieval relationships...")
        _create_chunk_entity_relationships(driver)

        print("\nPost-pipeline Step 3: Create product shortcuts...")
        _create_product_shortcuts(driver)

        print("\nPost-pipeline Step 4: Create indexes...")
        _create_indexes(driver)

        print("\nGraph counts:")
        _print_counts(driver)

        print()
        print("=" * 60)
        print(f"Pipeline complete. {success} processed, {failed} failed.")
        print("=" * 60)
        return 0 if failed == 0 else 1

    finally:
        driver.close()


try:
    import nest_asyncio

    nest_asyncio.apply()
except ImportError:
    pass

def main() -> int:
    """Synchronous console entry point for the async GraphRAG loader."""
    return asyncio.run(load_graphrag())


if __name__ == "__main__":
    sys.exit(main())

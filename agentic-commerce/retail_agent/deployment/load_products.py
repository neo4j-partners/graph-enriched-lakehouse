"""Load sample product data into Neo4j for the Agentic Commerce assistant demo.

Databricks-only version. Runs in a Databricks notebook or job cluster.
Gets Neo4j credentials from Databricks secrets via dbutils,
using the same scope and keys as the deployed agent
(see retail_agent.agent.config).

Uses the Neo4j Spark Connector for node and relationship writes,
and the sync Neo4j Python driver for DDL operations (indexes, embeddings).

Prerequisites:
    Databricks secrets set:
         databricks secrets put-secret retail-agent-secrets neo4j-uri
         databricks secrets put-secret retail-agent-secrets neo4j-password
    Neo4j Spark Connector JAR installed on the cluster.
"""

import sys

from neo4j import GraphDatabase
from pyspark.sql import Row

from retail_agent.data.product_catalog import (
    BOUGHT_TOGETHER,
    CATEGORIES,
    PRODUCTS,
    SHARED_ATTRIBUTES,
)
from retail_agent.data.product_knowledge import (
    KNOWLEDGE_ARTICLES,
    REVIEWS,
    SUPPORT_TICKETS,
)
from retail_agent.agent.config import CONFIG
from retail_agent.deployment.runtime import inject_env_params

NEO4J_FORMAT = "org.neo4j.spark.DataSource"


# ---------------------------------------------------------------------------
# Credentials & Spark setup
# ---------------------------------------------------------------------------

def _get_spark_and_credentials():
    """Get SparkSession and Neo4j credentials from Databricks secrets."""
    from pyspark.dbutils import DBUtils
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    dbutils = DBUtils(spark)

    scope = CONFIG.secret_scope
    uri = dbutils.secrets.get(scope, CONFIG.neo4j_uri_secret)
    password = dbutils.secrets.get(scope, CONFIG.neo4j_password_secret)

    if not uri or not password:
        raise ValueError(
            f"Could not read Neo4j credentials from Databricks secrets "
            f"(scope={scope}, keys={CONFIG.neo4j_uri_secret}, "
            f"{CONFIG.neo4j_password_secret}). "
            f"Set them with: databricks secrets put-secret {scope} "
            f"{CONFIG.neo4j_uri_secret}"
        )

    print(f"  Credentials from dbutils secrets ({scope})")
    return spark, uri, password


# ---------------------------------------------------------------------------
# Spark Connector helpers (matching databricks-neo4j-lab pattern)
# ---------------------------------------------------------------------------

def write_nodes(df, label, id_column):
    """Write a DataFrame as nodes to Neo4j."""
    (df
     .coalesce(1)
     .write
     .format(NEO4J_FORMAT)
     .mode("Overwrite")
     .option("labels", f":{label}")
     .option("node.keys", id_column)
     .option("schema.optimization.node.keys", "UNIQUE")
     .save())
    count = df.count()
    print(f"  Wrote {count} {label} nodes")
    return count


def write_relationships(df, rel_type, source_label, source_key,
                        target_label, target_key):
    """Write relationships to Neo4j using keys strategy."""
    (df
     .coalesce(1)
     .write
     .format(NEO4J_FORMAT)
     .mode("Overwrite")
     .option("relationship", rel_type)
     .option("relationship.save.strategy", "keys")
     .option("relationship.source.labels", f":{source_label}")
     .option("relationship.source.save.mode", "Match")
     .option("relationship.source.node.keys", source_key)
     .option("relationship.target.labels", f":{target_label}")
     .option("relationship.target.save.mode", "Match")
     .option("relationship.target.node.keys", target_key)
     .save())
    count = df.count()
    print(f"  Wrote {count} {rel_type} relationships")
    return count


# ---------------------------------------------------------------------------
# Node creators (Spark Connector)
# ---------------------------------------------------------------------------

def _create_products(spark):
    """Create Product nodes with all properties."""
    rows = []
    for p in PRODUCTS:
        d = p.model_dump()
        d.pop("attributes")  # nested dict — not a flat node property
        rows.append(Row(**d))
    df = spark.createDataFrame(rows)
    write_nodes(df, "Product", "id")


def _create_categories(spark):
    """Create Category nodes."""
    rows = [Row(name=k, description=v) for k, v in CATEGORIES.items()]
    df = spark.createDataFrame(rows)
    write_nodes(df, "Category", "name")


def _create_brands(spark):
    """Create Brand nodes from distinct product brands."""
    brand_names = sorted({p.brand for p in PRODUCTS})
    rows = [Row(name=b) for b in brand_names]
    df = spark.createDataFrame(rows)
    write_nodes(df, "Brand", "name")


def _create_attributes(spark):
    """Create Attribute nodes with composite key (name, value)."""
    rows = [Row(name=a[0], value=a[1]) for a in SHARED_ATTRIBUTES]
    df = spark.createDataFrame(rows)
    write_nodes(df, "Attribute", "name,value")


def _create_knowledge_articles(spark):
    """Create KnowledgeArticle nodes."""
    rows = [Row(**a.model_dump()) for a in KNOWLEDGE_ARTICLES]
    df = spark.createDataFrame(rows)
    write_nodes(df, "KnowledgeArticle", "article_id")


def _create_support_tickets(spark):
    """Create SupportTicket nodes."""
    rows = [Row(**t.model_dump()) for t in SUPPORT_TICKETS]
    df = spark.createDataFrame(rows)
    write_nodes(df, "SupportTicket", "ticket_id")


def _create_reviews(spark):
    """Create Review nodes."""
    rows = [Row(**r.model_dump()) for r in REVIEWS]
    df = spark.createDataFrame(rows)
    write_nodes(df, "Review", "review_id")


# ---------------------------------------------------------------------------
# Relationship creators (Spark Connector)
# ---------------------------------------------------------------------------

def _create_in_category(spark):
    """Create IN_CATEGORY relationships (Product -> Category)."""
    rows = [Row(id=p.id, name=p.category) for p in PRODUCTS]
    df = spark.createDataFrame(rows)
    write_relationships(df, "IN_CATEGORY",
                        "Product", "id", "Category", "name")


def _create_made_by(spark):
    """Create MADE_BY relationships (Product -> Brand)."""
    rows = [Row(id=p.id, name=p.brand) for p in PRODUCTS]
    df = spark.createDataFrame(rows)
    write_relationships(df, "MADE_BY",
                        "Product", "id", "Brand", "name")


def _create_bought_together(spark):
    """Create BOUGHT_TOGETHER relationships with frequency/confidence props."""
    rows = [
        Row(source_id=p[0], target_id=p[1], frequency=p[2], confidence=p[3])
        for p in BOUGHT_TOGETHER
    ]
    df = spark.createDataFrame(rows)
    (df
     .coalesce(1)
     .write
     .format(NEO4J_FORMAT)
     .mode("Overwrite")
     .option("relationship", "BOUGHT_TOGETHER")
     .option("relationship.save.strategy", "keys")
     .option("relationship.source.labels", ":Product")
     .option("relationship.source.save.mode", "Match")
     .option("relationship.source.node.keys", "source_id:id")
     .option("relationship.target.labels", ":Product")
     .option("relationship.target.save.mode", "Match")
     .option("relationship.target.node.keys", "target_id:id")
     .option("relationship.properties", "frequency,confidence")
     .save())
    print(f"  Wrote {df.count()} BOUGHT_TOGETHER relationships")


def _create_has_attribute(spark):
    """Create HAS_ATTRIBUTE relationships (Product -> Attribute)."""
    attr_mappings = [
        ("cushion", "Cushion Level"),
        ("surface", "Surface"),
        ("occasion", "Occasion"),
        ("fit", "Fit"),
        ("material", "Material"),
    ]
    rows = []
    for product in PRODUCTS:
        for attr_key, attr_name in attr_mappings:
            if attr_key in product.attributes:
                rows.append(Row(
                    source_id=product.id,
                    target_name=attr_name,
                    target_value=product.attributes[attr_key],
                ))
    df = spark.createDataFrame(rows)
    (df
     .coalesce(1)
     .write
     .format(NEO4J_FORMAT)
     .mode("Overwrite")
     .option("relationship", "HAS_ATTRIBUTE")
     .option("relationship.save.strategy", "keys")
     .option("relationship.source.labels", ":Product")
     .option("relationship.source.save.mode", "Match")
     .option("relationship.source.node.keys", "source_id:id")
     .option("relationship.target.labels", ":Attribute")
     .option("relationship.target.save.mode", "Match")
     .option("relationship.target.node.keys", "target_name:name,target_value:value")
     .save())
    print(f"  Wrote {df.count()} HAS_ATTRIBUTE relationships")


def _create_covers(spark):
    """Create COVERS relationships (KnowledgeArticle -> Product)."""
    rows = [Row(article_id=a.article_id, id=a.product_id)
            for a in KNOWLEDGE_ARTICLES]
    df = spark.createDataFrame(rows)
    write_relationships(df, "COVERS",
                        "KnowledgeArticle", "article_id", "Product", "id")


def _create_about(spark):
    """Create ABOUT relationships (SupportTicket -> Product)."""
    rows = [Row(ticket_id=t.ticket_id, id=t.product_id)
            for t in SUPPORT_TICKETS]
    df = spark.createDataFrame(rows)
    write_relationships(df, "ABOUT",
                        "SupportTicket", "ticket_id", "Product", "id")


def _create_reviews_rels(spark):
    """Create REVIEWS relationships (Review -> Product)."""
    rows = [Row(review_id=r.review_id, id=r.product_id)
            for r in REVIEWS]
    df = spark.createDataFrame(rows)
    write_relationships(df, "REVIEWS",
                        "Review", "review_id", "Product", "id")


# ---------------------------------------------------------------------------
# DDL operations (sync Neo4j Python driver)
# ---------------------------------------------------------------------------

def _clear_database(driver):
    """Delete all nodes and relationships."""
    driver.execute_query("MATCH (n) DETACH DELETE n")


def _create_similarity_relationships(driver):
    """Create SIMILAR_TO relationships between products in the same category."""
    driver.execute_query(
        """
        MATCH (p1:Product)-[:IN_CATEGORY]->(c)<-[:IN_CATEGORY]-(p2:Product)
        WHERE p1 <> p2
        MERGE (p1)-[:SIMILAR_TO]-(p2)
        """
    )


def _create_vector_index(driver):
    """Create vector index for product embeddings.

    Drops and recreates the index to ensure dimensions match
    CONFIG.embedding_dimensions (e.g. 1024 for Databricks BGE).
    A stale index with wrong dimensions (e.g. 1536 from OpenAI) will
    silently fail every vector query.
    """
    dims = CONFIG.embedding_dimensions

    try:
        driver.execute_query("DROP INDEX product_embedding IF EXISTS")
        driver.execute_query(
            f"""
            CREATE VECTOR INDEX product_embedding
            FOR (p:Product)
            ON (p.embedding)
            OPTIONS {{indexConfig: {{
                `vector.dimensions`: {dims},
                `vector.similarity_function`: 'cosine'
            }}}}
            """
        )
        print(f"  Vector index created — {dims} dimensions")
    except Exception as e:
        print(f"  Vector index creation note: {e}")


def _drop_stale_memory_indexes(driver):
    """Drop agent-memory vector indexes so they can be recreated at the correct size.

    The agent-memory library creates vector indexes during MemoryClient.connect():
        message_embedding_idx, entity_embedding_idx, preference_embedding_idx,
        fact_embedding_idx, task_embedding_idx

    If embedding dimensions changed (e.g., 1536 OpenAI -> 1024 Databricks BGE),
    these must be dropped first. Since _clear_database() already deleted all
    nodes, we drop ALL non-product vector indexes so connect() recreates them
    at the correct size.
    """
    memory_indexes = [
        "message_embedding_idx",
        "entity_embedding_idx",
        "preference_embedding_idx",
        "fact_embedding_idx",
        "task_embedding_idx",
    ]
    try:
        dropped = 0
        for idx_name in memory_indexes:
            driver.execute_query(f"DROP INDEX {idx_name} IF EXISTS")
            dropped += 1
        print(f"  Dropped {dropped} agent-memory vector indexes")
    except Exception as e:
        print(f"  Memory index cleanup note: {e}")


def _generate_embeddings(driver):
    """Generate and store product embeddings using Databricks Foundation Model API."""
    try:
        import mlflow.deployments
    except ImportError:
        print("  mlflow not available — skipping embedding generation.")
        print("  Products will work with text search fallback.")
        return

    model = CONFIG.embedding_model
    print(f"  Model: {model}")

    try:
        client = mlflow.deployments.get_deploy_client("databricks")
        texts = [f"{p.name}: {p.description}" for p in PRODUCTS]

        # Batch in chunks of 100 to avoid request size limits
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = client.predict(
                endpoint=model,
                inputs={"input": batch},
            )
            all_embeddings.extend(item["embedding"] for item in response["data"])
            print(f"  Embedded {min(i + batch_size, len(texts))}/{len(texts)} products")

        for i, product in enumerate(PRODUCTS):
            driver.execute_query(
                """
                MATCH (p:Product {id: $product_id})
                SET p.embedding = $embedding
                """,
                product_id=product.id,
                embedding=all_embeddings[i],
            )

        print(f"  Generated embeddings for {len(PRODUCTS)} products")

    except Exception as e:
        print(f"  Embedding generation failed: {e}")
        print("  Products will work with text search fallback.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_sample_data() -> int:
    """Load all sample data into Neo4j."""
    inject_env_params()

    print("Getting Neo4j credentials from Databricks secrets...")
    try:
        spark, uri, password = _get_spark_and_credentials()
    except ValueError as e:
        print(f"  Error: {e}")
        return 1

    # Configure Spark Connector
    spark.conf.set("neo4j.url", uri)
    spark.conf.set("neo4j.authentication.basic.username", "neo4j")
    spark.conf.set("neo4j.authentication.basic.password", password)
    spark.conf.set("neo4j.database", "neo4j")

    # Sync driver for DDL operations
    driver = GraphDatabase.driver(uri, auth=("neo4j", password))
    driver.verify_connectivity()

    print("Clearing existing data...")
    _clear_database(driver)

    # --- Nodes (Spark Connector) ---
    print("Creating products...")
    _create_products(spark)

    print("Creating categories...")
    _create_categories(spark)

    print("Creating brands...")
    _create_brands(spark)

    print("Creating attributes...")
    _create_attributes(spark)

    print("Creating knowledge articles...")
    _create_knowledge_articles(spark)

    print("Creating support tickets...")
    _create_support_tickets(spark)

    print("Creating reviews...")
    _create_reviews(spark)

    # --- Relationships (Spark Connector) ---
    print("Creating IN_CATEGORY relationships...")
    _create_in_category(spark)

    print("Creating MADE_BY relationships...")
    _create_made_by(spark)

    print("Creating BOUGHT_TOGETHER relationships...")
    _create_bought_together(spark)

    print("Creating HAS_ATTRIBUTE relationships...")
    _create_has_attribute(spark)

    print("Creating COVERS relationships...")
    _create_covers(spark)

    print("Creating ABOUT relationships...")
    _create_about(spark)

    print("Creating REVIEWS relationships...")
    _create_reviews_rels(spark)

    # --- DDL / Cypher (sync driver) ---
    print("Creating similarity relationships...")
    _create_similarity_relationships(driver)

    print("Creating vector index...")
    _create_vector_index(driver)

    print("Dropping stale agent-memory indexes...")
    _drop_stale_memory_indexes(driver)

    print("Generating product embeddings...")
    _generate_embeddings(driver)

    driver.close()

    print(f"\nSample data loaded successfully!")
    print(f"  Products: {len(PRODUCTS)}")
    print(f"  Categories: {len(CATEGORIES)}")
    print(f"  Bought-together pairs: {len(BOUGHT_TOGETHER)}")
    print(f"  Knowledge articles: {len(KNOWLEDGE_ARTICLES)}")
    print(f"  Support tickets: {len(SUPPORT_TICKETS)}")
    print(f"  Reviews: {len(REVIEWS)}")
    return 0


if __name__ == "__main__":
    sys.exit(load_sample_data())

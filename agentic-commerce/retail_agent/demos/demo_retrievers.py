"""Demonstrate GraphRAG retriever patterns against the entity-enriched graph.

Run AFTER load_products.py and load_graphrag.py. Shows four neo4j-graphrag
retriever classes with progressively richer retrieval:

  1. VectorRetriever         — plain semantic search (baseline)
  2. VectorCypherRetriever   — vector + entity traversal (comparison)
  3. HybridCypherRetriever   — hybrid search + entity traversal
  4. Text2CypherRetriever    — LLM-generated Cypher, pure graph query

Runs on a Databricks cluster. Requires neo4j-graphrag installed on the cluster.
"""

import sys
from typing import Any, List, Optional, Type, Union

import mlflow.deployments
from neo4j import GraphDatabase
from neo4j_graphrag.embeddings.base import Embedder
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.llm.base import LLMInterfaceV2
from neo4j_graphrag.llm.types import LLMResponse
from neo4j_graphrag.retrievers import (
    HybridCypherRetriever,
    Text2CypherRetriever,
    VectorCypherRetriever,
    VectorRetriever,
)
from neo4j_graphrag.types import LLMMessage
from pydantic import BaseModel

from retail_agent.agent.config import CONFIG
from retail_agent.deployment.runtime import inject_env_params


# ---------------------------------------------------------------------------
# Neo4j credentials (same pattern as load_products.py / load_graphrag.py)
# ---------------------------------------------------------------------------


def _get_neo4j_credentials() -> tuple[str, str]:
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
            return uri, password
    except Exception:
        pass

    raise ValueError(
        f"Could not read Neo4j credentials from Databricks secrets "
        f"(scope={scope}, keys={uri_key}, {password_key})"
    )


# ---------------------------------------------------------------------------
# neo4j-graphrag interface adapters (Databricks Foundation Model API)
# ---------------------------------------------------------------------------


class DatabricksEmbeddings(Embedder):
    """Embedder using Databricks Foundation Model API via mlflow.deployments."""

    def __init__(self, model_id: str = CONFIG.embedding_model):
        self.model_id = model_id
        self._client = mlflow.deployments.get_deploy_client("databricks")

    def embed_query(self, text: str) -> list[float]:
        response = self._client.predict(
            endpoint=self.model_id,
            inputs={"input": [text]},
        )
        return response["data"][0]["embedding"]


class DatabricksLLM(LLMInterfaceV2):
    """LLM using Databricks Foundation Model API via mlflow.deployments.

    Handles both V2 (List[LLMMessage]) and V1 (str) invoke signatures
    so it works with both GraphRAG and Text2CypherRetriever.
    """

    def __init__(self, model_id: str = CONFIG.llm_endpoint):
        super().__init__(model_name=model_id)
        self.model_id = model_id
        self._client = mlflow.deployments.get_deploy_client("databricks")

    def invoke(
        self,
        input: Union[str, List[LLMMessage]],
        response_format: Optional[Union[Type[BaseModel], dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        # Text2CypherRetriever calls invoke(str); GraphRAG calls invoke(List)
        if isinstance(input, str):
            messages = [{"role": "user", "content": input}]
        else:
            messages = [{"role": msg["role"], "content": msg["content"]} for msg in input]

        response = self._client.predict(
            endpoint=self.model_id,
            inputs={"messages": messages, "max_tokens": 2048},
        )
        content = response["choices"][0]["message"]["content"]
        return LLMResponse(content=content)

    async def ainvoke(
        self,
        input: Union[str, List[LLMMessage]],
        response_format: Optional[Union[Type[BaseModel], dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return self.invoke(input, response_format=response_format)


# ---------------------------------------------------------------------------
# Retrieval queries for Cypher-enhanced retrievers
# ---------------------------------------------------------------------------

VECTOR_CYPHER_QUERY = """
RETURN node.text AS text,
       score,
       collect { MATCH (node)-[:MENTIONS_FEATURE]->(f:Feature) RETURN f.name } AS features,
       collect { MATCH (node)-[:REPORTS_SYMPTOM]->(s:Symptom) RETURN s.name } AS symptoms,
       collect { MATCH (node)-[:PROVIDES_SOLUTION]->(sol:Solution) RETURN sol.name } AS solutions,
       collect {
           MATCH (node)-[:REPORTS_SYMPTOM]->(s:Symptom)<-[:REPORTS_SYMPTOM]-(other:Chunk)
           WHERE other <> node
           MATCH (other)<-[:HAS_CHUNK]-(doc)-[:COVERS|ABOUT|REVIEWS]->(p:Product)
           RETURN DISTINCT p.name
       } AS related_products
"""

HYBRID_CYPHER_QUERY = """
RETURN node.text AS text,
       score,
       collect { MATCH (node)-[:MENTIONS_FEATURE]->(f:Feature) RETURN f.name } AS features,
       collect { MATCH (node)-[:REPORTS_SYMPTOM]->(s:Symptom) RETURN s.name } AS symptoms,
       collect { MATCH (node)-[:PROVIDES_SOLUTION]->(sol:Solution) RETURN sol.name } AS solutions,
       collect {
           MATCH (node)-[:PROVIDES_SOLUTION]->(sol:Solution)<-[:PROVIDES_SOLUTION]-(other:Chunk)
           WHERE other <> node
           MATCH (other)<-[:HAS_CHUNK]-(doc)-[:COVERS|ABOUT|REVIEWS]->(p:Product)
           RETURN DISTINCT p.name
       } AS products_with_same_solution
"""

# Few-shot examples for Text2CypherRetriever.
# Uses modern Cypher syntax: explicit grouping, null-safe sorting.
TEXT2CYPHER_EXAMPLES = [
    "Question: What are the most common symptoms for running shoes?\n"
    "Cypher: MATCH (p:Product)-[:IN_CATEGORY]->(c:Category {name: 'Running Shoes'}), "
    "(p)-[:HAS_SYMPTOM]->(s:Symptom) "
    "WITH s.name AS symptom, count(DISTINCT p) AS product_count "
    "RETURN symptom, product_count "
    "ORDER BY product_count DESC LIMIT 10",

    "Question: Which products share the outsole separation issue?\n"
    "Cypher: MATCH (p:Product)-[:HAS_SYMPTOM]->(s:Symptom) "
    "WHERE s.name CONTAINS 'outsole' "
    "RETURN p.name AS product, s.name AS symptom "
    "ORDER BY p.name",

    "Question: What solutions exist for yellowing on shoes?\n"
    "Cypher: MATCH (p:Product)-[:HAS_SYMPTOM]->(s:Symptom), "
    "(p)-[:HAS_SOLUTION]->(sol:Solution) "
    "WHERE s.name CONTAINS 'yellow' "
    "RETURN p.name AS product, s.name AS symptom, sol.name AS solution",

    "Question: Which features are shared across the most products?\n"
    "Cypher: MATCH (p:Product)-[:HAS_FEATURE]->(f:Feature) "
    "WITH f.name AS feature, count(DISTINCT p) AS product_count "
    "WHERE product_count > 1 "
    "RETURN feature, product_count "
    "ORDER BY product_count DESC LIMIT 10",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_header(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def _print_retriever_results(result):
    """Print raw retriever results."""
    print(f"\n  Retrieved {len(result.items)} results:\n")
    for i, item in enumerate(result.items, 1):
        meta = item.metadata or {}
        score = meta.get("score")
        score_str = f"  score={score:.4f}" if score is not None else ""
        # Show enough content to see entity data in Cypher retriever results
        text = item.content[:400].replace("\n", " ")
        print(f"  [{i}]{score_str}")
        print(f"      {text}")
        if len(item.content) > 400:
            print(f"      ...")
    print()


def _run_graphrag(llm, retriever, query: str, retriever_config: dict | None = None):
    """Run GraphRAG and print the LLM answer."""
    rag = GraphRAG(llm=llm, retriever=retriever)
    response = rag.search(
        query,
        retriever_config=retriever_config or {},
        return_context=True,
        response_fallback="No relevant information found.",
    )
    print(f"  GraphRAG Answer:\n")
    print(f"  {response.answer}")
    return response


# ---------------------------------------------------------------------------
# Demo sections
# ---------------------------------------------------------------------------


def demo_vector_vs_vector_cypher(driver, embedder, llm):
    """Section 1: VectorRetriever vs VectorCypherRetriever (side-by-side)."""
    query = "My running shoes feel flat and unresponsive. What should I do?"

    # --- 1a: VectorRetriever (baseline) ---
    _print_header("1a. VectorRetriever (baseline semantic search)")
    print(f"\n  Query: \"{query}\"\n")

    vector_retriever = VectorRetriever(
        driver=driver,
        index_name="chunk_embedding",
        embedder=embedder,
        return_properties=["text", "chunk_id", "source_type"],
    )
    vector_result = vector_retriever.search(query_text=query, top_k=5)
    _print_retriever_results(vector_result)
    _run_graphrag(llm, vector_retriever, query, retriever_config={"top_k": 5})

    # --- 1b: VectorCypherRetriever (entity-aware) ---
    _print_header("1b. VectorCypherRetriever (vector + entity traversal)")
    print(f"\n  Query: \"{query}\" (same query)\n")

    vector_cypher_retriever = VectorCypherRetriever(
        driver=driver,
        index_name="chunk_embedding",
        embedder=embedder,
        retrieval_query=VECTOR_CYPHER_QUERY,
    )
    cypher_result = vector_cypher_retriever.search(query_text=query, top_k=5)
    _print_retriever_results(cypher_result)
    _run_graphrag(llm, vector_cypher_retriever, query, retriever_config={"top_k": 5})

    # --- Comparison callout ---
    print(f"\n  {'─' * 60}")
    print("  COMPARISON: What entity traversal added")
    print(f"  {'─' * 60}")
    print("  VectorRetriever returns only the closest-matching chunks.")
    print("  VectorCypherRetriever traverses from those chunks through")
    print("  extracted Symptom/Feature/Solution entities to find related")
    print("  chunks from OTHER products — cross-product context that no")
    print("  amount of vector similarity alone would reliably surface.")


def demo_hybrid_cypher(driver, embedder, llm):
    """Section 2: HybridCypherRetriever."""
    query = "Continental outsole peeling after 3 months"

    _print_header("2. HybridCypherRetriever (hybrid search + entity traversal)")
    print(f"\n  Query: \"{query}\"\n")
    print("  Why hybrid? 'Continental' is a specific brand term — fulltext")
    print("  search catches the exact keyword match while vector search")
    print("  finds semantically similar content about outsole issues.\n")

    hybrid_cypher_retriever = HybridCypherRetriever(
        driver=driver,
        vector_index_name="chunk_embedding",
        fulltext_index_name="chunkText",
        embedder=embedder,
        retrieval_query=HYBRID_CYPHER_QUERY,
    )
    result = hybrid_cypher_retriever.search(query_text=query, top_k=5)
    _print_retriever_results(result)
    _run_graphrag(llm, hybrid_cypher_retriever, query, retriever_config={"top_k": 5})


def demo_text2cypher(driver, llm):
    """Section 3: Text2CypherRetriever."""
    query = "What are the most common problems with running shoes?"

    _print_header("3. Text2CypherRetriever (LLM generates Cypher, pure graph query)")
    print(f"\n  Query: \"{query}\"\n")
    print("  No embeddings needed — the LLM translates natural language")
    print("  into a Cypher query that aggregates over the entity graph.\n")

    text2cypher_retriever = Text2CypherRetriever(
        driver=driver,
        llm=llm,
        examples=TEXT2CYPHER_EXAMPLES,
    )
    result = text2cypher_retriever.search(query_text=query)

    # Text2CypherRetriever includes the generated Cypher in metadata
    if result.metadata and "cypher" in result.metadata:
        print(f"  Generated Cypher:\n  {result.metadata['cypher']}\n")

    _print_retriever_results(result)
    _run_graphrag(llm, text2cypher_retriever, query, retriever_config={})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def demo_retrievers() -> int:
    """Run all retriever demos."""
    inject_env_params()

    print("=== GraphRAG Retriever Demo ===\n")

    print("Getting Neo4j credentials...")
    try:
        uri, password = _get_neo4j_credentials()
    except ValueError as e:
        print(f"  Error: {e}")
        return 1

    driver = GraphDatabase.driver(uri, auth=("neo4j", password))
    driver.verify_connectivity()
    print("  Connected to Neo4j\n")

    embedder = DatabricksEmbeddings()
    llm = DatabricksLLM()
    print(f"  Embedder: {embedder.model_id}")
    print(f"  LLM: {llm.model_id}")

    try:
        demo_vector_vs_vector_cypher(driver, embedder, llm)
        demo_hybrid_cypher(driver, embedder, llm)
        demo_text2cypher(driver, llm)
    finally:
        driver.close()

    print(f"\n{'=' * 70}")
    print("  Demo complete.")
    print(f"{'=' * 70}")
    return 0


if __name__ == "__main__":
    sys.exit(demo_retrievers())

"""Databricks Foundation Model API embedder for neo4j-agent-memory.

Implements the Embedder protocol (dimensions, embed, embed_batch) by calling
a Databricks built-in embedding model via mlflow.deployments.predict().

Follows the validation and error handling patterns used by the Databricks
Foundation Model API embedding examples.
"""

import asyncio
import logging
from functools import partial

import mlflow.deployments

logger = logging.getLogger(__name__)


class DatabricksEmbedder:
    """Embedder using Databricks Foundation Model API via mlflow.deployments.

    Uses the standard Databricks deployment client pattern:
        client = mlflow.deployments.get_deploy_client("databricks")
        response = client.predict(endpoint=model, inputs={"input": [text]})
    """

    def __init__(
        self,
        model: str = "databricks-bge-large-en",
        dims: int = 1024,
    ):
        self._model = model
        self._dims = dims
        self._client: mlflow.deployments.BaseDeploymentClient | None = None

    def _get_client(self) -> mlflow.deployments.BaseDeploymentClient:
        """Lazy client initialization."""
        if self._client is None:
            self._client = mlflow.deployments.get_deploy_client("databricks")
        return self._client

    @property
    def dimensions(self) -> int:
        return self._dims

    def validate_endpoint(self) -> bool:
        """Validate the embedding endpoint before use.

        Sends a test request and verifies the response structure and
        dimensions match configuration. Call this during initialization
        to catch misconfigurations early.
        """
        try:
            logger.info("Validating embedding endpoint: %s", self._model)
            client = self._get_client()
            response = client.predict(
                endpoint=self._model,
                inputs={"input": ["embedding validation test"]},
            )

            if "data" not in response:
                logger.error(
                    "No 'data' key in response. Keys: %s", list(response.keys())
                )
                return False

            if not response["data"]:
                logger.error("Empty 'data' array in response")
                return False

            embedding = response["data"][0].get("embedding")
            if embedding is None:
                logger.error("No 'embedding' key in response data")
                return False

            if len(embedding) != self._dims:
                logger.error(
                    "Dimension mismatch: expected %d, got %d",
                    self._dims,
                    len(embedding),
                )
                return False

            logger.info(
                "Embedding validation passed: %s, %d dimensions",
                self._model,
                len(embedding),
            )
            return True

        except Exception as e:
            logger.error("Embedding validation failed: %s: %s", type(e).__name__, e)
            return False

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in one request."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(
                    self._get_client().predict,
                    endpoint=self._model,
                    inputs={"input": texts},
                ),
            )
        except Exception as e:
            logger.error("Embedding request failed: %s: %s", type(e).__name__, e)
            raise

        if "data" not in response:
            raise ValueError(
                f"Unexpected response from {self._model}: "
                f"missing 'data' key. Keys: {list(response.keys())}"
            )

        embeddings = []
        for i, item in enumerate(response["data"]):
            embedding = item.get("embedding")
            if embedding is None:
                raise ValueError(
                    f"Missing 'embedding' key in response['data'][{i}]"
                )
            if len(embedding) != self._dims:
                raise ValueError(
                    f"Dimension mismatch at index {i}: "
                    f"expected {self._dims}, got {len(embedding)}"
                )
            embeddings.append(embedding)

        return embeddings

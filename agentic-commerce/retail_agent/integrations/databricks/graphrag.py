"""Databricks Foundation Model API adapters for neo4j-graphrag."""

from __future__ import annotations

import logging
from typing import Any

import mlflow.deployments
from neo4j_graphrag.embeddings.base import Embedder
from neo4j_graphrag.llm.base import LLMInterface
from neo4j_graphrag.llm.types import LLMResponse
from neo4j_graphrag.message_history import MessageHistory
from neo4j_graphrag.types import LLMMessage

from retail_agent.agent.config import CONFIG

logger = logging.getLogger(__name__)


class DatabricksGraphRAGEmbedder(Embedder):
    """Embedder using Databricks Foundation Model API via mlflow.deployments."""

    def __init__(
        self,
        model: str = CONFIG.embedding_model,
        dimensions: int = CONFIG.embedding_dimensions,
    ) -> None:
        super().__init__()
        self.model = model
        self.dimensions = dimensions
        self._client = mlflow.deployments.get_deploy_client("databricks")

    def embed_query(self, text: str) -> list[float]:
        response = self._client.predict(
            endpoint=self.model,
            inputs={"input": [text]},
        )
        embedding = response["data"][0]["embedding"]

        if len(embedding) != self.dimensions:
            logger.warning(
                "Dimension mismatch: expected %d, got %d",
                self.dimensions,
                len(embedding),
            )

        return embedding


class DatabricksGraphRAGLLM(LLMInterface):
    """LLM using Databricks Foundation Model API via mlflow.deployments."""

    def __init__(
        self,
        model_id: str = CONFIG.llm_endpoint,
        model_params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(model_name=model_id, model_params=model_params)
        self.model_id = model_id
        self._client = mlflow.deployments.get_deploy_client("databricks")

    def invoke(
        self,
        input: str,
        message_history: list[LLMMessage] | MessageHistory | None = None,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        messages: list[dict[str, str]] = []

        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        if message_history:
            history = (
                message_history.messages
                if isinstance(message_history, MessageHistory)
                else message_history
            )
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": input})

        params: dict[str, Any] = {"messages": messages, "max_tokens": 2048}
        if self.model_params:
            params.update(self.model_params)

        response = self._client.predict(
            endpoint=self.model_id,
            inputs=params,
        )
        content = response["choices"][0]["message"]["content"]
        return LLMResponse(content=content)

    async def ainvoke(
        self,
        input: str,
        message_history: list[LLMMessage] | MessageHistory | None = None,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        return self.invoke(
            input,
            message_history=message_history,
            system_instruction=system_instruction,
        )

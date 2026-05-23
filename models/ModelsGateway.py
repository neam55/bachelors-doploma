from __future__ import annotations

from typing import Any, Final

from models.Base import (
    BaseEmbeddingsProvider,
    BaseLLMProvider,
    BaseRerankerProvider,
    ChatMessage,
)
from models.Config import GatewayConfig
from models.runtime_guard import strip_model_overrides


class ModelsGateway:
    """Gateway with model names fixed at construction from GatewayConfig only."""

    def __init__(
        self,
        llm: BaseLLMProvider,
        embedder: BaseEmbeddingsProvider,
        reranker: BaseRerankerProvider,
        *,
        llm_model: str,
        embedder_model: str,
        reranker_model: str,
    ) -> None:
        if not llm_model or not embedder_model or not reranker_model:
            raise ValueError("Model names must be non-empty strings from config")

        self._llm: Final[BaseLLMProvider] = llm
        self._embedder: Final[BaseEmbeddingsProvider] = embedder
        self._reranker: Final[BaseRerankerProvider] = reranker
        self._llm_model: Final[str] = llm_model
        self._embedder_model: Final[str] = embedder_model
        self._reranker_model: Final[str] = reranker_model

    @classmethod
    def from_config(cls, config: GatewayConfig) -> ModelsGateway:
        from models.factories.CrossEncoderFactory import RerankerFactory
        from models.factories.EmbedderFactory import EmbedderFactory
        from models.factories.LlmServiceFactory import LlmServiceFactory

        return cls(
            llm=LlmServiceFactory.create(config.llm),
            embedder=EmbedderFactory.create(config.embedder),
            reranker=RerankerFactory.create(config.reranker),
            llm_model=config.llm.model,
            embedder_model=config.embedder.model,
            reranker_model=config.reranker.model,
        )

    @property
    def llm_model(self) -> str:
        return self._llm_model

    @property
    def embedder_model(self) -> str:
        return self._embedder_model

    @property
    def reranker_model(self) -> str:
        return self._reranker_model

    def chat(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        safe_kwargs = strip_model_overrides(kwargs, operation="chat")
        messages: list[ChatMessage] = []
        if system:
            messages.append(ChatMessage(role="system", content=system))
        messages.append(ChatMessage(role="user", content=prompt))
        return self._llm.chat(messages, **safe_kwargs)

    def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        safe_kwargs = strip_model_overrides(kwargs, operation="embed")
        return self._embedder.embed(texts, **safe_kwargs)

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
        **kwargs: Any,
    ) -> list[tuple[int, float]]:
        safe_kwargs = strip_model_overrides(kwargs, operation="rerank")
        return self._reranker.rerank(
            query,
            documents,
            top_k=top_k,
            **safe_kwargs,
        )

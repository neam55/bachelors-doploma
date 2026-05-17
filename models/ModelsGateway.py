from models.Base import (
    BaseEmbeddingsProvider,
    BaseLLMProvider,
    BaseRerankerProvider,
    ChatMessage,
)


class ModelsGateway:
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
        self._llm = llm
        self._embedder = embedder
        self._reranker = reranker
        self._llm_model = llm_model
        self._embedder_model = embedder_model
        self._reranker_model = reranker_model

    def chat(self, prompt: str, *, system: str | None = None, **kwargs) -> str:
        messages = []
        if system:
            messages.append(ChatMessage(role="system", content=system))
        messages.append(ChatMessage(role="user", content=prompt))
        return self._llm.chat(self._llm_model, messages, **kwargs)

    def embed(self, texts: list[str], **kwargs) -> list[list[float]]:
        return self._embedder.embed(self._embedder_model, texts, **kwargs)

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
        **kwargs,
    ) -> list[tuple[int, float]]:
        return self._reranker.rerank(
            self._reranker_model,
            query,
            documents,
            top_k=top_k,
            **kwargs,
        )

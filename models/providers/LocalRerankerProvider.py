from __future__ import annotations

from typing import Any

from models.Base import BaseRerankerProvider, ProviderContext
from models.ProviderRegistry import reranker_registry
from sentence_transformers import CrossEncoder

class LocalRerankerProvider(BaseRerankerProvider):
    def __init__(self, context: ProviderContext, default_model: str) -> None:

        device = context.options.get("device", "cpu")
        self._backend = context.options.get("backend", "torch")
        self._default_model = default_model
        self._batch_size = context.options.get("batch_size", 32)
        self._model = CrossEncoder(default_model, device=device, backend=self._backend, trust_remote_code=True)

    def rerank(
        self,
        model: str,
        query: str,
        documents: list[str],
        top_k: int | None = None,
        **kwargs: Any,
    ) -> list[tuple[int, float]]:
        _ = model
        if not documents:
            return []

        pairs = [[query, doc] for doc in documents]
        scores = self._model.predict(pairs, batch_size=self._batch_size, **kwargs)
        ranked = sorted(
            enumerate(float(s) for s in scores),
            key=lambda item: item[1],
            reverse=True,
        )
        if top_k is not None:
            ranked = ranked[:top_k]
        return ranked


@reranker_registry.register("local")
def _create_local_reranker(
    *,
    model: str,
    context: ProviderContext,
) -> BaseRerankerProvider:
    return LocalRerankerProvider(context=context, default_model=model)

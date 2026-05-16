from __future__ import annotations
from typing import Any
from models.Base import BaseEmbeddingsProvider, ProviderContext
from models.ProviderRegistry import embedder_registry
from sentence_transformers import SentenceTransformer

class LocalEmbedderProvider(BaseEmbeddingsProvider):
    def __init__(self, context: ProviderContext, default_model: str) -> None:
        device = context.options.get("device", "cpu")
        self._batch_size = context.options.get("batch_size", 128)
        self._default_model = default_model
        self._backend = context.options.get("backend", "torch")
        self._model = SentenceTransformer(default_model, device=device, backend=self._backend)

    def embed(self, model: str, texts: list[str], **kwargs: Any) -> list[list[float]]:
        _ = model 
        normalize = kwargs.pop("normalize_embeddings", True)
        vectors = self._model.encode(texts, normalize_embeddings=normalize, batch_size=self._batch_size, **kwargs)
        return vectors.tolist()


@embedder_registry.register("local")
def _create_local_embedder(
    *,
    model: str,
    context: ProviderContext,
) -> BaseEmbeddingsProvider:
    return LocalEmbedderProvider(context=context, default_model=model)

from __future__ import annotations

from typing import Any

from models.exceptions import ProviderConfigurationError

_MODEL_OVERRIDE_KEYS = frozenset(
    {
        "model",
        "model_id",
        "model_name",
        "modelId",
        "embedding_model",
        "llm_model",
        "reranker_model",
    }
)


def strip_model_overrides(kwargs: dict[str, Any], *, operation: str) -> dict[str, Any]:
    blocked = _MODEL_OVERRIDE_KEYS.intersection(kwargs)
    if blocked:
        keys = ", ".join(sorted(blocked))
        raise ProviderConfigurationError(
            f"Cannot override model at runtime in {operation}(); "
            f"configure models only in GatewayConfig.yaml (blocked: {keys})"
        )
    return dict(kwargs)

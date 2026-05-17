from __future__ import annotations

from typing import Any

from huggingface_hub import InferenceClient

from models.Base import BaseLLMProvider, ChatMessage, ProviderContext
from models.ProviderRegistry import llm_registry


class HuggingFaceLLMProvider(BaseLLMProvider):
    def __init__(self, context: ProviderContext, default_model: str) -> None:
        self._default_model = default_model
        self._generation = dict(context.generation)
        self._client = InferenceClient(
            api_key=context.api_key,
            base_url=context.base_url,
            timeout=context.timeout,
        )

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> str:
        resolved = model or self._default_model
        payload = [{"role": m.role, "content": m.content} for m in messages]
        params = {**self._generation, **kwargs}
        #print(f"[HuggingFaceLLM] generation params: {params}")
        completion = self._client.chat.completions.create(
            model=resolved,
            messages=payload,
            **params,
        )
        return completion.choices[0].message.content


@llm_registry.register("huggingface")
def _create_huggingface_llm(
    *,
    model: str,
    context: ProviderContext,
) -> BaseLLMProvider:
    return HuggingFaceLLMProvider(context=context, default_model=model)

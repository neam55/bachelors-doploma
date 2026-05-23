from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

@dataclass
class ProviderContext:
    api_key: str | None = None
    base_url: str | None = None
    model_provider : str | None = None
    timeout: int = 30
    options: dict[str, Any] = field(default_factory=dict)
    generation: dict[str, Any] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> str:
        ...


class BaseEmbeddingsProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        ...

class BaseRerankerProvider(ABC):
    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
        **kwargs: Any,
    ) -> list[tuple[int, float]]:
        ...

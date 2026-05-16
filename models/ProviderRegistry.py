from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from models.exceptions import ProviderNotFoundError

T = TypeVar("T")
Factory = Callable[..., T]


class ProviderRegistry(Generic[T]):

    def __init__(self, capability: str) -> None:
        self._capability = capability
        self._factories: dict[str, Factory[T]] = {}

    def register(self, name: str) -> Callable[[Factory[T]], Factory[T]]:
        def decorator(factory: Factory[T]) -> Factory[T]:
            key = name.strip().lower()
            if key in self._factories:
                raise ValueError(
                    f"{self._capability} provider '{key}' is already registered"
                )
            self._factories[key] = factory
            return factory

        return decorator

    def create(self, name: str, *args, **kwargs) -> T:
        key = name.strip().lower()
        try:
            factory = self._factories[key]
        except KeyError as exc:
            raise ProviderNotFoundError(
                self._capability, name, self.list_providers()
            ) from exc
        return factory(*args, **kwargs)

    def list_providers(self) -> list[str]:
        return sorted(self._factories.keys())

    def is_registered(self, name: str) -> bool:
        return name.strip().lower() in self._factories


llm_registry: ProviderRegistry = ProviderRegistry("llm")
embedder_registry: ProviderRegistry = ProviderRegistry("embedder")
reranker_registry: ProviderRegistry = ProviderRegistry("reranker")

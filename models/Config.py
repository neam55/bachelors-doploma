from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from models.Base import ProviderContext
from models.exceptions import ProviderConfigurationError

_dotenv_loaded = False


def _ensure_dotenv() -> None:
    global _dotenv_loaded
    if not _dotenv_loaded:
        load_dotenv()
        _dotenv_loaded = True


def _require_env(name: str, *, section: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ProviderConfigurationError(
            f"Environment variable '{name}' is not set (required by '{section}')"
        )
    return value


@dataclass
class ServiceConfig:
    provider: str
    model: str
    timeout: int = 30
    api_key_env: str | None = None
    base_url: str | None = None
    base_url_env: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    generation: dict[str, Any] = field(default_factory=dict)

    def to_context(self, *, section: str = "service") -> ProviderContext:
        _ensure_dotenv()

        api_key = (
            _require_env(self.api_key_env, section=section)
            if self.api_key_env
            else None
        )

        base_url = self.base_url
        if self.base_url_env:
            base_url = os.environ.get(self.base_url_env) or base_url

        return ProviderContext(
            api_key=api_key,
            base_url=base_url,
            timeout=self.timeout,
            options=dict(self.options),
            generation=dict(self.generation),
        )


@dataclass
class GatewayConfig:
    llm: ServiceConfig
    embedder: ServiceConfig
    reranker: ServiceConfig


def _parse_service(raw: dict[str, Any], section: str) -> ServiceConfig:
    try:
        return ServiceConfig(
            provider=str(raw["provider"]),
            model=str(raw["model"]),
            timeout=int(raw.get("timeout", 30)),
            api_key_env=raw.get("api_key_env"),
            base_url=raw.get("base_url"),
            base_url_env=raw.get("base_url_env"),
            options=dict(raw.get("options", {})),
            generation=dict(raw.get("generation", {})),
        )
    except (KeyError, TypeError) as exc:
        raise ProviderConfigurationError(
            f"Invalid config section '{section}': {exc}"
        ) from exc


class ConfigLoader:
    @staticmethod
    def load(path: str | Path = "./models/GatewayConfig.yaml") -> GatewayConfig:
        _ensure_dotenv()

        config_path = Path(path)
        with config_path.open(encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}

        return GatewayConfig(
            llm=_parse_service(raw["llm"], "llm"),
            embedder=_parse_service(raw["embedder"], "embedder"),
            reranker=_parse_service(
                raw.get("reranker") or raw.get("cross-encoder"),
                "reranker",
            ),
        )

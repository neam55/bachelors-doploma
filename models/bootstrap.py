from __future__ import annotations

from pathlib import Path

from models.Config import ConfigLoader, GatewayConfig
from models.ModelsGateaway import ModelsGateway
from models.factories.CrossEncoderFactory import RerankerFactory
from models.factories.EmbedderFactory import EmbedderFactory
from models.factories.LlmServiceFactory import LlmServiceFactory
from models.plugins import discover_plugins


def create_gateway(
    config_path: str | Path = "./models/GatewayConfig.yaml",
    *,
    plugins_package: str = "models.providers",
) -> ModelsGateway:
    discover_plugins(plugins_package)
    config = ConfigLoader.load(config_path)
    return build_gateway(config)


def build_gateway(config: GatewayConfig) -> ModelsGateway:
    return ModelsGateway(
        llm=LlmServiceFactory.create(config.llm),
        embedder=EmbedderFactory.create(config.embedder),
        reranker=RerankerFactory.create(config.reranker),
        llm_model=config.llm.model,
        embedder_model=config.embedder.model,
        reranker_model=config.reranker.model,
    )

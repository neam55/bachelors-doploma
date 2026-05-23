from __future__ import annotations

from pathlib import Path

from models.Config import ConfigLoader, GatewayConfig
from models.ModelsGateway import ModelsGateway
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
    return ModelsGateway.from_config(config)

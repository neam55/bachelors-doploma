from models.Base import BaseEmbeddingsProvider
from models.Config import ServiceConfig
from models.ProviderRegistry import embedder_registry

class EmbedderFactory:
    @staticmethod
    def create(config: ServiceConfig) -> BaseEmbeddingsProvider:
        ctx = config.to_context()
        return embedder_registry.create(
            config.provider,
            model=config.model,
            context=ctx,
        )

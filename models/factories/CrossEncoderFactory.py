from models.Base import BaseRerankerProvider
from models.Config import ServiceConfig
from models.ProviderRegistry import reranker_registry

class RerankerFactory:
    @staticmethod
    def create(config: ServiceConfig) -> BaseRerankerProvider:
        ctx = config.to_context()
        return reranker_registry.create(
            config.provider,
            model=config.model,
            context=ctx,
        )

from models.Base import BaseLLMProvider
from models.Config import ServiceConfig
from models.ProviderRegistry import llm_registry


class LlmServiceFactory:
    @staticmethod
    def create(config: ServiceConfig) -> BaseLLMProvider:
        ctx = config.to_context(section="llm")
        return llm_registry.create(
            config.provider,
            model=config.model,
            context=ctx,
        )

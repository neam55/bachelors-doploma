class GatewayError(Exception):
    pass

class ProviderNotFoundError(GatewayError):
    def __init__(self, capability: str, provider: str, available: list[str]):
        self.capability = capability
        self.provider = provider
        self.available = available
        super().__init__(
            f"No {capability} provider '{provider}'. "
            f"Available: {', '.join(available) or '(none — load plugins first)'}"
        )

class ProviderConfigurationError(GatewayError):
    pass

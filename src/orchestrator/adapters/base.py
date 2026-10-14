"""Base adapter class for external API integrations."""

from src.orchestrator.clients.base_http import RestClient
from src.orchestrator.config.settings import settings


class BaseApiAdapter:
    """Base class for domain API adapters."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.use_mock = settings.USE_MOCK_APIS
        self.client = RestClient(base_url=self.base_url)

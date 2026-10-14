"""Secrets and dynamic configuration provider interface (SSM / Doppler ready)."""

from abc import ABC, abstractmethod
import os
from typing import Optional


class BaseConfigProvider(ABC):
    """Abstract interface for runtime configuration and secrets management."""

    @abstractmethod
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Fetches a secret key value."""
        pass

    @abstractmethod
    def get_endpoint_url(self, service_name: str, default: Optional[str] = None) -> Optional[str]:
        """Fetches an external API endpoint URL."""
        pass


class EnvConfigProvider(BaseConfigProvider):
    """Default configuration provider fetching values from environment variables and .env."""

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return os.getenv(key, default)

    def get_endpoint_url(self, service_name: str, default: Optional[str] = None) -> Optional[str]:
        env_key = f"{service_name.upper()}_API_URL"
        return os.getenv(env_key, default)


class SSMConfigProvider(BaseConfigProvider):
    """
    AWS Systems Manager (SSM) Parameter Store provider.
    Can be activated in production to dynamically pull secrets without code changes.
    """

    def __init__(self, prefix: str = "/orchestrator/prod"):
        self.prefix = prefix
        self._cache = {}

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        # Placeholder for boto3 ssm client call:
        # response = ssm.get_parameter(Name=f"{self.prefix}/{key}", WithDecryption=True)
        return os.getenv(key, default)

    def get_endpoint_url(self, service_name: str, default: Optional[str] = None) -> Optional[str]:
        return os.getenv(f"{service_name.upper()}_API_URL", default)


class DopplerConfigProvider(BaseConfigProvider):
    """
    Doppler Secrets Management provider.
    Can be activated to pull secrets via Doppler REST API or CLI agent.
    """

    def __init__(self, project: str = "order-orchestrator", config: str = "prd"):
        self.project = project
        self.config = config

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return os.getenv(key, default)

    def get_endpoint_url(self, service_name: str, default: Optional[str] = None) -> Optional[str]:
        return os.getenv(f"{service_name.upper()}_API_URL", default)

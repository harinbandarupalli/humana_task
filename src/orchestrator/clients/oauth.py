"""OAuth2 Client Credentials token manager with caching and auto-refresh."""

import time
from typing import Optional
import httpx
from src.orchestrator.config.settings import settings
from src.orchestrator.core.logging import logger


class OAuth2TokenManager:
    """Manages token acquisition and caching for OAuth2 Client Credentials flow."""

    def __init__(
        self,
        token_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        scopes: Optional[str] = None,
    ):
        self.token_url = token_url or settings.OAUTH_TOKEN_URL
        self.client_id = client_id or settings.OAUTH_CLIENT_ID
        self.client_secret = client_secret or settings.OAUTH_CLIENT_SECRET
        self.scopes = scopes or settings.OAUTH_SCOPES

        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._refresh_buffer_seconds: float = 60.0  # Refresh 60s before expiry

    def is_token_valid(self) -> bool:
        """Checks if current token exists and has not expired."""
        return self._cached_token is not None and time.time() < (self._token_expires_at - self._refresh_buffer_seconds)

    def get_token(self) -> str:
        """
        Returns a valid OAuth2 bearer token.
        Retrieves from cache if valid, otherwise fetches a fresh token.
        """
        if self.is_token_valid():
            return self._cached_token  # type: ignore

        return self.fetch_new_token()

    def fetch_new_token(self) -> str:
        """Requests a new access token using client credentials."""
        # Offline development or mock mode
        if settings.USE_MOCK_APIS or not (self.client_id and self.client_secret):
            logger.debug("[OAuth2TokenManager] Using mock OAuth2 bearer token.")
            self._cached_token = "mock-oauth-access-token"
            self._token_expires_at = time.time() + 3600.0  # 1 hour validity
            return self._cached_token

        logger.info(f"[OAuth2TokenManager] Requesting fresh token from {self.token_url}...")
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scopes:
            payload["scope"] = self.scopes

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    self.token_url,
                    data=payload,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

                self._cached_token = data.get("access_token")
                expires_in = float(data.get("expires_in", 3600))
                self._token_expires_at = time.time() + expires_in

                logger.debug(f"[OAuth2TokenManager] Fresh token acquired, valid for {expires_in}s.")
                return self._cached_token  # type: ignore
        except Exception as e:
            logger.error(f"[OAuth2TokenManager] Failed to fetch OAuth2 token: {e}")
            raise


# Default singleton token manager instance
oauth_token_manager = OAuth2TokenManager()

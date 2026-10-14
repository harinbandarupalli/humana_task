"""Configurable REST HTTP Client with transparent OAuth2, retries, and correlation tracing."""

import time
import uuid
from typing import Any, Dict, Optional
import httpx
from src.orchestrator.clients.oauth import OAuth2TokenManager, oauth_token_manager
from src.orchestrator.config.settings import settings
from src.orchestrator.core.logging import logger


class HttpClientError(Exception):
    """Raised on 4xx HTTP responses."""
    def __init__(self, status_code: int, message: str, response_body: Optional[str] = None):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.response_body = response_body


class HttpServerError(Exception):
    """Raised on 5xx HTTP responses."""
    def __init__(self, status_code: int, message: str, response_body: Optional[str] = None):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.response_body = response_body


class RestClient:
    """
    Configurable HTTP REST Client with transparent OAuth2 Client Credentials
    authentication, retries, and correlation headers.
    """

    def __init__(
        self,
        base_url: str,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        default_headers: Optional[Dict[str, str]] = None,
        enable_oauth: bool = True,
        token_manager: Optional[OAuth2TokenManager] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout or settings.HTTP_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.HTTP_MAX_RETRIES
        self.default_headers = default_headers or {}
        self.enable_oauth = enable_oauth
        self.token_manager = token_manager or (oauth_token_manager if enable_oauth else None)

        self._client = httpx.Client(
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "OrderOrchestrator/1.0",
                **self.default_headers,
            },
        )

    def _build_headers(self, order_id: Optional[str] = None, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {}
        if order_id:
            headers["X-Correlation-ID"] = order_id
        headers["X-Request-ID"] = str(uuid.uuid4())

        # Transparently attach OAuth2 Bearer token
        if self.enable_oauth and self.token_manager:
            try:
                token = self.token_manager.get_token()
                headers["Authorization"] = f"Bearer {token}"
            except Exception as e:
                logger.warning(f"[RestClient] Could not resolve OAuth2 token: {e}")

        if extra_headers:
            headers.update(extra_headers)
        return headers

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        order_id: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes HTTP request with exponential backoff on transient errors.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        req_headers = self._build_headers(order_id, headers)
        attempt = 0

        while attempt <= self.max_retries:
            attempt += 1
            start_time = time.time()
            try:
                response = self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=req_headers,
                )
                duration_ms = int((time.time() - start_time) * 1000)
                logger.debug(f"HTTP {method} {url} -> {response.status_code} ({duration_ms}ms)")

                # Handle 2xx Success
                if 200 <= response.status_code < 300:
                    return response.json() if response.content else {}

                # Handle 4xx Client Errors (do not retry except 429)
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    raise HttpClientError(response.status_code, response.text, response.text)

                # Retry on 429 (rate limit) or 5xx (server error)
                if attempt <= self.max_retries:
                    backoff = settings.HTTP_BACKOFF_FACTOR * (2 ** (attempt - 1))
                    logger.warning(
                        f"Transient error HTTP {response.status_code} on {url}. Retrying attempt {attempt}/{self.max_retries} in {backoff:.2f}s..."
                    )
                    time.sleep(backoff)
                    continue

                raise HttpServerError(response.status_code, response.text, response.text)

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                if attempt <= self.max_retries:
                    backoff = settings.HTTP_BACKOFF_FACTOR * (2 ** (attempt - 1))
                    logger.warning(f"Connection error on {url}: {exc}. Retrying attempt {attempt}/{self.max_retries} in {backoff:.2f}s...")
                    time.sleep(backoff)
                    continue
                raise HttpServerError(504, f"Connection failed after {self.max_retries} retries: {exc}")

        raise HttpServerError(500, f"Request failed after {self.max_retries} retries")

    def get(self, path: str, **kwargs) -> Dict[str, Any]:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, json_data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        return self.request("POST", path, json_data=json_data, **kwargs)

    def put(self, path: str, json_data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        return self.request("PUT", path, json_data=json_data, **kwargs)

    def delete(self, path: str, **kwargs) -> Dict[str, Any]:
        return self.request("DELETE", path, **kwargs)

"""LiteLLM proxy admin API client.

Session 16: LiteLLM Proxy Integration
Async HTTP client for querying LiteLLM admin endpoints (cost tracking, health, model info).
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from haia.config import settings

logger = logging.getLogger(__name__)


class LiteLLMClient:
    """Async HTTP client for LiteLLM admin API.

    Provides methods for querying cost tracking data, health status,
    and model information from the LiteLLM proxy.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 10.0,
    ):
        """Initialize LiteLLM client.

        Args:
            base_url: LiteLLM proxy URL (defaults to settings.litellm_proxy_url)
            api_key: Master API key (defaults to settings.litellm_master_key)
            timeout: HTTP request timeout in seconds
        """
        self.base_url = (base_url or settings.litellm_proxy_url or "").rstrip("/")
        self.api_key = api_key or settings.litellm_master_key
        self.timeout = timeout

        if not self.base_url:
            logger.warning(
                "LiteLLM proxy URL not configured - client will not be functional"
            )

    async def get_spend_logs(
        self,
        api_key: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Query cost tracking records from LiteLLM spend logs.

        Args:
            api_key: Filter by virtual key (None = all keys)
            start_time: Filter by start time (ISO 8601)
            end_time: Filter by end time (ISO 8601)
            limit: Maximum records to return

        Returns:
            Dictionary with spend log records

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        if not self.base_url:
            logger.error("LiteLLM proxy URL not configured")
            return {"error": "proxy_not_configured", "records": []}

        params: dict[str, Any] = {"limit": limit}
        if api_key:
            params["api_key"] = api_key
        if start_time:
            params["startTime"] = start_time.isoformat()
        if end_time:
            params["endTime"] = end_time.isoformat()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/spend/logs",
                params=params,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            return response.json()

    async def get_health(self) -> dict[str, Any]:
        """Query LiteLLM proxy health status.

        Returns:
            Dictionary with health status, database connection, version info

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        if not self.base_url:
            logger.error("LiteLLM proxy URL not configured")
            return {"status": "unavailable", "error": "proxy_not_configured"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    async def get_model_info(self) -> dict[str, Any]:
        """Query configured models and their metadata.

        Returns:
            Dictionary with model list, provider info, routing configuration

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        if not self.base_url:
            logger.error("LiteLLM proxy URL not configured")
            return {"error": "proxy_not_configured", "models": []}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/model/info",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            return response.json()

"""
InstantRisk V3 - Generic REST API Connector

Connects to any REST API endpoint.
Used for integrating with syndicate's internal systems,
underwriting workbenches, and portfolio management systems.
"""

import aiohttp
from typing import Any, Dict, Optional
import logging

from app.services.connectors.base_connector import (
    BaseConnector,
    ConnectorConfig,
)

logger = logging.getLogger(__name__)


class GenericRESTConnector(BaseConnector):
    """
    Generic REST API connector for integrating with any HTTP/REST endpoint.

    Supports:
    - GET, POST, PUT, DELETE methods
    - API key, Basic auth, Bearer token authentication
    - Custom headers
    - JSON request/response
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _connect(self) -> bool:
        """Create aiohttp session."""
        headers = dict(self.config.headers)

        # Add authentication headers
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        elif self.config.username and self.config.password:
            import base64
            credentials = base64.b64encode(
                f"{self.config.username}:{self.config.password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {credentials}"

        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("Accept", "application/json")

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        self._session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
        )

        # Test connection if base_url provided
        if self.config.base_url:
            try:
                async with self._session.get(self.config.base_url) as resp:
                    return resp.status < 500
            except aiohttp.ClientError:
                return True  # Connection created, endpoint may not have root

        return True

    async def _disconnect(self) -> bool:
        """Close aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None
        return True

    async def _push(self, data: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """POST data to endpoint."""
        if not self._session:
            raise ConnectionError("Not connected")

        url = f"{self.config.base_url}{endpoint}" if self.config.base_url else endpoint

        async with self._session.post(url, json=data) as response:
            response.raise_for_status()
            return await response.json()

    async def _pull(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """GET data from endpoint."""
        if not self._session:
            raise ConnectionError("Not connected")

        endpoint = query.get("endpoint", "/")
        params = query.get("params", {})
        url = f"{self.config.base_url}{endpoint}" if self.config.base_url else endpoint

        async with self._session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def _healthcheck(self) -> bool:
        """Check if API is responding."""
        if not self._session:
            return False

        health_endpoint = self.config.extra.get("health_endpoint", "/health")
        url = f"{self.config.base_url}{health_endpoint}" if self.config.base_url else health_endpoint

        try:
            async with self._session.get(url) as response:
                return response.status < 500
        except aiohttp.ClientError:
            return False

    # Additional REST methods

    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """HTTP GET request."""
        return await self._pull({"endpoint": endpoint, "params": params or {}})

    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """HTTP POST request."""
        return await self._push(data, endpoint)

    async def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """HTTP PUT request."""
        if not self._session:
            raise ConnectionError("Not connected")

        url = f"{self.config.base_url}{endpoint}" if self.config.base_url else endpoint

        async with self._session.put(url, json=data) as response:
            response.raise_for_status()
            return await response.json()

    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """HTTP DELETE request."""
        if not self._session:
            raise ConnectionError("Not connected")

        url = f"{self.config.base_url}{endpoint}" if self.config.base_url else endpoint

        async with self._session.delete(url) as response:
            response.raise_for_status()
            return await response.json() if response.content_length else {"success": True}
